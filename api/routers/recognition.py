"""
合同识别路由
读取上传的合同文本 → 调用合同识别服务 → 保存识别结果 → 输出合同摘要
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.json_store import json_store
from services.ai_services.contract_recognition import contract_recognition_service
from services.ai_services.plan_recognition import plan_recognition_service
from services.ai_services.cross_validation import cross_validation_service

router = APIRouter(prefix="/api/recognition", tags=["合同识别"])


def _recognition_response(run_id: str, result: dict, message: str = "") -> dict:
    """统一前端识别接口响应，避免页面误读 data 层级。"""
    return {
        "success": result.get("success", True),
        "run_id": run_id,
        "mode": result.get("mode", "rule"),
        "mode_label": result.get("mode_label", ""),
        "data_source": result.get("data_source", ""),
        "service": result.get("service", ""),
        "skipped": result.get("skipped", False),
        "data": result.get("data", result),
        "message": message or result.get("message", ""),
    }


def _empty_plan_result(message: str) -> dict:
    return {
        "success": True,
        "skipped": True,
        "mode": "rule",
        "mode_label": "真实解析模式(规则解析)",
        "data_source": "未上传年度服务计划",
        "service": "plan_recognition",
        "message": message,
        "data": {
            "service_modules": [],
            "milestones": [],
            "client_data": [],
            "meetings": [],
            "pending_items": [{
                "待确认事项": "未上传年度服务计划",
                "原因": "当前运行实例只有合同资料，计划识别已跳过",
                "建议向谁确认": "项目负责人",
                "不确认的影响": "任务拆分将主要依据合同内容，缺少年度计划约束",
            }],
            "raw_text": "",
            "source_file": "",
        },
    }


@router.post("/{run_id}/contract")
async def recognize_contract(run_id: str):
    """合同识别

    读取上传的合同文本，调用合同识别服务，保存识别结果
    """
    # 读取解析后的合同文本
    parsed = json_store.read(run_id, "contract_parsed.json")
    if not parsed:
        # 如果没有上传合同，检查是否已有识别结果（如 Mock 数据）
        existing = json_store.read(run_id, "contract_result.json")
        if existing:
            # 已有识别结果，直接返回，无需重新识别
            return _recognition_response(run_id, existing, "合同识别结果已存在（来自Mock数据）")
        raise HTTPException(status_code=404, detail="未找到已上传的合同文件，请先上传合同")

    # 获取完整文本
    contract_text = parsed.get("full_text", "")
    if not contract_text:
        # 回退到段落拼接
        paragraphs = parsed.get("paragraphs", [])
        contract_text = "\n".join(paragraphs)

    if not contract_text.strip():
        raise HTTPException(status_code=400, detail="合同文本为空，无法识别")

    # 调用合同识别服务
    filename = parsed.get("filename", "")
    result = await contract_recognition_service.run(
        contract_text=contract_text,
        filename=filename,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "合同识别失败"))

    # 注入来源文件清单（让用户知道 AI 分析了哪些文件）
    source_files = parsed.get("source_files", [{"filename": filename, "parsed_at": parsed.get("parsed_at", "")}])
    if isinstance(result.get("data"), dict):
        result["data"]["source_files"] = source_files
        result["data"]["file_analyses"] = [
            {"filename": sf.get("filename", ""), "analyzed": True, "note": "已纳入合同综合识别"}
            for sf in source_files
        ]
    result["source_files"] = source_files

    # 保存识别结果
    json_store.write(run_id, "contract_result.json", result)

    # 更新 run 元数据
    json_store.update_run_meta(run_id, {
        "status": "contract_recognized",
        "contract_mode": result.get("mode", "unknown"),
        "contract_mode_label": result.get("mode_label", ""),
    })

    return _recognition_response(run_id, result, "合同识别完成")


@router.get("/{run_id}/contract")
async def get_contract_result(run_id: str):
    """获取合同识别结果"""
    result = json_store.read(run_id, "contract_result.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果，请先执行合同识别")
    return _recognition_response(run_id, result)


@router.get("/{run_id}/summary")
async def get_contract_summary(run_id: str):
    """获取合同识别摘要

    返回合同核心字段摘要，作为用户确认节点
    """
    result = json_store.read(run_id, "contract_result.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果，请先执行合同识别")

    data = result.get("data", result)
    summary = data.get("contract_summary", {})

    if not summary:
        raise HTTPException(status_code=404, detail="合同识别摘要未生成")

    return {
        "success": True,
        "run_id": run_id,
        "mode": result.get("mode", "unknown"),
        "mode_label": result.get("mode_label", ""),
        "data_source": result.get("data_source", ""),
        "summary": summary,
        "basic_info": data.get("basic_info", []),
        "service_scope": data.get("service_scope", []),
        "pending_items": data.get("pending_items", []),
        "confirm_required": True,
        "message": "请确认合同识别摘要，确认后再进行任务拆分",
    }


@router.post("/{run_id}/summary/confirm")
async def confirm_contract_summary(run_id: str):
    """确认合同识别摘要

    用户确认合同识别摘要后，更新状态为已确认
    """
    result = json_store.read(run_id, "contract_result.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果")

    # 更新确认状态
    result["summary_confirmed"] = True
    result["confirmed_at"] = __import__("datetime").datetime.now().isoformat()
    json_store.write(run_id, "contract_result.json", result)

    json_store.update_run_meta(run_id, {
        "status": "summary_confirmed",
    })

    return {
        "success": True,
        "run_id": run_id,
        "message": "合同识别摘要已确认，可以进入澄清问题环节",
    }


@router.post("/{run_id}/plan")
async def recognize_plan(run_id: str):
    """年度服务计划识别"""
    parsed = json_store.read(run_id, "plan_parsed.json")
    if not parsed:
        result = _empty_plan_result("未上传年度服务计划，已跳过计划识别")
        json_store.write(run_id, "plan_result.json", result)
        return _recognition_response(run_id, result)

    plan_text = parsed.get("full_text", "")
    if not plan_text:
        paragraphs = parsed.get("paragraphs", [])
        plan_text = "\n".join(paragraphs)

    if not plan_text.strip():
        raise HTTPException(status_code=400, detail="年度服务计划文本为空，无法识别")

    result = await plan_recognition_service.run(
        plan_text=plan_text,
        filename=parsed.get("filename", ""),
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "年度服务计划识别失败"))

    # 注入来源文件清单（让用户知道 AI 分析了哪些文件）
    source_files = parsed.get("source_files", [{"filename": parsed.get("filename", ""), "parsed_at": parsed.get("parsed_at", "")}])
    if isinstance(result.get("data"), dict):
        result["data"]["source_files"] = source_files
        result["data"]["file_analyses"] = [
            {"filename": sf.get("filename", ""), "analyzed": True, "note": "已纳入计划综合识别"}
            for sf in source_files
        ]
    result["source_files"] = source_files

    json_store.write(run_id, "plan_result.json", result)

    json_store.update_run_meta(run_id, {
        "status": "plan_recognized",
    })

    return _recognition_response(run_id, result, "年度服务计划识别完成")


@router.get("/{run_id}/plan")
async def get_plan_result(run_id: str):
    """获取年度服务计划识别结果"""
    result = json_store.read(run_id, "plan_result.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到年度服务计划识别结果")
    return _recognition_response(run_id, result)


@router.post("/{run_id}/cross-check")
async def cross_check(run_id: str):
    """交叉核验"""
    import json as json_mod

    contract_result = json_store.read(run_id, "contract_result.json")
    plan_result = json_store.read(run_id, "plan_result.json")

    if not contract_result:
        raise HTTPException(status_code=404, detail="未找到合同识别结果")

    result = await cross_validation_service.run(
        contract_result=json_mod.dumps(contract_result, ensure_ascii=False),
        plan_result=json_mod.dumps(plan_result, ensure_ascii=False) if plan_result else "",
    )

    json_store.write(run_id, "cross_check_result.json", result)

    return _recognition_response(run_id, result, "交叉核验完成")


@router.get("/{run_id}/cross-check")
async def get_cross_check(run_id: str):
    """获取交叉核验结果"""
    result = json_store.read(run_id, "cross_check_result.json")
    if not result:
        raise HTTPException(status_code=404, detail="未找到交叉核验结果")
    return _recognition_response(run_id, result)
