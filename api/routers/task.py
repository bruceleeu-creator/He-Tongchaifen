"""
任务路由：拆分、获取、更新、新增、删除、标记复核、颗粒度检查、报告校验
"""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Body

from config import settings
from models.task import TaskCreate, TaskUpdate
from services.json_store import json_store
from services.ai_services.task_split import TaskSplitService
from services.ai_services.granularity_check import GranularityCheckService
from services.validators import report_validator

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])

task_split_service = TaskSplitService()
granularity_service = GranularityCheckService()


@router.post("/{run_id}/split")
async def split_tasks(run_id: str):
    """执行任务拆分（首次拆分，不包含用户回答）"""
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    # 获取识别和核验结果
    contract_result = json_store.read(run_id, "contract_result.json", {})
    plan_result = json_store.read(run_id, "plan_result.json", {})
    cross_check = json_store.read(run_id, "cross_check_result.json", {})

    # 执行拆分（不传 user_answers，使用空字符串）
    result = await task_split_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
        plan_result=json.dumps(plan_result, ensure_ascii=False) if plan_result else "",
        cross_check_result=json.dumps(cross_check, ensure_ascii=False) if cross_check else "",
        user_answers="",
    )

    # 保存任务列表（只保存 data 部分，避免双重嵌套）
    task_data = result.get("data", {})
    json_store.write(run_id, "task_list.json", task_data)

    return {
        "success": result.get("success", False),
        "run_id": run_id,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "data_source": result.get("data_source", ""),
        "data": task_data,
        "message": "任务拆分完成" if result.get("success") else "任务拆分失败",
    }


@router.get("/{run_id}")
async def get_tasks(run_id: str):
    """获取任务列表"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在，请先执行拆分")
    return {"success": True, "run_id": run_id, "data": data}


@router.get("/{run_id}/{task_id}")
async def get_task(run_id: str, task_id: str):
    """获取单个任务"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])
    for task in tasks:
        if task.get("task_id") == task_id:
            return {"success": True, "run_id": run_id, "data": task}

    raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")


@router.put("/{run_id}/{task_id}")
async def update_task(run_id: str, task_id: str, task_update: TaskUpdate):
    """更新任务"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])
    found = False
    for i, task in enumerate(tasks):
        if task.get("task_id") == task_id:
            # 更新字段
            update_dict = task_update.model_dump(exclude_none=True)
            tasks[i].update(update_dict)
            tasks[i]["updated_at"] = datetime.now().isoformat()
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    data["tasks"] = tasks
    data["updated_at"] = datetime.now().isoformat()
    json_store.write(run_id, "task_list.json", data)

    return {
        "success": True,
        "run_id": run_id,
        "task_id": task_id,
        "message": "任务已更新",
        "data": tasks[[i for i, t in enumerate(tasks) if t.get("task_id") == task_id][0]],
    }


@router.post("/{run_id}")
async def create_task(run_id: str, task: TaskCreate):
    """新增任务"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    new_task = task.model_dump()
    new_task["task_id"] = f"task_manual_{uuid.uuid4().hex[:8]}"
    new_task["created_at"] = datetime.now().isoformat()
    new_task["updated_at"] = datetime.now().isoformat()

    data["tasks"].append(new_task)
    data["total"] = len(data["tasks"])
    data["updated_at"] = datetime.now().isoformat()
    json_store.write(run_id, "task_list.json", data)

    return {
        "success": True,
        "run_id": run_id,
        "data": new_task,
        "message": "任务已新增",
    }


@router.delete("/{run_id}/{task_id}")
async def delete_task(run_id: str, task_id: str):
    """删除任务"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])
    original_len = len(tasks)
    data["tasks"] = [t for t in tasks if t.get("task_id") != task_id]

    if len(data["tasks"]) == original_len:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    data["total"] = len(data["tasks"])
    data["updated_at"] = datetime.now().isoformat()
    json_store.write(run_id, "task_list.json", data)

    return {
        "success": True,
        "run_id": run_id,
        "task_id": task_id,
        "message": "任务已删除",
    }


@router.patch("/{run_id}/{task_id}/review")
async def mark_review(run_id: str, task_id: str, status: str = Body(..., embed=True)):
    """标记任务复核状态

    status: 待复核 / 已确认 / 需修改 / 剔除
    """
    valid_statuses = ["待复核", "已确认", "需修改", "剔除"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效的复核状态，可选: {', '.join(valid_statuses)}")

    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])
    found = False
    for task in tasks:
        if task.get("task_id") == task_id:
            task["review_status"] = status
            task["updated_at"] = datetime.now().isoformat()
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    data["tasks"] = tasks
    data["updated_at"] = datetime.now().isoformat()
    json_store.write(run_id, "task_list.json", data)

    return {
        "success": True,
        "run_id": run_id,
        "task_id": task_id,
        "review_status": status,
        "message": f"任务复核状态已标记为: {status}",
    }


@router.patch("/{run_id}/batch-review")
async def batch_mark_review(
    run_id: str,
    status: str = Body(..., embed=True),
    service_module: str = Body("", embed=True),
    task_ids: list = Body([], embed=True),
):
    """批量标记任务复核状态（需求6：按服务模块同类批量复核）

    支持两种范围：
    - 按 service_module：把该模块下所有「待复核」任务批量标记为指定状态
    - 按 task_ids：传入显式任务 id 列表，仅标记这些任务

    status: 待复核 / 已确认 / 需修改 / 剔除
    """
    valid_statuses = ["待复核", "已确认", "需修改", "剔除"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效的复核状态，可选: {', '.join(valid_statuses)}")

    if not service_module and not task_ids:
        raise HTTPException(status_code=400, detail="必须提供 service_module 或 task_ids 之一")

    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])
    updated_ids: list[str] = []
    now = datetime.now().isoformat()

    for task in tasks:
        tid = task.get("task_id", "")
        # 范围匹配：服务模块（仅作用于「待复核」状态，避免重复处理已确认任务）
        if service_module:
            if task.get("service_module", "") == service_module and task.get("review_status") == "待复核":
                task["review_status"] = status
                task["updated_at"] = now
                updated_ids.append(tid)
                continue
        # 显式任务 id 列表：不受当前状态限制
        if task_ids and tid in task_ids:
            task["review_status"] = status
            task["updated_at"] = now
            updated_ids.append(tid)

    if not updated_ids:
        raise HTTPException(status_code=404, detail="未找到符合条件的待复核任务")

    data["tasks"] = tasks
    data["updated_at"] = now
    json_store.write(run_id, "task_list.json", data)

    scope = f"服务模块「{service_module}」" if service_module else f"指定任务 {len(task_ids)} 条"
    return {
        "success": True,
        "run_id": run_id,
        "scope": scope,
        "updated_count": len(updated_ids),
        "updated_task_ids": updated_ids,
        "review_status": status,
        "message": f"{scope}下共 {len(updated_ids)} 条任务已批量标记为: {status}",
    }


@router.post("/{run_id}/granularity-check")
async def check_granularity(run_id: str):
    """任务颗粒度检查"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在，请先执行拆分")

    tasks = data.get("tasks", [])

    # 执行检查
    result = await granularity_service.run(task_list=str(tasks))

    # 保存结果
    check_data = result.get("data", {})
    json_store.write(run_id, "granularity_result.json", check_data)

    return {
        "success": result.get("success", False),
        "run_id": run_id,
        "mode": result.get("mode", "mock"),
        "data": check_data,
        "message": "颗粒度检查完成" if result.get("success") else "颗粒度检查失败",
    }


@router.get("/{run_id}/field-options")
async def get_field_options(run_id: str = ""):
    """获取字段选项标准"""
    from config import settings
    return {
        "success": True,
        "field_options": settings.FIELD_OPTIONS,
        "field_mapping": settings.FIELD_MAPPING,
    }


@router.post("/{run_id}/validate")
async def validate_report(run_id: str):
    """报告校验

    在导出前校验报告内容是否符合合同真实信息
    返回校验结果（通过/不通过 + 错误/警告列表）
    """
    # 读取合同识别结果
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果，无法校验")

    contract_data = contract_result.get("data", contract_result)
    summary = contract_data.get("contract_summary", {})

    # 读取任务列表
    task_list = json_store.read(run_id, "task_list.json")
    if not task_list:
        raise HTTPException(status_code=404, detail="未找到任务列表，无法校验")

    task_data = task_list.get("data", task_list)

    # 读取待确认清单和风险提示（可选）
    pending_list = json_store.read(run_id, "pending_list.json", {})
    risk_list = json_store.read(run_id, "risk_list.json", {})

    # 检查是否上传了年度服务计划
    has_plan = json_store.read(run_id, "plan_parsed.json") is not None

    # 执行校验
    result = report_validator.validate(
        contract_summary=summary,
        task_list=task_data,
        pending_list=pending_list,
        risk_list=risk_list,
        run_mode=settings.parser_mode,
        has_plan=has_plan,
    )

    # 保存校验结果
    json_store.write(run_id, "validation_result.json", result)

    return {
        "success": True,
        "run_id": run_id,
        "passed": result["passed"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "checks": result["checks"],
        "mode": settings.parser_mode,
        "mode_label": settings.run_mode_label,
        "message": "校验通过，可以导出报告" if result["passed"] else f"校验未通过，存在{len(result['errors'])}个阻断性错误",
    }


@router.get("/{run_id}/validate")
async def get_validation_result(run_id: str):
    """获取校验结果"""
    result = json_store.read(run_id, "validation_result.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到校验结果，请先执行校验")
    return result
