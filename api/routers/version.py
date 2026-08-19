"""
版本管理路由：保存、列表、获取、回退
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from models.version import VersionSaveRequest
from services.json_store import json_store

router = APIRouter(prefix="/api/versions", tags=["版本管理"])


@router.post("/{run_id}/save")
async def save_version(run_id: str, request: VersionSaveRequest):
    """保存当前任务列表为版本快照"""
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    # 获取当前任务列表
    task_data = json_store.read(run_id, "task_list.json")
    if not task_data:
        raise HTTPException(status_code=404, detail="任务列表不存在，无法保存版本")

    # 读取版本列表
    versions = json_store.read(run_id, "versions.json", {"versions": []})
    version_list = versions.get("versions", [])

    # 创建新版本
    version_id = f"ver_{uuid.uuid4().hex[:12]}"
    version_number = len(version_list) + 1

    version_info = {
        "version_id": version_id,
        "run_id": run_id,
        "version_number": version_number,
        "description": request.description or f"版本 {version_number}",
        "task_count": len(task_data.get("tasks", [])),
        "created_at": datetime.now().isoformat(),
        "created_by": "system",
        "snapshot": task_data,
    }

    version_list.append(version_info)
    versions["versions"] = version_list
    versions["updated_at"] = datetime.now().isoformat()
    json_store.write(run_id, "versions.json", versions)

    return {
        "success": True,
        "run_id": run_id,
        "version_id": version_id,
        "version_number": version_number,
        "task_count": version_info["task_count"],
        "message": f"版本 {version_number} 已保存",
    }


@router.get("/{run_id}")
async def list_versions(run_id: str):
    """获取版本列表"""
    versions = json_store.read(run_id, "versions.json")
    if not versions:
        return {"success": True, "run_id": run_id, "total": 0, "versions": []}

    version_list = versions.get("versions", [])
    # 返回时不包含 snapshot
    summary_list = [
        {k: v for k, v in ver.items() if k != "snapshot"}
        for ver in version_list
    ]
    return {
        "success": True,
        "run_id": run_id,
        "total": len(summary_list),
        "versions": summary_list,
    }


@router.get("/{run_id}/{version_id}")
async def get_version(run_id: str, version_id: str):
    """获取版本详情（含任务快照）"""
    versions = json_store.read(run_id, "versions.json")
    if not versions:
        raise HTTPException(status_code=404, detail="版本列表不存在")

    version_list = versions.get("versions", [])
    for ver in version_list:
        if ver.get("version_id") == version_id:
            return {"success": True, "run_id": run_id, "data": ver}

    raise HTTPException(status_code=404, detail=f"版本不存在: {version_id}")


@router.post("/{run_id}/{version_id}/rollback")
async def rollback_version(run_id: str, version_id: str):
    """回退到指定版本"""
    versions = json_store.read(run_id, "versions.json")
    if not versions:
        raise HTTPException(status_code=404, detail="版本列表不存在")

    version_list = versions.get("versions", [])
    target_version = None
    for ver in version_list:
        if ver.get("version_id") == version_id:
            target_version = ver
            break

    if not target_version:
        raise HTTPException(status_code=404, detail=f"版本不存在: {version_id}")

    # 用快照覆盖当前任务列表
    snapshot = target_version.get("snapshot")
    if not snapshot:
        raise HTTPException(status_code=500, detail="版本快照为空，无法回退")

    json_store.write(run_id, "task_list.json", snapshot)

    return {
        "success": True,
        "run_id": run_id,
        "version_id": version_id,
        "version_number": target_version.get("version_number", 0),
        "task_count": target_version.get("task_count", 0),
        "message": f"已回退到版本 {target_version.get('version_number', '?')}",
    }


@router.delete("/{run_id}/{version_id}")
async def delete_version(run_id: str, version_id: str):
    """删除指定版本快照

    从 versions.json 中真实移除该版本记录，保留文件本身便于前端显示空状态。
    """
    # 校验 run 是否存在
    meta = json_store.get_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"运行实例不存在: {run_id}")

    versions = json_store.read(run_id, "versions.json")
    if not versions:
        raise HTTPException(status_code=404, detail="版本列表不存在")

    version_list = versions.get("versions", [])
    original_total = len(version_list)

    # 找到对应 version_id
    target_version = None
    for ver in version_list:
        if ver.get("version_id") == version_id:
            target_version = ver
            break

    if not target_version:
        raise HTTPException(status_code=404, detail=f"版本不存在: {version_id}")

    # 从列表中移除该版本
    new_list = [ver for ver in version_list if ver.get("version_id") != version_id]
    versions["versions"] = new_list
    versions["updated_at"] = datetime.now().isoformat()

    # 重新编号 version_number，保持连续（不影响 version_id）
    for idx, ver in enumerate(new_list, start=1):
        ver["version_number"] = idx

    # 写回 versions.json（即使删到 0 条也保留文件，便于前端显示空状态）
    json_store.write(run_id, "versions.json", versions)

    return {
        "success": True,
        "run_id": run_id,
        "version_id": version_id,
        "remaining_total": len(new_list),
        "message": f"版本 {target_version.get('version_number', '?')} 已删除"
        + (f"，剩余 {len(new_list)} 条" if new_list else "，版本列表已清空"),
    }
