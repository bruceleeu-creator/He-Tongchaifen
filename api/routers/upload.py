"""
上传、解析、创建 run 路由
真实合同上传时不再初始化 Mock 数据
"""
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from config import settings
from services.json_store import json_store
from services.docx_parser import docx_parser

router = APIRouter(prefix="/api/upload", tags=["上传与解析"])


def _infer_file_type(filename: str, full_text: str, requested_type: str) -> tuple:
    """根据文件名和正文修正明显选错的资料类型。

    返回 (file_type, warning) 元组：
    - file_type: 最终确定的文件类型
    - warning: 当内容与用户选择类型不一致时的警告提示，无警告时为空字符串

    当用户显式选择了 contract 或 plan 时，尊重用户选择，不强制修正类型，
    仅在返回结果中给出警告提示，避免管线因找不到 contract_parsed.json 而失败。
    """
    content = f"{filename}\n{full_text[:2000]}"
    plan_keywords = ["年度服务计划", "服务计划", "年度计划", "实施计划", "工作计划", "月度", "季度"]
    contract_keywords = ["合同", "协议", "甲方", "乙方", "委托方", "服务方", "服务费用", "付款"]

    plan_score = sum(1 for keyword in plan_keywords if keyword in content)
    contract_score = sum(1 for keyword in contract_keywords if keyword in content)

    inferred = requested_type
    warning = ""

    # 内容强烈指向 plan
    if plan_score >= 2 and plan_score >= contract_score:
        if requested_type == "contract":
            # 用户显式选择了合同，尊重用户选择，仅给出警告
            warning = (
                f"文件内容包含「服务计划」相关关键词（命中 {plan_score} 个），"
                f"但已按您选择的「合同」类型处理。如确认是计划文件，"
                f"请重新选择文件类型为「年度服务计划」后重新上传。"
            )
        else:
            inferred = "plan"
    # 内容强烈指向 contract
    elif contract_score >= 3 and contract_score > plan_score:
        if requested_type == "plan":
            # 用户显式选择了计划，尊重用户选择，仅给出警告
            warning = (
                f"文件内容包含「合同」相关关键词（命中 {contract_score} 个），"
                f"但已按您选择的「年度服务计划」类型处理。如确认是合同文件，"
                f"请重新选择文件类型为「合同」后重新上传。"
            )
        else:
            inferred = "contract"

    return inferred, warning


def _merge_meta_list(meta: dict, key: str, value: str) -> list:
    values = list(meta.get(key, []) or [])
    if value not in values:
        values.append(value)
    return values


def _load_parsed_files(run_id: str) -> list:
    """加载已上传文件聚合清单 parsed_files.json"""
    data = json_store.read(run_id, "parsed_files.json", default=[])
    if not isinstance(data, list):
        return []
    return data


def _save_parsed_files(run_id: str, files: list):
    """保存 parsed_files.json"""
    json_store.write(run_id, "parsed_files.json", files)


def _invalidate_downstream_results(run_id: str, file_type: str):
    """资料重新上传或删除后清理依赖旧解析结果生成的产物。

    按文件类型区分清理范围（对应需求：合同删除重置全部，计划删除仅清计划）：

    - contract（合同）删除/重传：下游全部失效，等同于 run 数据重置
      清理 contract_result / plan_result / cross_check / clarification /
      task_list / granularity / pending / risk / pipeline_state /
      validation_result / deliverable_artifacts 及 deliverables 目录
    - plan（年度服务计划）删除/重传：仅清计划相关，保留合同识别与任务列表
      仅清理 plan_result / cross_check_result / pipeline_state /
      validation_result（交叉核验依赖计划，校验依赖交叉核验）
    - 其他类型（meeting_minutes 等）：按计划口径处理

    注意：不删除 parsed_files.json 和已上传的原始文件，保留多文件记录。
    兼容文件 contract_parsed.json / plan_parsed.json 由 _rewrite_type_parsed_json 单独处理。
    """
    # 合同删除：清理全部下游产物（run 数据重置）
    contract_filenames = [
        "contract_result.json",
        "plan_result.json",
        "cross_check_result.json",
        "clarification_form.json",
        "user_answers.json",  # 修复：用户回答属于澄清表单下游产物，应一并清除
        "task_list.json",
        "granularity_result.json",
        "pending_list.json",
        "risk_list.json",
        "pipeline_state.json",
        "validation_result.json",
        "deliverable_artifacts.json",
        # 兼容别名文件（历史命名，可能不存在，删除是安全的）
        "contract_summary.json",
        "plan_summary.json",
        "recognition_result.json",
        "clarification_questions.json",
    ]
    # 计划删除：仅清理计划相关 + 依赖计划的产物（交叉核验、校验、流程状态）
    plan_filenames = [
        "plan_result.json",
        "cross_check_result.json",
        "pipeline_state.json",
        "validation_result.json",
        # 兼容别名
        "plan_summary.json",
    ]

    if file_type == "contract":
        filenames = contract_filenames
        # 合同删除同时清理 deliverables 目录（重置全部）
        json_store.delete_dir(run_id, "deliverables")
    else:
        # plan / meeting_minutes 等仅清计划相关缓存
        filenames = plan_filenames

    for filename in filenames:
        json_store.delete_file(run_id, filename)


def _rewrite_type_parsed_json(run_id: str, file_type: str):
    """删除文件后，按剩余同类型文件重新合并 *_parsed.json。

    - 若该类型已无剩余文件：删除 {file_type}_parsed.json
    - 若仍有同类型文件：重新拼接全部剩余文件文本，重写 {file_type}_parsed.json，
      保留 source_files 清单，full_text 为合并文本。
    """
    parsed_files = _load_parsed_files(run_id)
    same_type_files = [pf for pf in parsed_files if pf.get("file_type") == file_type]
    target_filename = f"{file_type}_parsed.json"

    if not same_type_files:
        # 该类型已无剩余文件，删除兼容文件
        json_store.delete_file(run_id, target_filename)
        return

    merged_text_parts = []
    for pf in same_type_files:
        merged_text_parts.append(f"===== 文件: {pf.get('filename', '')} =====\n{pf.get('full_text', '')}")
    merged_full_text = "\n\n".join(merged_text_parts)

    latest = same_type_files[-1]
    # 复用 parsed_files 中的 parse_result 摘要，剥离 full_text 避免覆盖
    latest_parse_result = latest.get("parse_result", {}) or {}
    parse_result_clean = {k: v for k, v in latest_parse_result.items() if k != "full_text"}

    merged_payload = {
        "filename": latest.get("filename", ""),
        "file_type": file_type,
        "requested_file_type": latest.get("requested_file_type", file_type),
        "filepath": latest.get("filepath", ""),
        "parsed_at": datetime.now().isoformat(),
        "source_files": [
            {"filename": pf.get("filename", ""), "parsed_at": pf.get("parsed_at", "")}
            for pf in same_type_files
        ],
        **parse_result_clean,
        "full_text": merged_full_text,
    }
    json_store.write(run_id, target_filename, merged_payload)


def _try_remove_upload_file(run_id: str, filepath: str):
    """尝试删除原始上传文件，失败时静默忽略（业务记录已清理即可）"""
    if not filepath:
        return
    try:
        fp = os.path.abspath(filepath)
        if os.path.exists(fp) and os.path.isfile(fp):
            os.remove(fp)
    except Exception:
        # 无法安全定位或删除原始文件时，忽略；业务记录已清理
        pass


class DeleteFileRequest(BaseModel):
    filename: str
    file_type: Optional[str] = None
    parsed_at: Optional[str] = None


@router.delete("/runs/{run_id}/files")
async def delete_uploaded_file(run_id: str, payload: DeleteFileRequest):
    """删除已上传文件，并同步清理业务记录与解析记录。

    请求参数：
    - filename: 必填，要删除的文件名
    - file_type: 可选，用于区分同名文件或同类型多文件
    - parsed_at: 可选，用于精确匹配某次上传记录

    删除时同步更新：
    - meta.json.uploaded_files / file_records / file_types
    - parsed_files.json
    - 对应类型的 *_parsed.json（重新合并或删除）
    - 下游所有旧结果（识别、交叉核验、任务列表、交付成果等）
    - 原始上传文件（若可安全定位）
    """
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    filename = payload.filename
    if not filename:
        raise HTTPException(status_code=400, detail="filename 为必填参数")

    # 1. 从 parsed_files.json 中匹配并删除目标记录
    # 匹配语义（parsed_at 仅用于多候选消歧，避免误删同名同类型文件）：
    #   - parsed_at 未提供：按 filename + file_type 匹配，删除所有候选
    #   - parsed_at 显式提供 + 精确匹配命中：仅删除命中的记录
    #   - parsed_at 显式提供 + 无精确匹配 + 仅 1 个候选：容忍时间戳不一致（历史数据
    #     meta.file_records.parsed_at 与 parsed_files.parsed_at 可能差微秒），删除该候选
    #   - parsed_at 显式提供 + 无精确匹配 + 多个候选：404，无法确定删除哪一个
    #     （例如 parsed_at=2099-01-01T00:00:00 这种不存在的时间戳，不应误删多个真实记录）
    parsed_files = _load_parsed_files(run_id)

    def _base_match(record: dict) -> bool:
        if record.get("filename") != filename:
            return False
        if payload.file_type and record.get("file_type") != payload.file_type:
            return False
        return True

    candidate_indices = [idx for idx, pf in enumerate(parsed_files) if _base_match(pf)]
    if not candidate_indices:
        raise HTTPException(status_code=404, detail=f"未找到匹配的文件记录: filename={filename}")

    if payload.parsed_at:
        exact_indices = [
            idx for idx in candidate_indices
            if parsed_files[idx].get("parsed_at") == payload.parsed_at
        ]
        if exact_indices:
            # 精确匹配命中：仅删除命中的记录
            matched_indices = set(exact_indices)
        elif len(candidate_indices) == 1:
            # 仅 1 个候选：容忍时间戳不一致（历史数据 meta 与 parsed_files 可能差微秒）
            matched_indices = set(candidate_indices)
        else:
            # 多个候选且 parsed_at 无精确匹配：禁止误删，返回 404
            raise HTTPException(
                status_code=404,
                detail=(
                    f"parsed_at 不匹配且存在 {len(candidate_indices)} 个同名同类型候选，"
                    f"无法确定删除哪一个: filename={filename}, parsed_at={payload.parsed_at}"
                ),
            )
    else:
        # parsed_at 未提供：按 filename + file_type 回退匹配
        matched_indices = set(candidate_indices)

    matched = [pf for idx, pf in enumerate(parsed_files) if idx in matched_indices]

    removed_filepaths = [pf.get("filepath", "") for pf in matched]
    removed_file_types = list({pf.get("file_type", "") for pf in matched})

    new_parsed_files = [pf for idx, pf in enumerate(parsed_files) if idx not in matched_indices]
    _save_parsed_files(run_id, new_parsed_files)

    # 2. 更新 meta.json: uploaded_files / file_records / file_types
    # 与 parsed_files 匹配语义保持一致：parsed_at 显式提供时仅精确匹配，单候选容忍时间戳不一致
    file_records = list(meta.get("file_records", []) or [])

    record_candidate_indices = [idx for idx, r in enumerate(file_records) if _base_match(r)]
    if payload.parsed_at:
        record_exact_indices = [
            idx for idx in record_candidate_indices
            if file_records[idx].get("parsed_at") == payload.parsed_at
        ]
        if record_exact_indices:
            remove_record_indices = set(record_exact_indices)
        elif len(record_candidate_indices) == 1:
            # 单候选容忍时间戳不一致
            remove_record_indices = set(record_candidate_indices)
        else:
            # 多候选无精确匹配：保持 meta 不变（parsed_files 已在上面 404 拦截，这里理论上不会到达）
            remove_record_indices = set()
    else:
        remove_record_indices = set(record_candidate_indices)
    new_file_records = [r for idx, r in enumerate(file_records) if idx not in remove_record_indices]

    # uploaded_files 基于剩余记录重新生成，避免同名/同类型文件删除时出现页面残留。
    uploaded_files = []
    seen_uploaded = set()
    for r in new_file_records:
        name = r.get("filename", "")
        if name and name not in seen_uploaded:
            uploaded_files.append(name)
            seen_uploaded.add(name)

    # file_types: 重新基于剩余 file_records 计算
    new_file_types = []
    seen = set()
    for r in new_file_records:
        ft = r.get("file_type", "")
        if ft and ft not in seen:
            new_file_types.append(ft)
            seen.add(ft)

    json_store.update_run_meta(run_id, {
        "uploaded_files": uploaded_files,
        "file_records": new_file_records,
        "file_types": new_file_types,
        "status": "uploaded" if new_file_records else "empty",
    })

    # 3. 重写或删除对应类型的 *_parsed.json
    for ft in removed_file_types:
        _rewrite_type_parsed_json(run_id, ft)

    # 4. 按被删文件类型分别清理下游旧结果
    #    - contract 删除：重置整个 run（合同是基础数据源）
    #    - plan 删除：仅清计划相关缓存，保留合同识别和任务列表
    if not removed_file_types:
        _invalidate_downstream_results(run_id, "contract")
    else:
        for ft in removed_file_types:
            _invalidate_downstream_results(run_id, ft)

    # 5. 尝试删除原始上传文件
    for fp in removed_filepaths:
        _try_remove_upload_file(run_id, fp)

    return {
        "success": True,
        "run_id": run_id,
        "deleted_filename": filename,
        "deleted_count": len(matched),
        "remaining_files": len(new_parsed_files),
        "remaining_file_types": new_file_types,
        "message": f"已删除文件 {filename}（共 {len(matched)} 条记录），下游旧结果已清理",
    }


@router.post("/docx")
async def upload_docx(
    file: UploadFile = File(...),
    file_type: str = Form(default="contract"),  # contract / plan / meeting_minutes
    run_id: Optional[str] = Form(default=None),
):
    """上传 Word 文档并解析

    Args:
        file: 上传的 .docx 文件
        file_type: 文件类型 (contract=合同, plan=年度服务计划, meeting_minutes=启动会纪要)
    """
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="只支持 .docx 或 .doc 文件")

    if file_type not in {"contract", "plan", "meeting_minutes"}:
        raise HTTPException(status_code=400, detail="无效的文件类型")

    # 第一次上传创建 run；后续上传复用当前 run，确保合同和计划在同一实例内。
    existing_meta = json_store.get_run_meta(run_id) if run_id else None
    if run_id and not existing_meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")
    if not run_id:
        run_id = json_store.create_run(run_name=file.filename)
        existing_meta = json_store.get_run_meta(run_id) or {}

    # 保存文件
    content = await file.read()
    filepath = docx_parser.save_upload(content, file.filename, run_id)

    # 解析文件
    try:
        parse_result = docx_parser.parse(filepath)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

    # 提取完整文本（段落拼接）
    full_text = "\n".join(parse_result.get("paragraphs", []))
    # 表格内容也拼接
    for table in parse_result.get("tables", []):
        for row in table:
            full_text += "\n" + "\t".join(row)

    detected_file_type, type_warning = _infer_file_type(file.filename, full_text, file_type)
    _invalidate_downstream_results(run_id, detected_file_type)

    # 统一时间戳：parsed_files.json / *_parsed.json / meta.file_records 共用同一个 parsed_at
    # 避免三次 datetime.now() 产生不同值导致 DELETE 接口按 parsed_at 匹配时失败（404 或 deleted_count=0）
    upload_parsed_at = datetime.now().isoformat()

    # 新增本文件到聚合清单 parsed_files.json（保留所有上传文件，不去重）
    parsed_files = _load_parsed_files(run_id)
    parsed_files.append({
        "filename": file.filename,
        "file_type": detected_file_type,
        "requested_file_type": file_type,
        "filepath": filepath,
        "parsed_at": upload_parsed_at,
        "full_text": full_text,
        "parse_result": {
            "paragraph_count": parse_result.get("paragraph_count", 0),
            "table_count": parse_result.get("table_count", 0),
            "char_count": parse_result.get("char_count", 0),
        },
    })
    _save_parsed_files(run_id, parsed_files)

    # 兼容文件：contract_parsed.json / plan_parsed.json 合并同类型所有文件文本
    # 识别服务仍读取这两个文件，这里把同类型所有文件的文本拼接写入
    # 注意：parse_result 可能含 full_text 字段，必须先剥离再显式写入 merged_full_text
    # 避免 **parse_result 在最后展开时把合并文本覆盖为单个文件文本
    same_type_files = [pf for pf in parsed_files if pf.get("file_type") == detected_file_type]
    if same_type_files:
        merged_text_parts = []
        for pf in same_type_files:
            merged_text_parts.append(f"===== 文件: {pf.get('filename', '')} =====\n{pf.get('full_text', '')}")
        merged_full_text = "\n\n".join(merged_text_parts)
        # 兼容结构：保留最新 parse_result 结构 + 合并文本 + source_files 清单
        latest = same_type_files[-1]
        # 剥离 parse_result 中的 full_text，确保后续不会覆盖合并文本
        parse_result_clean = {k: v for k, v in parse_result.items() if k != "full_text"}
        merged_payload = {
            "filename": latest.get("filename", file.filename),
            "file_type": detected_file_type,
            "requested_file_type": file_type,
            "filepath": latest.get("filepath", filepath),
            "parsed_at": upload_parsed_at,
            "source_files": [
                {"filename": pf.get("filename", ""), "parsed_at": pf.get("parsed_at", "")}
                for pf in same_type_files
            ],
            **parse_result_clean,
            # 显式在最后写入 full_text，保证最终值是合并文本
            "full_text": merged_full_text,
        }
        json_store.write(run_id, f"{detected_file_type}_parsed.json", merged_payload)

    # 真实合同模式：不初始化 Mock 数据，等待合同识别服务生成真实结果
    # 仅在 mock 全局模式下才自动初始化预设数据（用户显式 use_mock 不走这里）
    if settings.is_mock_mode and not file_type:
        json_store.init_from_mock(run_id)

    # 更新 run 元数据（file_records 不再按 file_type 去重，保留所有上传记录）
    uploaded_files = _merge_meta_list(existing_meta, "uploaded_files", file.filename)
    file_types = _merge_meta_list(existing_meta, "file_types", detected_file_type)
    file_records = list(existing_meta.get("file_records", []) or [])
    # 不再删除旧的同类型记录，直接追加
    file_records.append({
        "filename": file.filename,
        "file_type": detected_file_type,
        "requested_file_type": file_type,
        "parsed_at": upload_parsed_at,
    })

    json_store.update_run_meta(run_id, {
        "status": "uploaded",
        "uploaded_files": uploaded_files,
        "file_types": file_types,
        "file_records": file_records,
        "run_mode": settings.run_mode_label,
        "parser_mode": settings.parser_mode,
    })

    return {
        "success": True,
        "run_id": run_id,
        "filename": file.filename,
        "file_type": detected_file_type,
        "requested_file_type": file_type,
        "file_type_corrected": detected_file_type != file_type,
        "warning": type_warning,
        "parse_result": {
            "paragraph_count": parse_result["paragraph_count"],
            "table_count": parse_result["table_count"],
            "char_count": parse_result["char_count"],
        },
        "run_mode": settings.run_mode_label,
        "parser_mode": settings.parser_mode,
        "message": "文件上传解析成功，已创建运行实例",
    }


@router.post("/create-run")
async def create_run(
    run_name: str = Form(default=""),
    use_mock: bool = Form(default=False),
):
    """创建新的运行实例

    默认不使用 mock 数据，需要显式指定 use_mock=true 才初始化演示数据
    """
    run_id = json_store.create_run(run_name=run_name)

    if use_mock:
        json_store.init_from_mock(run_id)
        json_store.update_run_meta(run_id, {
            "status": "mock_initialized",
            "mode": "mock",
        })
        return {
            "success": True,
            "run_id": run_id,
            "mode": "mock",
            "run_mode": "Mock演示模式",
            "message": "运行实例已创建并初始化 Mock 演示数据",
        }
    else:
        json_store.update_run_meta(run_id, {
            "status": "empty",
            "mode": settings.parser_mode,
            "run_mode": settings.run_mode_label,
        })
        return {
            "success": True,
            "run_id": run_id,
            "mode": settings.parser_mode,
            "run_mode": settings.run_mode_label,
            "message": "运行实例已创建（空数据，等待上传文件）",
        }


@router.get("/runs")
async def list_runs():
    """列出所有运行实例"""
    runs = json_store.list_runs()
    return {
        "success": True,
        "total": len(runs),
        "runs": runs,
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """获取运行实例详情"""
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")
    return {
        "success": True,
        "run": meta,
    }
