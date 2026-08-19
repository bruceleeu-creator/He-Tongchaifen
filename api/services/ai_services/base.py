"""
AI 服务基类
提供 mock / rule / llm 三层模式
- mock: 预设样例数据（仅演示）
- rule: 规则解析，无需 API Key
- llm: 真实 LLM 调用
- 规则保底+后台重试：先用规则解析快速出结果，再尝试 LLM 增强
"""
import json
from pathlib import Path
from typing import Any, Optional

from config import settings
from services.llm_client import llm_client
from services.ai_config_store import ai_config_store


class AIServiceBase:
    """AI 服务基类"""

    service_name: str = "base"
    mock_filename: str = ""
    prompt_name: str = ""

    def __init__(self):
        self.mock_mode = settings.is_mock_mode
        # llm_available 和 rule_mode 改为动态属性，确保运行时配置 API Key 后立即生效

    @property
    def llm_available(self) -> bool:
        """LLM 是否可用（动态读取，确保运行时配置后立即生效）"""
        return ai_config_store.is_available

    @property
    def rule_mode(self) -> bool:
        """是否为规则解析模式（动态读取）"""
        return settings.is_rule_mode

    @property
    def mode(self) -> str:
        """当前运行模式"""
        if self.mock_mode:
            return "mock"
        if self.llm_available and not self.rule_mode:
            return "real"
        if self.llm_available:
            return "llm_enhanced"
        return "rule"

    @property
    def mode_label(self) -> str:
        """运行模式中文标签"""
        m = self.mode
        if m == "mock":
            return "Mock演示模式"
        if m == "real":
            return "真实解析模式(LLM)"
        if m == "llm_enhanced":
            return "真实解析模式(规则+LLM增强)"
        return "真实解析模式(规则解析)"

    @property
    def data_source(self) -> str:
        """数据来源"""
        m = self.mode
        if m == "mock":
            return "样例数据"
        return "合同原文"

    def get_mock_data(self) -> Optional[dict]:
        """获取 mock 数据"""
        if not self.mock_filename:
            return None
        mock_path = settings.get_mock_data_path(self.mock_filename)
        if not mock_path.exists():
            return None
        try:
            with open(mock_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    @staticmethod
    def unwrap_contract_data(contract_data: Any) -> dict:
        """解包 contract_result 中的 data 字段

        contract_result.json 保存了完整的服务结果：
        { "success": True, "mode": "...", "data": { "basic_info": [...], ... } }
        本方法提取内部 data 字段供下游服务使用。
        """
        if isinstance(contract_data, dict):
            if "data" in contract_data and isinstance(contract_data["data"], dict):
                inner = contract_data["data"]
                # 确认内层确实包含合同解析字段（而非另一个服务结果）
                contract_keys = {
                    "basic_info", "service_scope", "contract_summary",
                    "pending_items", "deliverables", "client_responsibilities",
                    "our_responsibilities", "delay_rules", "raw_text",
                }
                if contract_keys & set(inner.keys()):
                    return inner
        return contract_data if isinstance(contract_data, dict) else {}

    def get_prompt_template(self) -> str:
        """获取提示词模板"""
        prompt_path = settings.get_prompt_path(self.prompt_name)
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def render_prompt(self, variables: dict) -> str:
        """渲染提示词模板，替换 {{变量}} 占位符"""
        template = self.get_prompt_template()
        if not template:
            return ""
        result = template
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
        return result

    async def execute_mock(self, **kwargs) -> dict:
        """mock 模式执行"""
        mock_data = self.get_mock_data()
        if mock_data is not None:
            return {
                "success": True,
                "mode": "mock",
                "mode_label": "Mock演示模式",
                "data_source": "样例数据",
                "service": self.service_name,
                "data": mock_data,
            }
        return {
            "success": False,
            "mode": "mock",
            "service": self.service_name,
            "message": f"Mock 数据文件不存在: {self.mock_filename}",
        }

    async def execute_rule(self, **kwargs) -> dict:
        """规则解析模式执行（子类必须覆盖）"""
        return {
            "success": False,
            "mode": "rule",
            "service": self.service_name,
            "message": "规则解析未实现",
        }

    async def execute_real(self, **kwargs) -> dict:
        """LLM 模式执行（子类可覆盖）"""
        return await self.execute_mock(**kwargs)

    async def run(self, **kwargs) -> dict:
        """执行服务（统一入口）

        优先级: mock模式 → mock数据
                rule模式 → execute_rule
                llm_enhanced模式 → execute_rule + execute_real增强
                real模式 → execute_real
        """
        if self.mock_mode:
            return await self.execute_mock(**kwargs)

        if self.mode == "real":
            return await self.execute_real(**kwargs)

        if self.mode == "llm_enhanced":
            # 先规则解析，再 LLM 增强
            rule_result = await self.execute_rule(**kwargs)
            if rule_result.get("success"):
                # 尝试 LLM 增强
                try:
                    llm_result = await self.execute_real(**kwargs)
                    # 只有 LLM 真正成功（mode=real）才使用 LLM 结果
                    # execute_real 内部 LLM 失败时会回退到 execute_rule，返回 mode=rule
                    if llm_result.get("success") and llm_result.get("mode") == "real" and not llm_result.get("data", {}).get("error"):
                        # LLM 成功，使用 LLM 结果但标注增强模式
                        llm_result["mode"] = "llm_enhanced"
                        llm_result["mode_label"] = "真实解析模式(规则+LLM增强)"
                        llm_result["data_source"] = "合同原文(LLM深度解析)"
                        return llm_result
                except Exception:
                    pass
            # LLM 失败，使用规则保底结果
            return rule_result

        # rule 模式
        return await self.execute_rule(**kwargs)
