"""
合同与计划交叉核验服务
"""
from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


class CrossValidationService(AIServiceBase):
    """交叉核验服务"""

    service_name = "cross_validation"
    mock_filename = "cross_check_result.json"
    prompt_name = "cross_validation"

    async def execute_rule(
        self,
        contract_result: str = "",
        plan_result: str = "",
        **kwargs,
    ) -> dict:
        """规则解析模式：基础交叉核验"""
        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "合同+计划",
            "service": self.service_name,
            "data": {
                "cross_check_items": [],
                "total": 0,
                "message": "规则解析模式下交叉核验暂未实现，请在上传计划后使用 LLM 增强模式",
            },
        }

    async def execute_real(
        self,
        contract_result: str = "",
        plan_result: str = "",
        **kwargs,
    ) -> dict:
        """真实模式：调用 LLM 进行交叉核验"""
        prompt = self.render_prompt({
            "合同识别结果": contract_result,
            "年度服务计划识别结果": plan_result,
        })
        if not prompt:
            return await self.execute_rule(contract_result=contract_result, plan_result=plan_result, **kwargs)
        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            return await self.execute_rule(contract_result=contract_result, plan_result=plan_result, **kwargs)
        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"合同+计划(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": result,
        }


# 全局实例
cross_validation_service = CrossValidationService()
