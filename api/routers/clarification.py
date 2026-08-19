"""
澄清表单路由
基于合同识别结果动态生成追问问题
支持二次拆分（用户回答后合并生成任务主表）
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.json_store import json_store
from services.ai_services.clarification_form import clarification_form_service
from services.ai_services.task_split import task_split_service

router = APIRouter(prefix="/api/clarification", tags=["澄清表单"])


@router.post("/{run_id}/form")
async def generate_clarification_form(run_id: str):
    """生成动态澄清表单

    根据合同识别结果动态生成追问问题
    """
    # 读取合同识别结果
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果，请先执行合同识别")

    # 将结果转为字符串传递给服务
    contract_str = json.dumps(contract_result, ensure_ascii=False)

    result = await clarification_form_service.run(
        contract_result=contract_str,
        task_list="",
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "澄清表单生成失败"))

    # 保存澄清表单
    json_store.write(run_id, "clarification_form.json", result)

    json_store.update_run_meta(run_id, {
        "status": "clarification_generated",
    })

    return result


@router.get("/{run_id}/form")
async def get_clarification_form(run_id: str):
    """获取澄清表单"""
    result = json_store.read(run_id, "clarification_form.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到澄清表单，请先生成")
    return result


class AnswerItem(BaseModel):
    item_id: str
    pending_item: str
    confirmed_value: str


class SubmitAnswersRequest(BaseModel):
    answers: list[AnswerItem]


@router.post("/{run_id}/submit-answers")
async def submit_answers(run_id: str, req: SubmitAnswersRequest):
    """提交澄清问题回答

    用户一次性提交所有回答，保存后进入二次拆分
    """
    # 读取澄清表单
    form = json_store.read(run_id, "clarification_form.json")
    if not form:
        raise HTTPException(status_code=404, detail="未找到澄清表单")

    # 更新表单中的确认值
    form_data = form.get("data", form)
    items = form_data.get("items", [])

    answer_map = {a.item_id: a.confirmed_value for a in req.answers}

    for item in items:
        item_id = item.get("item_id", "")
        if item_id in answer_map:
            item["confirmed_value"] = answer_map[item_id]
            item["status"] = "已确认" if answer_map[item_id] else "待确认"

    # 保存更新后的表单
    form["data"] = form_data
    json_store.write(run_id, "clarification_form.json", form)

    # 构建用户回答字典（pending_item → confirmed_value）
    user_answers = {}
    for item in items:
        pending = item.get("pending_item", "")
        value = item.get("confirmed_value", "")
        if pending and value:
            user_answers[pending] = value

    # 保存用户回答
    json_store.write(run_id, "user_answers.json", {
        "answers": user_answers,
        "submitted_at": __import__("datetime").datetime.now().isoformat(),
    })

    json_store.update_run_meta(run_id, {
        "status": "answers_submitted",
    })

    return {
        "success": True,
        "run_id": run_id,
        "total_answered": len(user_answers),
        "message": "澄清问题回答已提交，可以执行二次任务拆分",
    }


@router.post("/{run_id}/second-split")
async def second_round_split(run_id: str):
    """二次任务拆分

    基于合同识别结果 + 用户回答，重新生成任务主表
    """
    import json as json_mod

    # 读取合同识别结果
    contract_result = json_store.read(run_id, "contract_result.json")
    if not contract_result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果")

    # 读取用户回答
    user_answers_data = json_store.read(run_id, "user_answers.json")
    if not user_answers_data:
        raise HTTPException(status_code=400, detail="未找到用户回答，请先提交澄清问题回答")

    user_answers = user_answers_data.get("answers", {})

    # 读取年度服务计划（可选）
    plan_result = json_store.read(run_id, "plan_result.json")
    cross_check = json_store.read(run_id, "cross_check_result.json")

    # 调用任务拆分服务
    result = await task_split_service.run(
        contract_result=json_mod.dumps(contract_result, ensure_ascii=False),
        plan_result=json_mod.dumps(plan_result, ensure_ascii=False) if plan_result else "",
        cross_check_result=json_mod.dumps(cross_check, ensure_ascii=False) if cross_check else "",
        user_answers=json_mod.dumps(user_answers, ensure_ascii=False),
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "二次拆分失败"))

    # 保存任务列表（只保存 data 部分，避免双重嵌套）
    json_store.write(run_id, "task_list.json", result.get("data", result))

    json_store.update_run_meta(run_id, {
        "status": "task_split_done",
        "task_mode": result.get("mode", "unknown"),
        "task_mode_label": result.get("mode_label", ""),
    })

    return result
