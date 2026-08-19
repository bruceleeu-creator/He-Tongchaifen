"""
导出路由：CSV导出、Markdown导出、下载
"""
import os
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import io

from services.json_store import json_store
from services.csv_export import csv_exporter
from services.ai_services.pending_list import PendingListService
from services.ai_services.risk_warning import RiskWarningService

router = APIRouter(prefix="/api/export", tags=["导出服务"])
pending_service = PendingListService()
risk_service = RiskWarningService()


@router.get("/{run_id}/csv")
async def export_csv(run_id: str, download: bool = True):
    """导出任务列表为 CSV（UTF-8 BOM）

    Args:
        run_id: 运行实例 ID
        download: 是否下载文件（True=文件下载，False=返回内容）
    """
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])

    if download:
        # 保存文件并返回下载
        filepath = csv_exporter.export_tasks(tasks, run_id)
        filename = os.path.basename(filepath)
        return FileResponse(
            filepath,
            media_type="text/csv",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
        )
    else:
        # 返回 CSV 内容
        csv_content = csv_exporter.export_to_string(tasks)
        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=task_list_{run_id}.csv"},
        )


@router.get("/{run_id}/markdown")
async def export_markdown(run_id: str, download: bool = True):
    """导出任务列表为 Markdown"""
    data = json_store.read(run_id, "task_list.json")
    if not data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = data.get("tasks", [])

    if download:
        filepath = csv_exporter.export_markdown_file(tasks, run_id)
        filename = os.path.basename(filepath)
        return FileResponse(
            filepath,
            media_type="text/markdown",
            filename=filename,
        )
    else:
        content = csv_exporter.export_markdown(tasks, run_id)
        return {
            "success": True,
            "run_id": run_id,
            "content": content,
        }


@router.get("/{run_id}/full")
async def export_full(run_id: str):
    """导出完整数据包（任务列表 + 待确认清单 + 风险提示 + 颗粒度检查）"""
    task_data = json_store.read(run_id, "task_list.json", {})
    pending_data = json_store.read(run_id, "pending_list.json", {})
    risk_data = json_store.read(run_id, "risk_list.json", {})
    granularity_data = json_store.read(run_id, "granularity_result.json", {})
    clarification_data = json_store.read(run_id, "clarification_form.json", {})

    tasks = task_data.get("tasks", [])
    contract_result = json_store.read(run_id, "contract_result.json", {})
    plan_result = json_store.read(run_id, "plan_result.json", {})

    if tasks and not pending_data:
        pending_result = await pending_service.run(
            contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
            task_list=json.dumps(tasks, ensure_ascii=False),
        )
        pending_data = pending_result.get("data", pending_result)
        json_store.write(run_id, "pending_list.json", pending_data)

    if tasks and not risk_data:
        risk_result = await risk_service.run(
            contract_result=json.dumps(contract_result, ensure_ascii=False) if contract_result else "",
            plan_result=json.dumps(plan_result, ensure_ascii=False) if plan_result else "",
            task_list=json.dumps(tasks, ensure_ascii=False),
        )
        risk_data = risk_result.get("data", risk_result)
        json_store.write(run_id, "risk_list.json", risk_data)

    # 生成 Markdown 导出内容
    md_content = csv_exporter.export_markdown(tasks, run_id)

    # 添加待确认清单
    if pending_data and pending_data.get("items"):
        md_content += "\n\n## 待人工确认清单\n\n"
        md_content += "| 待确认事项 | 涉及任务 | 原因 | 建议向谁确认 | 不确认的影响 |\n"
        md_content += "|---|---|---|---|---|\n"
        for item in pending_data["items"]:
            md_content += f"| {item.get('pending_item', '')} | {item.get('related_tasks', '')} | {item.get('reason', '')} | {item.get('suggest_confirm_to', '')} | {item.get('impact_if_not_confirmed', '')} |\n"

    # 添加风险提示
    if risk_data and risk_data.get("risks"):
        md_content += "\n\n## 风险提示清单\n\n"
        md_content += "| 风险点 | 风险来源 | 影响范围 | 建议处理方式 |\n"
        md_content += "|---|---|---|---|\n"
        for risk in risk_data["risks"]:
            md_content += f"| {risk.get('risk_point', '')} | {risk.get('risk_source', '')} | {risk.get('impact_scope', '')} | {risk.get('suggestion', '')} |\n"

    # 保存文件（防路径穿越：校验 run_id，最终路径必须仍在导出目录内）
    from services.path_safety import validate_id
    validate_id(run_id, "run_id")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{run_id}_full_export_{timestamp}.md"
    export_root = csv_exporter.export_dir.resolve()
    filepath = (export_root / filename).resolve()
    if not filepath.is_relative_to(export_root):
        raise HTTPException(status_code=400, detail=f"路径越界的文件名: {filename}")
    filepath.write_text(md_content, encoding="utf-8")

    return {
        "success": True,
        "run_id": run_id,
        "filename": filename,
        "download_url": f"/api/export/{run_id}/download?file={filename}",
        "task_count": len(tasks),
        "pending_count": len(pending_data.get("items", [])) if pending_data else 0,
        "risk_count": len(risk_data.get("risks", [])) if risk_data else 0,
        "message": "完整数据包导出成功",
    }


@router.get("/{run_id}/download")
async def download_file(run_id: str, file: str):
    """下载导出的文件（file 仅允许纯文件名，禁止任何目录部分）"""
    from services.path_safety import validate_id

    validate_id(run_id, "run_id")
    # 防路径穿越：剥离目录部分并校验，最终路径必须仍在导出目录内
    safe_name = os.path.basename(file)
    if not safe_name or safe_name in {".", ".."} or safe_name != file:
        raise HTTPException(status_code=400, detail=f"非法文件名: {file}")
    export_root = csv_exporter.export_dir.resolve()
    filepath = (export_root / safe_name).resolve()
    if not filepath.is_relative_to(export_root):
        raise HTTPException(status_code=400, detail=f"路径越界的文件名: {file}")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file}")

    return FileResponse(
        filepath,
        filename=file,
    )
