"""
AI 配置路由
提供 AI 服务商切换、API Key 管理、连接测试接口
前端侧边栏面板通过此路由动态配置 LLM 参数
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.ai_config_store import ai_config_store, PRESETS
from services.llm_client import llm_client
from config import settings

router = APIRouter(prefix="/api/ai-config", tags=["AI 配置"])


class UpdateConfigRequest(BaseModel):
    """更新 AI 配置请求"""
    preset: Optional[str] = ""       # deepseek / qwen / openai
    api_key: Optional[str] = ""      # 空字符串表示不更新
    base_url: Optional[str] = ""     # 手动覆盖 Base URL
    model: Optional[str] = ""        # 手动覆盖模型名称
    temperature: Optional[float] = None
    timeout: Optional[int] = None


@router.get("")
async def get_config():
    """获取当前 AI 配置

    返回脱敏后的配置信息，API Key 只显示前后4位
    """
    config = ai_config_store.get_config()
    return {
        "success": True,
        "config": config,
        "presets": PRESETS,
        "llm_available": ai_config_store.is_available,
        "mode": settings.parser_mode,
        "mode_label": settings.run_mode_label,
        "model_source": llm_client.model_source,
    }


@router.post("/update")
async def update_config(req: UpdateConfigRequest):
    """更新 AI 配置

    支持切换服务商预设和更新 API Key，无需重启后端
    """
    if req.preset and req.preset not in PRESETS:
        raise HTTPException(status_code=400, detail=f"无效的预设: {req.preset}，可选: {', '.join(PRESETS.keys())}")

    config = ai_config_store.update_config(
        preset=req.preset or "",
        api_key=req.api_key or "",
        base_url=req.base_url or "",
        model=req.model or "",
        temperature=req.temperature,
        timeout=req.timeout,
    )

    return {
        "success": True,
        "config": config,
        "llm_available": ai_config_store.is_available,
        "message": "AI 配置已更新" + ("，LLM 已就绪" if ai_config_store.is_available else "，API Key 未配置（将使用规则解析模式）"),
    }


@router.post("/test")
async def test_connection():
    """测试 LLM 连接

    发送一条简短消息验证 API Key 是否有效、网络是否通畅
    """
    if not ai_config_store.is_available:
        return {
            "success": False,
            "message": "API Key 未配置，无法测试连接",
            "llm_available": False,
        }

    result = await llm_client.test_connection()
    return {
        "success": result["success"],
        "message": result["message"],
        "model": result.get("model", ""),
        "response_preview": result.get("response_preview", ""),
        "llm_available": ai_config_store.is_available,
    }


@router.get("/presets")
async def get_presets():
    """获取所有服务商预设"""
    return {
        "success": True,
        "presets": PRESETS,
        "current_preset": ai_config_store.get_config().get("preset", ""),
    }
