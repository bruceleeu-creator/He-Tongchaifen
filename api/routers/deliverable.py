"""
交付成果路由：设计、生成、下载、模板管理
"""
import json
import uuid
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from services.json_store import json_store
from services.ai_services.deliverable_design import deliverable_design_service
from services.deliverable_writer import deliverable_writer

router = APIRouter(prefix="/api/deliverables", tags=["交付成果"])


class ArtifactUpdate(BaseModel):
    deliverable_name: Optional[str] = None
    deliverable_type: Optional[str] = None
    status: Optional[str] = None
    review_status: Optional[str] = None
    ai_design_reason: Optional[str] = None
    template_key: Optional[str] = None


class SaveTemplateRequest(BaseModel):
    template_name: str


def _get_artifacts_path(run_id: str) -> Path:
    """获取交付成果数据文件路径"""
    return settings.get_run_dir(run_id) / "deliverable_artifacts.json"


def _get_deliverables_dir(run_id: str) -> Path:
    """获取交付成果文件存放目录"""
    d = settings.get_run_dir(run_id) / "deliverables"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _extract_tasks(task_data: dict) -> list:
    """从任务列表数据中提取任务数组
    兼容两种存储格式：
    - 直接格式：{"tasks": [...]}
    - 嵌套格式：{"data": {"tasks": [...]}}
    """
    if not task_data:
        return []
    if not isinstance(task_data, dict):
        return []
    # 优先取直接字段
    tasks = task_data.get("tasks")
    if isinstance(tasks, list):
        return tasks
    # 兼容嵌套格式
    inner = task_data.get("data")
    if isinstance(inner, dict):
        tasks = inner.get("tasks")
        if isinstance(tasks, list):
            return tasks
    return []


def _load_artifacts(run_id: str) -> dict:
    """加载交付成果数据"""
    path = _get_artifacts_path(run_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"total": 0, "items": []}


def _save_artifacts(run_id: str, data: dict):
    """保存交付成果数据"""
    path = _get_artifacts_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_artifact(design_data: dict, task: dict, covered_tasks: Optional[list] = None) -> dict:
    """构建交付成果条目

    需求7新增：
    - covered_tasks：归并模式下覆盖的任务列表，每项形如 {task_id, task_name, task_type, plan_end_date}
      归并后 artifact 覆盖多个任务，写入 covered_task_ids / covered_task_names 字段
    """
    artifact_id = f"art_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    # 归并模式：覆盖多任务
    if covered_tasks and len(covered_tasks) > 1:
        covered_ids = [t.get("task_id", "") for t in covered_tasks]
        covered_names = [t.get("task_name", "") for t in covered_tasks]
        primary_task = covered_tasks[0]
        # 归并后任务名以"覆盖 N 项"标注
        merged_name_hint = f"覆盖 {len(covered_tasks)} 项任务（{primary_task.get('task_name', '')} 等）"
    else:
        covered_ids = [task.get("task_id", "")]
        covered_names = [task.get("task_name", "")]
        primary_task = task
        merged_name_hint = None

    return {
        "artifact_id": artifact_id,
        "task_id": primary_task.get("task_id", ""),
        "task_name": primary_task.get("task_name", ""),
        "service_module": primary_task.get("service_module", ""),
        "task_type": primary_task.get("task_type", ""),
        # 需求7：归并字段
        "covered_task_ids": covered_ids,
        "covered_task_names": covered_names,
        "covered_task_count": len(covered_ids),
        "is_merged": len(covered_ids) > 1,
        "merge_hint": merged_name_hint or "",
        "deliverable_name": design_data.get("deliverable_name", "交付成果"),
        "deliverable_type": design_data.get("deliverable_type", "文档"),
        "file_format": design_data.get("file_format", "docx"),
        "template_key": design_data.get("template_key", ""),
        "template_name": design_data.get("template_name", ""),
        "reuse_source": design_data.get("reuse_source", "新生成"),
        "ai_design_reason": design_data.get("ai_design_reason", ""),
        "content_outline": design_data.get("content_outline", []),
        "content_sections": design_data.get("content_sections", []),
        "acceptance_criteria": design_data.get("acceptance_criteria", []),
        "client_inputs": design_data.get("client_inputs", []),
        "risk_notes": design_data.get("risk_notes", []),
        "next_actions": design_data.get("next_actions", []),
        "variables": design_data.get("variables", {}),
        "status": "已生成",
        "review_status": "待复核",
        "file_path": "",
        "download_url": "",
        "version": "v1",
        "created_at": now,
        "updated_at": now,
    }


async def _generate_artifact_for_task(
    run_id: str,
    task: dict,
    force_rule: bool = False,
    exclude_template_keys: Optional[list] = None,
    covered_tasks: Optional[list] = None,
) -> dict:
    """为单个任务生成交付成果

    force_rule=True 时强制走规则/模板模式，不调用 LLM，用于批量生成避免超时。
    exclude_template_keys：需求7，重新生成时排除已用过的模板，强制切换为另一套。
    covered_tasks：需求7，归并模式下覆盖的多任务列表，用于在文档中标注"针对哪几项任务"。
    """
    # 调用 AI 设计服务（透传 exclude_template_keys）
    kwargs = {"force_rule": force_rule}
    if exclude_template_keys:
        kwargs["exclude_template_keys"] = exclude_template_keys
    result = await deliverable_design_service.run(task=task, **kwargs)
    design_data = result.get("data", {})

    # 归并模式下补充 ai_design_reason
    if covered_tasks and len(covered_tasks) > 1:
        merge_desc = (
            f"本成果归并覆盖 {len(covered_tasks)} 项任务，"
            f"针对：{('、'.join([t.get('task_name', '') for t in covered_tasks[:3]]))}"
            f"{'等' if len(covered_tasks) > 3 else ''}。"
        )
        design_data["ai_design_reason"] = (
            merge_desc + " " + design_data.get("ai_design_reason", "")
        )

    # 构建成果条目
    artifact = _build_artifact(design_data, task, covered_tasks=covered_tasks)

    # 归并模式：在内容大纲前部插入"覆盖任务清单"章节
    if covered_tasks and len(covered_tasks) > 1:
        artifact["content_sections"] = _inject_covered_tasks_section(
            artifact.get("content_sections", []),
            covered_tasks,
        )

    # 生成 docx 文件
    deliverables_dir = _get_deliverables_dir(run_id)
    safe_task_name = "".join(c for c in task.get("task_name", "") if c.isalnum() or c in "_-")[:20]
    filename = f"{artifact['artifact_id']}_{safe_task_name}.docx"
    file_path = deliverables_dir / filename

    try:
        deliverable_writer.generate_docx(artifact, file_path)
        artifact["file_path"] = str(file_path)
        artifact["download_url"] = f"/api/deliverables/{run_id}/download/{artifact['artifact_id']}"
    except Exception as e:
        artifact["status"] = "生成失败"
        artifact["ai_design_reason"] += f"\n[文件生成异常: {str(e)}]"

    return artifact


def _inject_covered_tasks_section(content_sections: list, covered_tasks: list) -> list:
    """需求7：归并模式下在内容最前面插入"覆盖任务清单"章节

    明确告知本成果针对哪几项任务进行交付，避免重复列举。
    """
    if not covered_tasks:
        return content_sections

    bullets = []
    for idx, t in enumerate(covered_tasks, start=1):
        bullets.append(
            f"任务 {idx}：{t.get('task_name', '')}"
            f"（类型：{t.get('task_type', '-')}，"
            f"计划完成：{t.get('plan_end_date', '-') or '-'}, "
            f"责任人：{t.get('our_owner', '-') or '-'}）"
        )
    covered_section = {
        "title": "本成果覆盖的任务清单",
        "bullets": bullets,
    }
    return [covered_section] + list(content_sections)


def _group_tasks_by_module_and_type(tasks: list) -> list:
    """需求7：按 (service_module, deliverable_type) 归并任务

    返回归并后的"任务组"列表，每组包含：
    - key: 任务组 key
    - service_module / deliverable_type
    - tasks: 该组下所有任务
    - primary_task: 用于设计成果的主任务（取第一个）
    - need_merge: 是否需要归并（多于 1 个任务时为 True）

    归并判定：先调用 design 推断每个任务的 deliverable_type，再按 (module, type) 分组。
    """
    # 第一步：为每个任务推断 deliverable_type（轻量，走规则匹配，不生成完整设计）
    typed_tasks = []
    for t in tasks:
        matched = deliverable_writer.match_template(
            t.get("service_module", ""),
            t.get("task_type", ""),
            t.get("task_name", ""),
        )
        if matched:
            d_type = matched.get("deliverable_type", "文档")
        else:
            # 与 _generic_design 中默认 task_type -> deliverable_type 映射保持一致
            default_type_map = {
                "客户资料": "清单",
                "会议沟通": "文档",
                "交付验收": "确认函",
                "服务执行": "报告",
            }
            d_type = default_type_map.get(t.get("task_type", ""), "文档")
        typed_tasks.append((t, d_type))

    # 第二步：按 (service_module, deliverable_type) 分组
    groups: dict[tuple, list] = {}
    for t, d_type in typed_tasks:
        key = (t.get("service_module", "未分类"), d_type)
        groups.setdefault(key, []).append(t)

    # 第三步：构建任务组
    result = []
    for (module, d_type), group_tasks in groups.items():
        result.append({
            "key": f"{module}__{d_type}",
            "service_module": module,
            "deliverable_type": d_type,
            "tasks": group_tasks,
            "primary_task": group_tasks[0],
            "need_merge": len(group_tasks) > 1,
        })
    # 按 service_module 字母序排序，便于阅读
    result.sort(key=lambda g: g["service_module"])
    return result


@router.post("/{run_id}/generate")
async def generate_all_deliverables(run_id: str):
    """为全部任务生成交付成果设计和文件

    需求7：按 (service_module, deliverable_type) 归并同类任务，合并为 1 份成果。
    归并后每份成果明确"针对哪几项任务"，避免重复列举。
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    # 读取任务列表
    task_data = json_store.read(run_id, "task_list.json")
    if not task_data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = _extract_tasks(task_data)
    if not tasks:
        raise HTTPException(status_code=400, detail="任务列表为空")

    # 需求7：按 (service_module, deliverable_type) 分组
    groups = _group_tasks_by_module_and_type(tasks)

    # 加载已有成果（避免重复生成）- 需求7归并模式下以 covered_task_ids 集合判断
    artifacts_data = _load_artifacts(run_id)
    existing_items = artifacts_data.get("items", [])

    # 已归并成果的"任务组 key"集合
    existing_group_keys = set()
    for a in existing_items:
        if a.get("is_merged"):
            # 归并成果：以 (service_module, deliverable_type) 为 group key
            gk = f"{a.get('service_module', '')}__{a.get('deliverable_type', '')}"
            existing_group_keys.add(gk)
        else:
            # 单任务成果：以 task_id 为 key
            existing_group_keys.add(f"single__{a.get('task_id', '')}")

    new_items = []
    updated_items = []
    merged_count = 0

    for group in groups:
        gk = group["key"]
        primary_task = group["primary_task"]
        group_tasks = group["tasks"]

        # 跳过已生成（同组已存在归并成果或单任务成果）
        if gk in existing_group_keys:
            # 找到对应已有成果，保留
            for a in existing_items:
                if a.get("is_merged") and f"{a.get('service_module', '')}__{a.get('deliverable_type', '')}" == gk:
                    updated_items.append(a)
                    break
            continue

        # 批量生成强制规则/模板模式，避免每任务依次调用 LLM 导致前端超时
        artifact = await _generate_artifact_for_task(
            run_id,
            primary_task,
            force_rule=True,
            covered_tasks=group_tasks if group["need_merge"] else None,
        )
        new_items.append(artifact)
        if group["need_merge"]:
            merged_count += 1

    all_items = updated_items + new_items
    artifacts_data["items"] = all_items
    artifacts_data["total"] = len(all_items)
    _save_artifacts(run_id, artifacts_data)

    merge_msg = (
        f"，其中 {merged_count} 份为多任务归并成果"
        if merged_count > 0 else ""
    )
    return {
        "success": True,
        "run_id": run_id,
        "total": len(all_items),
        "new_count": len(new_items),
        "merged_count": merged_count,
        "group_count": len(groups),
        "message": (
            f"批量生成完成（规则/模板模式），新增 {len(new_items)} 项，共 {len(all_items)} 项{merge_msg}。"
            "如需 LLM 深度设计，请在任务列表中选择单个任务重新生成。"
        ),
    }


@router.post("/{run_id}/tasks/{task_id}/generate")
async def generate_task_deliverable(run_id: str, task_id: str):
    """为单个任务重新生成交付成果

    需求7：重新生成时从历史 artifact 中读取该任务已用过的 template_key，
    作为 exclude_template_keys 传入，强制切换为另一套模板。
    修复：保留累计历史 template_key 列表（template_history），
    避免每次刷新只记得最近一次，导致模板在两个之间来回切换。
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    # 读取任务列表
    task_data = json_store.read(run_id, "task_list.json")
    if not task_data:
        raise HTTPException(status_code=404, detail="任务列表不存在")

    tasks = _extract_tasks(task_data)
    task = None
    for t in tasks:
        if t.get("task_id") == task_id:
            task = t
            break

    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # 加载已有成果
    artifacts_data = _load_artifacts(run_id)
    items = artifacts_data.get("items", [])

    # 需求7修复：收集该任务历史所有用过的 template_key（包括累计的 template_history）
    template_history: list[str] = []
    for a in items:
        if a.get("task_id") == task_id:
            # 累积历史 template_history（如果存在）
            history = a.get("template_history", [])
            if isinstance(history, list):
                template_history.extend(history)
            # 加入当前 artifact 的 template_key
            if a.get("template_key"):
                template_history.append(a["template_key"])

    # 保序去重
    template_history = list(dict.fromkeys(template_history))
    # exclude_keys 即历史用过的全部 template_key
    exclude_keys = template_history[:]

    # 删除该任务旧成果
    items = [a for a in items if a.get("task_id") != task_id]

    # 重新生成（传入 exclude_template_keys 强制切换模板）
    artifact = await _generate_artifact_for_task(
        run_id,
        task,
        exclude_template_keys=exclude_keys if exclude_keys else None,
    )
    # 把历史 template_key 列表保存到新 artifact 中，便于下次刷新时累积排除
    artifact["template_history"] = template_history

    items.append(artifact)

    artifacts_data["items"] = items
    artifacts_data["total"] = len(items)
    _save_artifacts(run_id, artifacts_data)

    # 标记此次刷新使用的模板是否切换
    template_switched = bool(exclude_keys) and artifact.get("template_key") not in exclude_keys

    return {
        "success": True,
        "run_id": run_id,
        "task_id": task_id,
        "artifact": artifact,
        "template_switched": template_switched,
        "previous_template_count": len(exclude_keys),
        "message": (
            f"已切换为「{artifact.get('template_name', '')}」模板重新生成"
            if template_switched else "交付成果已重新生成（继续使用同套模板）"
        ),
    }


@router.get("/{run_id}")
async def get_deliverables(run_id: str):
    """获取本次运行的全部交付成果清单"""
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    artifacts_data = _load_artifacts(run_id)
    return {
        "success": True,
        "run_id": run_id,
        "total": artifacts_data.get("total", 0),
        "data": artifacts_data,
    }


@router.patch("/{run_id}/artifacts/{artifact_id}")
async def update_artifact(run_id: str, artifact_id: str, update: ArtifactUpdate):
    """人工修改成果名称、类型、状态、设计说明等"""
    artifacts_data = _load_artifacts(run_id)
    items = artifacts_data.get("items", [])

    found = False
    for i, item in enumerate(items):
        if item.get("artifact_id") == artifact_id:
            found = True
            update_dict = update.model_dump(exclude_none=True)
            for key, value in update_dict.items():
                if value is not None:
                    item[key] = value
            item["updated_at"] = datetime.now().isoformat()
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"交付成果不存在: {artifact_id}")

    artifacts_data["items"] = items
    _save_artifacts(run_id, artifacts_data)

    return {
        "success": True,
        "run_id": run_id,
        "artifact_id": artifact_id,
        "message": "交付成果已更新",
    }


@router.get("/{run_id}/download/{artifact_id}")
async def download_artifact(run_id: str, artifact_id: str):
    """下载单个交付成果文件"""
    artifacts_data = _load_artifacts(run_id)
    items = artifacts_data.get("items", [])

    artifact = None
    for item in items:
        if item.get("artifact_id") == artifact_id:
            artifact = item
            break

    if not artifact:
        raise HTTPException(status_code=404, detail=f"交付成果不存在: {artifact_id}")

    file_path = artifact.get("file_path", "")
    if not file_path or not Path(file_path).exists():
        # 文件不存在，尝试重新生成
        task_data = json_store.read(run_id, "task_list.json")
        tasks = _extract_tasks(task_data) if task_data else []
        task = None
        for t in tasks:
            if t.get("task_id") == artifact.get("task_id"):
                task = t
                break

        if task:
            deliverables_dir = _get_deliverables_dir(run_id)
            safe_task_name = "".join(c for c in task.get("task_name", "") if c.isalnum() or c in "_-")[:20]
            filename = f"{artifact_id}_{safe_task_name}.docx"
            new_path = deliverables_dir / filename
            try:
                deliverable_writer.generate_docx(artifact, new_path)
                artifact["file_path"] = str(new_path)
                artifact["status"] = "已生成"
                _save_artifacts(run_id, artifacts_data)
                file_path = str(new_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"文件生成失败: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail="文件不存在且关联任务已删除")

    filename = Path(file_path).name
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/{run_id}/download-all")
async def download_all_deliverables(run_id: str):
    """下载全部交付成果（打包为 zip）

    将当前 run_id 下所有已生成的 .docx 交付成果打包为 zip 文件返回。
    跳过文件缺失的条目；若无任何可下载文件则返回 404。
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    artifacts_data = _load_artifacts(run_id)
    items = artifacts_data.get("items", [])

    # 收集所有实际存在的 docx 文件
    docx_files: list[tuple[str, str]] = []  # (arcname, abs_path)
    for item in items:
        file_path = item.get("file_path", "")
        if not file_path or not Path(file_path).exists():
            continue
        # zip 内文件名：用任务名+原文件名，避免重名
        task_name = item.get("task_name", "task")
        safe_name = "".join(c for c in task_name if c.isalnum() or c in "_-()")[:30]
        arcname = f"{safe_name}_{Path(file_path).name}" if safe_name else Path(file_path).name
        docx_files.append((arcname, file_path))

    if not docx_files:
        raise HTTPException(status_code=404, detail="没有可下载的交付成果文件，请先生成")

    # 创建临时 zip 文件
    deliverables_dir = _get_deliverables_dir(run_id)
    zip_filename = f"{run_id}_deliverables.zip"
    zip_path = deliverables_dir / zip_filename

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, abs_path in docx_files:
            zf.write(abs_path, arcname)

    return FileResponse(
        path=str(zip_path),
        filename=zip_filename,
        media_type="application/zip",
    )


@router.post("/{run_id}/artifacts/{artifact_id}/save-template")
async def save_as_template(run_id: str, artifact_id: str, req: SaveTemplateRequest):
    """将人工确认后的成果沉淀为模板"""
    artifacts_data = _load_artifacts(run_id)
    items = artifacts_data.get("items", [])

    artifact = None
    for item in items:
        if item.get("artifact_id") == artifact_id:
            artifact = item
            break

    if not artifact:
        raise HTTPException(status_code=404, detail=f"交付成果不存在: {artifact_id}")

    # 加载模板库
    templates_path = settings.API_DIR / "data" / "deliverable_templates.json"
    templates_data = {"templates": []}
    if templates_path.exists():
        try:
            with open(templates_path, "r", encoding="utf-8") as f:
                templates_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    templates = templates_data.get("templates", [])

    # 检查是否已有相同 template_key
    template_key = artifact.get("template_key", "")
    if not template_key or template_key.startswith("generic_"):
        template_key = f"custom_{uuid.uuid4().hex[:8]}"

    # 构建新模板
    new_template = {
        "template_key": template_key,
        "template_name": req.template_name or artifact.get("template_name", "自定义模板"),
        "deliverable_type": artifact.get("deliverable_type", "文档"),
        "applicable_task_type": artifact.get("task_type", ""),
        "applicable_service_module": artifact.get("service_module", ""),
        "content_schema": {
            "title": artifact.get("deliverable_name", ""),
            "sections": artifact.get("content_outline", []),
        },
        "variables": list(artifact.get("variables", {}).keys()),
        "created_from_artifact_id": artifact_id,
        "usage_count": 0,
        "updated_at": datetime.now().isoformat(),
    }

    # 替换或追加
    existing_idx = -1
    for i, t in enumerate(templates):
        if t.get("template_key") == template_key:
            existing_idx = i
            break

    if existing_idx >= 0:
        templates[existing_idx] = new_template
    else:
        templates.append(new_template)

    templates_data["templates"] = templates
    templates_path.parent.mkdir(parents=True, exist_ok=True)
    templates_path.write_text(json.dumps(templates_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新成果状态
    artifact["reuse_source"] = "已沉淀为模板"
    artifact["template_key"] = template_key
    _save_artifacts(run_id, artifacts_data)

    return {
        "success": True,
        "run_id": run_id,
        "artifact_id": artifact_id,
        "template_key": template_key,
        "message": f"已保存为模板: {new_template['template_name']}",
    }
