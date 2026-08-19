"""
全流程自动化路由
编排完整的文档分析流程：合同识别 → 计划识别 → 交叉核验 → 动态追问 → 任务拆分 → 颗粒度检查 → 待确认清单 → 风险提示 → 报告校验

特性：
- 进度可见：每步执行后更新状态，前端可轮询查看
- 可中断：用户可随时暂停，后续恢复继续执行
- 可跳过：用户可跳过任意步骤
- 规则保底+后台重试：AI 失败时自动回退到规则解析
"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.json_store import json_store
from services.ai_config_store import ai_config_store
from services.ai_services.contract_recognition import contract_recognition_service
from services.ai_services.plan_recognition import plan_recognition_service
from services.ai_services.cross_validation import cross_validation_service
from services.ai_services.clarification_form import clarification_form_service
from services.ai_services.task_split import task_split_service
from services.ai_services.granularity_check import GranularityCheckService
from services.ai_services.pending_list import PendingListService
from services.ai_services.risk_warning import RiskWarningService
from services.validators import report_validator
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["全流程自动化"])

granularity_service = GranularityCheckService()
pending_service = PendingListService()
risk_service = RiskWarningService()


# ========== 流程步骤定义 ==========

PIPELINE_STEPS = [
    {"step": 1, "key": "contract_recognition", "name": "合同识别", "description": "深度读取合同原文，提取核心字段"},
    {"step": 2, "key": "plan_recognition", "name": "计划识别", "description": "识别年度服务计划（如已上传）"},
    {"step": 3, "key": "cross_check", "name": "交叉核验", "description": "合同与计划交叉核验，识别冲突"},
    {"step": 4, "key": "clarification", "name": "动态追问", "description": "根据合同摘要生成追问问题"},
    {"step": 5, "key": "task_split", "name": "任务拆分", "description": "基于合同+回答生成任务主表"},
    {"step": 6, "key": "granularity_check", "name": "颗粒度检查", "description": "检查任务拆分粒度是否合理"},
    {"step": 7, "key": "pending_list", "name": "待确认清单", "description": "生成待人工确认事项清单"},
    {"step": 8, "key": "risk_warning", "name": "风险提示", "description": "生成风险提示清单"},
    {"step": 9, "key": "validation", "name": "报告校验", "description": "9 项校验规则检查报告质量"},
]


def _init_pipeline_state(run_id: str) -> dict:
    """初始化流程状态"""
    return {
        "run_id": run_id,
        "status": "idle",  # idle / running / paused / completed / failed
        "current_step": 0,
        "steps": [
            {
                "step": s["step"],
                "key": s["key"],
                "name": s["name"],
                "description": s["description"],
                "status": "pending",  # pending / running / completed / skipped / failed
                "mode": "",  # rule / llm / llm_enhanced
                "mode_label": "",
                "started_at": "",
                "completed_at": "",
                "message": "",
                "error": "",
            }
            for s in PIPELINE_STEPS
        ],
        "started_at": "",
        "completed_at": "",
        "llm_available": ai_config_store.is_available,
        "llm_model": ai_config_store.model if ai_config_store.is_available else "",
    }


def _get_pipeline_state(run_id: str) -> dict:
    """读取流程状态"""
    state = json_store.read(run_id, "pipeline_state.json")
    if not state:
        state = _init_pipeline_state(run_id)
        json_store.write(run_id, "pipeline_state.json", state)
    return state


def _save_pipeline_state(run_id: str, state: dict):
    """保存流程状态"""
    json_store.write(run_id, "pipeline_state.json", state)


def _update_pipeline_meta(run_id: str, **kwargs):
    """更新流程级别的元数据（不影响步骤状态）

    避免用过期的本地 state 覆盖 _update_step 已写入的步骤状态
    """
    state = _get_pipeline_state(run_id)
    for k, v in kwargs.items():
        state[k] = v
    _save_pipeline_state(run_id, state)


def _update_step(run_id: str, step_key: str, status: str, message: str = "", mode: str = "", mode_label: str = "", error: str = ""):
    """更新单个步骤状态"""
    state = _get_pipeline_state(run_id)
    for s in state["steps"]:
        if s["key"] == step_key:
            s["status"] = status
            if status == "running":
                s["started_at"] = datetime.now().isoformat()
            elif status in ("completed", "skipped", "failed"):
                s["completed_at"] = datetime.now().isoformat()
            s["message"] = message or s["message"]
            s["mode"] = mode or s["mode"]
            s["mode_label"] = mode_label or s["mode_label"]
            s["error"] = error or s["error"]
            break
    _save_pipeline_state(run_id, state)


def _is_paused(run_id: str) -> bool:
    """检查流程是否已暂停"""
    state = _get_pipeline_state(run_id)
    return state["status"] == "paused"


# ========== 步骤执行函数 ==========

async def _execute_contract_recognition(run_id: str) -> dict:
    """步骤1：合同识别"""
    parsed = json_store.read(run_id, "contract_parsed.json")
    if not parsed:
        existing = json_store.read(run_id, "contract_result.json")
        if existing:
            return {"success": True, "mode": "cached", "message": "合同识别结果已存在"}
        # 检查是否只上传了计划文件，给出更明确的提示
        plan_parsed = json_store.read(run_id, "plan_parsed.json")
        if plan_parsed:
            raise ValueError(
                "未上传合同文件，请先上传合同。当前仅检测到年度服务计划文件，"
                "全流程分析需要合同文件作为基础。"
            )
        raise ValueError("未上传合同文件，请先上传合同")

    contract_text = parsed.get("full_text", "") or "\n".join(parsed.get("paragraphs", []))
    if not contract_text.strip():
        raise ValueError("合同文本为空")

    filename = parsed.get("filename", "")
    result = await contract_recognition_service.run(contract_text=contract_text, filename=filename)

    if not result.get("success"):
        raise ValueError(result.get("message", "合同识别失败"))

    # 注入来源文件清单（与 recognition 路由保持一致）
    source_files = parsed.get("source_files", [{"filename": filename, "parsed_at": parsed.get("parsed_at", "")}])
    if isinstance(result.get("data"), dict):
        result["data"]["source_files"] = source_files
        result["data"]["file_analyses"] = [
            {"filename": sf.get("filename", ""), "analyzed": True, "note": "已纳入合同综合识别"}
            for sf in source_files
        ]
    result["source_files"] = source_files

    json_store.write(run_id, "contract_result.json", result)
    json_store.update_run_meta(run_id, {
        "status": "contract_recognized",
        "contract_mode": result.get("mode", "unknown"),
        "contract_mode_label": result.get("mode_label", ""),
    })
    return {
        "success": True,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": "合同识别完成",
    }


async def _execute_plan_recognition(run_id: str) -> dict:
    """步骤2：计划识别"""
    parsed = json_store.read(run_id, "plan_parsed.json")
    if not parsed:
        _update_step(run_id, "plan_recognition", "skipped", "未上传年度服务计划，已跳过")
        return {"success": True, "mode": "skipped", "message": "未上传年度服务计划，已跳过"}

    plan_text = parsed.get("full_text", "") or "\n".join(parsed.get("paragraphs", []))
    if not plan_text.strip():
        raise ValueError("年度服务计划文本为空")

    result = await plan_recognition_service.run(plan_text=plan_text, filename=parsed.get("filename", ""))
    if not result.get("success"):
        raise ValueError(result.get("message", "计划识别失败"))

    # 注入来源文件清单（与 recognition 路由保持一致）
    source_files = parsed.get("source_files", [{"filename": parsed.get("filename", ""), "parsed_at": parsed.get("parsed_at", "")}])
    if isinstance(result.get("data"), dict):
        result["data"]["source_files"] = source_files
        result["data"]["file_analyses"] = [
            {"filename": sf.get("filename", ""), "analyzed": True, "note": "已纳入计划综合识别"}
            for sf in source_files
        ]
    result["source_files"] = source_files

    json_store.write(run_id, "plan_result.json", result)
    json_store.update_run_meta(run_id, {"status": "plan_recognized"})
    return {
        "success": True,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": "年度服务计划识别完成",
    }


async def _execute_cross_check(run_id: str) -> dict:
    """步骤3：交叉核验"""
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise ValueError("未找到合同识别结果")

    plan_result = json_store.read(run_id, "plan_result.json")

    result = await cross_validation_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False),
        plan_result=json.dumps(plan_result, ensure_ascii=False) if plan_result else "",
    )

    json_store.write(run_id, "cross_check_result.json", result)
    return {
        "success": result.get("success", True),
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": "交叉核验完成",
    }


async def _execute_clarification(run_id: str) -> dict:
    """步骤4：动态追问"""
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise ValueError("未找到合同识别结果")

    contract_str = json.dumps(contract_result, ensure_ascii=False)
    result = await clarification_form_service.run(contract_result=contract_str, task_list="")

    if not result.get("success"):
        raise ValueError(result.get("message", "澄清表单生成失败"))

    json_store.write(run_id, "clarification_form.json", result)
    json_store.update_run_meta(run_id, {"status": "clarification_generated"})

    # 自动提交空回答，让流程继续
    form_data = result.get("data", result)
    items = form_data.get("items", [])
    user_answers = {}
    for item in items:
        pending = item.get("pending_item", "")
        if pending:
            user_answers[pending] = ""

    json_store.write(run_id, "user_answers.json", {
        "answers": user_answers,
        "submitted_at": datetime.now().isoformat(),
        "auto_submitted": True,
    })

    return {
        "success": True,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": f"动态追问已生成（{len(items)}个问题），已自动跳过可后续补充",
    }


async def _execute_task_split(run_id: str) -> dict:
    """步骤5：任务拆分"""
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise ValueError("未找到合同识别结果")

    user_answers_data = json_store.read(run_id, "user_answers.json")
    user_answers = user_answers_data.get("answers", {}) if user_answers_data else {}

    plan_result = json_store.read(run_id, "plan_result.json")
    cross_check = json_store.read(run_id, "cross_check_result.json")

    # 读取辅助资料（启动会纪要等），作为任务拆分的补充上下文
    auxiliary_context = ""
    meeting_parsed = json_store.read(run_id, "meeting_minutes_parsed.json")
    if meeting_parsed:
        meeting_text = meeting_parsed.get("full_text", "")
        if meeting_text:
            auxiliary_context = f"===== 启动会纪要: {meeting_parsed.get('filename', '')} =====\n{meeting_text[:3000]}"

    result = await task_split_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False),
        plan_result=json.dumps(plan_result, ensure_ascii=False) if plan_result else "",
        cross_check_result=json.dumps(cross_check, ensure_ascii=False) if cross_check else "",
        user_answers=json.dumps(user_answers, ensure_ascii=False),
        auxiliary_context=auxiliary_context,
    )

    if not result.get("success"):
        raise ValueError(result.get("message", "任务拆分失败"))

    json_store.write(run_id, "task_list.json", result.get("data", result))
    json_store.update_run_meta(run_id, {
        "status": "task_split_done",
        "task_mode": result.get("mode", "unknown"),
        "task_mode_label": result.get("mode_label", ""),
    })

    task_data = result.get("data", {})
    task_count = len(task_data.get("tasks", []))
    return {
        "success": True,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": f"任务拆分完成，共 {task_count} 个任务",
    }


async def _execute_granularity_check(run_id: str) -> dict:
    """步骤6：颗粒度检查"""
    task_data = json_store.read(run_id, "task_list.json")
    if not task_data:
        raise ValueError("任务列表不存在")

    tasks = task_data.get("tasks", [])
    result = await granularity_service.run(task_list=str(tasks))
    json_store.write(run_id, "granularity_result.json", result.get("data", {}))
    return {
        "success": result.get("success", True),
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": "颗粒度检查完成",
    }


async def _execute_pending_list(run_id: str) -> dict:
    """步骤7：待确认清单"""
    contract_result = json_store.read(run_id, "contract_result.json", {})
    task_data = json_store.read(run_id, "task_list.json", {})
    tasks = task_data.get("tasks", []) if task_data else []

    result = await pending_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
        task_list=json.dumps(tasks, ensure_ascii=False) if tasks else "",
    )

    json_store.write(run_id, "pending_list.json", result.get("data", result))
    return {
        "success": result.get("success", True),
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": "待确认清单生成完成",
    }


async def _execute_risk_warning(run_id: str) -> dict:
    """步骤8：风险提示"""
    contract_result = json_store.read(run_id, "contract_result.json", {})
    plan_result = json_store.read(run_id, "plan_result.json", {})
    task_data = json_store.read(run_id, "task_list.json", {})
    tasks = task_data.get("tasks", []) if task_data else []

    result = await risk_service.run(
        contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
        plan_result=json.dumps(plan_result, ensure_ascii=False) if plan_result else "",
        task_list=json.dumps(tasks, ensure_ascii=False) if tasks else "",
    )

    json_store.write(run_id, "risk_list.json", result.get("data", result))
    return {
        "success": result.get("success", True),
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "message": "风险提示生成完成",
    }


async def _execute_validation(run_id: str) -> dict:
    """步骤9：报告校验"""
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise ValueError("未找到合同识别结果")

    contract_data = contract_result.get("data", contract_result)
    summary = contract_data.get("contract_summary", {})

    task_list = json_store.read(run_id, "task_list.json")
    if not task_list:
        raise ValueError("未找到任务列表")

    pending_list = json_store.read(run_id, "pending_list.json", {})
    risk_list = json_store.read(run_id, "risk_list.json", {})
    has_plan = json_store.read(run_id, "plan_parsed.json") is not None

    result = report_validator.validate(
        contract_summary=summary,
        task_list=task_list,
        pending_list=pending_list,
        risk_list=risk_list,
        run_mode=settings.parser_mode,
        has_plan=has_plan,
    )

    json_store.write(run_id, "validation_result.json", result)

    passed = result["passed"]
    error_count = len(result["errors"])
    warning_count = len(result["warnings"])
    return {
        "success": True,
        "mode": settings.parser_mode,
        "mode_label": settings.run_mode_label,
        "message": f"校验{'通过' if passed else '未通过'}，{error_count}个错误，{warning_count}个警告",
    }


# 步骤执行映射
STEP_EXECUTORS = {
    "contract_recognition": _execute_contract_recognition,
    "plan_recognition": _execute_plan_recognition,
    "cross_check": _execute_cross_check,
    "clarification": _execute_clarification,
    "task_split": _execute_task_split,
    "granularity_check": _execute_granularity_check,
    "pending_list": _execute_pending_list,
    "risk_warning": _execute_risk_warning,
    "validation": _execute_validation,
}


# ========== API 接口 ==========

@router.post("/{run_id}/run")
async def run_pipeline(run_id: str):
    """启动或恢复全流程

    从当前未完成的步骤开始执行，每步完成后检查是否已暂停
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    state = _get_pipeline_state(run_id)

    # 检查是否已完成
    if state["status"] == "completed":
        return {
            "success": True,
            "run_id": run_id,
            "status": "completed",
            "message": "全流程已完成",
            "state": state,
        }

    # 标记为运行中
    _update_pipeline_meta(run_id,
        status="running",
        started_at=state.get("started_at") or datetime.now().isoformat(),
        llm_available=ai_config_store.is_available,
        llm_model=ai_config_store.model if ai_config_store.is_available else "",
    )

    # 重新加载最新状态
    state = _get_pipeline_state(run_id)

    # 执行未完成的步骤
    for step in state["steps"]:
        if step["status"] in ("completed", "skipped"):
            continue

        # 检查是否已暂停
        if _is_paused(run_id):
            return {
                "success": True,
                "run_id": run_id,
                "status": "paused",
                "message": f"流程已暂停，当前步骤: {step['name']}",
                "state": _get_pipeline_state(run_id),
            }

        # 更新步骤状态为运行中
        _update_step(run_id, step["key"], "running")
        _update_pipeline_meta(run_id, current_step=step["step"])

        # 执行步骤
        try:
            executor = STEP_EXECUTORS.get(step["key"])
            if not executor:
                _update_step(run_id, step["key"], "failed", error="未找到步骤执行器")
                _update_pipeline_meta(run_id, status="failed")
                raise HTTPException(status_code=500, detail=f"未找到步骤执行器: {step['key']}")

            result = await executor(run_id)

            # 如果步骤已被标记为 skipped（如计划识别），不覆盖
            current_state = _get_pipeline_state(run_id)
            current_step = next((s for s in current_state["steps"] if s["key"] == step["key"]), None)
            if current_step and current_step["status"] == "skipped":
                continue

            _update_step(
                run_id, step["key"], "completed",
                message=result.get("message", ""),
                mode=result.get("mode", ""),
                mode_label=result.get("mode_label", ""),
            )

        except ValueError as e:
            _update_step(run_id, step["key"], "failed", error=str(e))
            _update_pipeline_meta(run_id, status="failed")
            return {
                "success": False,
                "run_id": run_id,
                "status": "failed",
                "message": f"步骤 [{step['name']}] 执行失败: {str(e)}",
                "state": _get_pipeline_state(run_id),
            }
        except Exception as e:
            logger.error(f"Pipeline step {step['key']} error: {e}", exc_info=True)
            _update_step(run_id, step["key"], "failed", error=str(e))
            _update_pipeline_meta(run_id, status="failed")
            return {
                "success": False,
                "run_id": run_id,
                "status": "failed",
                "message": f"步骤 [{step['name']}] 执行异常: {str(e)}",
                "state": _get_pipeline_state(run_id),
            }

    # 全部完成
    _update_pipeline_meta(run_id, status="completed", completed_at=datetime.now().isoformat())

    json_store.update_run_meta(run_id, {"status": "pipeline_completed"})

    return {
        "success": True,
        "run_id": run_id,
        "status": "completed",
        "message": "全流程分析完成",
        "state": _get_pipeline_state(run_id),
    }


@router.get("/{run_id}/status")
async def get_pipeline_status(run_id: str):
    """获取全流程进度"""
    state = _get_pipeline_state(run_id)
    completed = sum(1 for s in state["steps"] if s["status"] == "completed")
    skipped = sum(1 for s in state["steps"] if s["status"] == "skipped")
    failed = sum(1 for s in state["steps"] if s["status"] == "failed")
    total = len(state["steps"])

    return {
        "success": True,
        "run_id": run_id,
        "status": state["status"],
        "progress": {
            "total": total,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "percentage": round((completed + skipped) / total * 100, 1),
        },
        "current_step": state["current_step"],
        "steps": state["steps"],
        "llm_available": state.get("llm_available", False),
        "llm_model": state.get("llm_model", ""),
        "started_at": state.get("started_at", ""),
        "completed_at": state.get("completed_at", ""),
    }


@router.post("/{run_id}/pause")
async def pause_pipeline(run_id: str):
    """暂停全流程"""
    state = _get_pipeline_state(run_id)
    if state["status"] != "running":
        return {
            "success": True,
            "run_id": run_id,
            "status": state["status"],
            "message": f"流程当前状态为 {state['status']}，无需暂停",
        }

    state["status"] = "paused"
    _save_pipeline_state(run_id, state)
    return {
        "success": True,
        "run_id": run_id,
        "status": "paused",
        "message": "流程已暂停，可随时恢复",
    }


@router.post("/{run_id}/resume")
async def resume_pipeline(run_id: str):
    """恢复全流程（等同于 run）"""
    state = _get_pipeline_state(run_id)
    if state["status"] not in ("paused", "failed", "idle"):
        return {
            "success": True,
            "run_id": run_id,
            "status": state["status"],
            "message": f"流程当前状态为 {state['status']}，无需恢复",
            "state": state,
        }

    # 如果之前是 failed，重置失败步骤为 pending
    if state["status"] == "failed":
        for s in state["steps"]:
            if s["status"] == "failed":
                s["status"] = "pending"
                s["error"] = ""
        _save_pipeline_state(run_id, state)

    _update_pipeline_meta(run_id, status="running")

    # 调用 run 继续
    return await run_pipeline(run_id)


@router.post("/{run_id}/skip/{step_key}")
async def skip_step(run_id: str, step_key: str):
    """跳过指定步骤"""
    state = _get_pipeline_state(run_id)

    step = next((s for s in state["steps"] if s["key"] == step_key), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"步骤不存在: {step_key}")

    if step["status"] == "completed":
        return {
            "success": True,
            "message": f"步骤 [{step['name']}] 已完成，无需跳过",
        }

    _update_step(run_id, step_key, "skipped", "用户手动跳过")
    return {
        "success": True,
        "run_id": run_id,
        "message": f"步骤 [{step['name']}] 已跳过",
        "step_key": step_key,
    }


@router.post("/{run_id}/retry/{step_key}")
async def retry_step(run_id: str, step_key: str):
    """重试指定步骤"""
    state = _get_pipeline_state(run_id)

    step = next((s for s in state["steps"] if s["key"] == step_key), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"步骤不存在: {step_key}")

    # 重置步骤状态
    step["status"] = "pending"
    step["error"] = ""
    step["started_at"] = ""
    step["completed_at"] = ""
    _save_pipeline_state(run_id, state)

    # 执行该步骤
    _update_step(run_id, step_key, "running")
    try:
        executor = STEP_EXECUTORS.get(step_key)
        if not executor:
            raise ValueError(f"未找到步骤执行器: {step_key}")

        result = await executor(run_id)
        _update_step(
            run_id, step_key, "completed",
            message=result.get("message", ""),
            mode=result.get("mode", ""),
            mode_label=result.get("mode_label", ""),
        )
        return {
            "success": True,
            "run_id": run_id,
            "message": f"步骤 [{step['name']}] 重试成功: {result.get('message', '')}",
        }
    except Exception as e:
        _update_step(run_id, step_key, "failed", error=str(e))
        return {
            "success": False,
            "run_id": run_id,
            "message": f"步骤 [{step['name']}] 重试失败: {str(e)}",
        }


@router.post("/{run_id}/reset")
async def reset_pipeline(run_id: str):
    """重置全流程状态"""
    state = _init_pipeline_state(run_id)
    state["status"] = "idle"
    _save_pipeline_state(run_id, state)
    return {
        "success": True,
        "run_id": run_id,
        "message": "全流程状态已重置",
        "state": state,
    }


@router.get("/steps")
async def get_pipeline_steps():
    """获取全流程步骤定义"""
    return {
        "success": True,
        "steps": PIPELINE_STEPS,
        "total": len(PIPELINE_STEPS),
    }
