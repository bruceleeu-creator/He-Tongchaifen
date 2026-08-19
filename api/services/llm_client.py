"""
LLM 客户端
支持 OpenAI-compatible 接口（DeepSeek / 通义千问 / 其他）
优先从动态配置存储读取参数，支持运行时切换服务商
未配置 API Key 时返回 mock=True，由上层服务决定是否回退到规则解析
"""
import json
import logging
import asyncio
import re
from typing import Any, Optional

import httpx

from config import settings
from services.ai_config_store import ai_config_store

logger = logging.getLogger(__name__)


class LLMResponse:
    """LLM 响应封装"""

    def __init__(self, content: str, mock: bool = True, model: str = "", raw: Any = None):
        self.content = content
        self.mock = mock
        self.model = model
        self.raw = raw

    @property
    def is_mock(self) -> bool:
        return self.mock

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "mock": self.mock,
            "model": self.model,
        }


class LLMClient:
    """LLM 客户端 - OpenAI-compatible，支持动态配置"""

    def __init__(self):
        # 不再在构造函数中固定参数，每次调用时从 ai_config_store 动态读取
        pass

    @property
    def is_available(self) -> bool:
        """LLM 是否可用（有 API Key）"""
        return ai_config_store.is_available

    @property
    def mode(self) -> str:
        """当前模式"""
        return "real" if self.is_available else "mock"

    @property
    def model_source(self) -> str:
        """模型来源标识"""
        return ai_config_store.model_source

    @property
    def model(self) -> str:
        """当前模型名称"""
        return ai_config_store.model

    @property
    def base_url(self) -> str:
        """当前 Base URL"""
        return ai_config_store.base_url

    async def chat(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """调用 LLM 进行对话

        如果没有配置 API Key，返回 mock 响应
        """
        if not self.is_available:
            return LLMResponse(
                content='{"mock": true, "message": "LLM API Key 未配置，上层服务应回退到规则解析"}',
                mock=True,
                model="mock",
            )

        api_key = ai_config_store.api_key
        base_url = ai_config_store.base_url
        model = ai_config_store.model
        temperature = ai_config_store.temperature
        timeout = ai_config_store.timeout

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                return LLMResponse(
                    content=content,
                    mock=False,
                    model=model,
                    raw=result,
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API HTTP 错误: {e.response.status_code} - {e.response.text}")
            return LLMResponse(
                content=f'{{"error": "HTTP {e.response.status_code}", "message": "{e.response.text[:200]}"}}',
                mock=True,
                model="error",
            )
        except Exception as e:
            logger.error(f"LLM 调用异常: {str(e)}")
            return LLMResponse(
                content=f'{{"error": "{str(e)}"}}',
                mock=True,
                model="error",
            )

    async def chat_json(self, prompt: str, system_prompt: str = "") -> dict:
        """调用 LLM 并返回 JSON 结果"""
        json_system_prompt = (
            system_prompt
            or "你是结构化数据抽取助手。必须只输出合法 JSON，不要输出 Markdown、解释文字或代码块。"
        )
        response = await self.chat(prompt, json_system_prompt)
        if response.is_mock:
            try:
                return json.loads(response.content)
            except json.JSONDecodeError:
                return {"mock": True, "raw": response.content[:500]}

        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            if "```json" in content:
                start = content.index("```json") + 7
                end = content.rindex("```")
                return json.loads(content[start:end])
            elif "```" in content:
                start = content.index("```") + 3
                end = content.rindex("```")
                return json.loads(content[start:end])
            # 尝试提取首个 JSON 对象或数组
            match = re.search(r"(\{.*\}|\[.*\])", content, flags=re.S)
            if match:
                return json.loads(match.group(1))
            return {"error": "LLM 返回内容无法解析为 JSON", "raw": response.content[:500]}

    async def test_connection(self) -> dict:
        """测试 LLM 连接是否正常

        发送一条简短消息验证 API Key 和网络连通性
        """
        if not self.is_available:
            return {
                "success": False,
                "message": "API Key 未配置",
                "model": "",
            }

        try:
            response = await self.chat(
                prompt="请回复 'OK'",
                system_prompt="你是一个测试助手，只需回复 OK。",
            )
            if not response.is_mock:
                return {
                    "success": True,
                    "message": f"连接成功，模型: {self.model}",
                    "model": self.model,
                    "response_preview": response.content[:100],
                }
            else:
                return {
                    "success": False,
                    "message": "API Key 无效或网络不通",
                    "model": "error",
                    "response_preview": response.content[:200],
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接测试失败: {str(e)}",
                "model": "error",
            }


# 全局实例
llm_client = LLMClient()
