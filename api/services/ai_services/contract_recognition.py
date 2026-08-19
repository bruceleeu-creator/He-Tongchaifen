"""
合同识别服务
规则解析优先 + LLM 增强 + 合同识别摘要生成
"""
import json
from services.ai_services.base import AIServiceBase
from services.contract_parser import contract_parser
from services.llm_client import llm_client


class ContractRecognitionService(AIServiceBase):
    """合同识别服务"""

    service_name = "contract_recognition"
    mock_filename = "contract_result.json"
    prompt_name = "contract_recognition"

    async def execute_rule(self, contract_text: str = "", **kwargs) -> dict:
        """规则解析模式：使用正则/关键词提取合同核心字段"""
        if not contract_text or not contract_text.strip():
            return {
                "success": False,
                "mode": "rule",
                "mode_label": "真实解析模式(规则解析)",
                "data_source": "合同原文",
                "service": self.service_name,
                "message": "合同文本为空，无法解析",
            }

        # 从 kwargs 获取文件名
        filename = kwargs.get("filename", "")

        # 执行规则解析
        result = contract_parser.parse(contract_text, filename)

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "合同原文",
            "service": self.service_name,
            "data": result,
        }

    async def execute_real(self, contract_text: str = "", **kwargs) -> dict:
        """LLM 增强模式：调用 LLM 进行深度合同识别"""
        prompt = self.render_prompt({"服务合同文本": contract_text})
        if not prompt:
            # 如果没有提示词模板，回退到规则解析
            return await self.execute_rule(contract_text=contract_text, **kwargs)

        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            # LLM 失败，回退到规则解析
            return await self.execute_rule(contract_text=contract_text, **kwargs)

        # 标注模型来源
        result["_model_source"] = llm_client.model_source

        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"合同原文(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": result,
        }


# 全局实例
contract_recognition_service = ContractRecognitionService()
