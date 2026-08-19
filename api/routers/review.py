"""
复核路由：待确认清单、风险提示
基于合同识别结果生成，不再使用 Mock 样例数据
"""
import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.json_store import json_store
from services.ai_services.pending_list import PendingListService
from services.ai_services.risk_warning import RiskWarningService

router = APIRouter(prefix="/api/review", tags=["复核服务"])


class PendingItemUpdate(BaseModel):
    pending_item: Optional[str] = None
    related_tasks: Optional[str] = None
    reason: Optional[str] = None
    suggest_confirm_to: Optional[str] = None
    impact_if_not_confirmed: Optional[str] = None
    confirmed_value: Optional[str] = None
    status: Optional[str] = None

pending_service = PendingListService()
risk_service = RiskWarningService()


@router.post("/{run_id}/pending-list")
async def generate_pending_list(run_id: str):
    """生成待确认清单

    基于合同识别结果提取待确认事项
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    # 获取合同识别结果和任务列表
    contract_result = json_store.read(run_id, "contract_result.json", {})
    task_data = json_store.read(run_id, "task_list.json", {})
    tasks = task_data.get("data", {}).get("tasks", []) if "data" in task_data else task_data.get("tasks", [])

    # 执行生成
    result = await pending_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
        task_list=json.dumps(tasks, ensure_ascii=False) if tasks else "",
    )

    # 保存（只保存 data 部分，避免双重嵌套）
    json_store.write(run_id, "pending_list.json", result.get("data", result))

    return {
        "success": result.get("success", False),
        "run_id": run_id,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "data_source": result.get("data_source", ""),
        "data": result.get("data", {}),
        "message": "待确认清单生成完成" if result.get("success") else "待确认清单生成失败",
    }


@router.get("/{run_id}/pending-list")
async def get_pending_list(run_id: str):
    """获取待确认清单"""
    data = json_store.read(run_id, "pending_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="待确认清单不存在，请先生成")
    return {"success": True, "data": data}


@router.post("/{run_id}/risk-warning")
async def generate_risk_warning(run_id: str):
    """生成风险提示清单

    基于合同识别结果生成风险提示
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    # 获取识别结果和任务列表
    contract_result = json_store.read(run_id, "contract_result.json", {})
    plan_result = json_store.read(run_id, "plan_result.json", {})
    task_data = json_store.read(run_id, "task_list.json", {})
    tasks = task_data.get("data", {}).get("tasks", []) if "data" in task_data else task_data.get("tasks", [])

    # 执行生成
    result = await risk_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
        plan_result=json.dumps(plan_result, ensure_ascii=False) if plan_result else "",
        task_list=json.dumps(tasks, ensure_ascii=False) if tasks else "",
    )

    # 保存（只保存 data 部分，避免双重嵌套）
    json_store.write(run_id, "risk_list.json", result.get("data", result))

    return {
        "success": result.get("success", False),
        "run_id": run_id,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "data_source": result.get("data_source", ""),
        "data": result.get("data", {}),
        "message": "风险提示生成完成" if result.get("success") else "风险提示生成失败",
    }


@router.get("/{run_id}/risk-warning")
async def get_risk_warning(run_id: str):
    """获取风险提示清单"""
    data = json_store.read(run_id, "risk_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="风险提示清单不存在，请先生成")
    return {"success": True, "data": data}


@router.patch("/{run_id}/pending-list/{item_id}")
async def update_pending_item(run_id: str, item_id: str, update: PendingItemUpdate):
    """更新待确认清单单条记录"""
    data = json_store.read(run_id, "pending_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="待确认清单不存在，请先生成")

    items = data.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail="待确认清单数据格式错误")

    found = False
    target_index = -1

    for i, item in enumerate(items):
        # 兼容老数据：如果老数据没有 item_id，用索引生成一个
        if not item.get("item_id"):
            item["item_id"] = f"pending_{i}_{uuid.uuid4().hex[:6]}"

        if item.get("item_id") == item_id:
            target_index = i
            found = True
            # 更新字段
            update_dict = update.model_dump(exclude_none=True)
            for key, value in update_dict.items():
                if value is not None:
                    item[key] = value
            item["updated_at"] = datetime.now().isoformat()
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"待确认事项不存在: {item_id}")

    data["items"] = items
    data["updated_at"] = datetime.now().isoformat()
    json_store.write(run_id, "pending_list.json", data)

    return {
        "success": True,
        "run_id": run_id,
        "item_id": item_id,
        "data": items[target_index],
        "message": "待确认事项已更新",
    }
