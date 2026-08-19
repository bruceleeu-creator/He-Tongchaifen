"""
待确认清单生成服务
规则解析模式：从合同识别结果提取待确认事项
"""
import json
from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


class PendingListService(AIServiceBase):
    """待确认清单生成服务"""

    service_name = "pending_list"
    mock_filename = "pending_list.json"
    prompt_name = "pending_list"

    async def execute_rule(self, contract_result: str = "", task_list: str = "", **kwargs) -> dict:
        """规则解析模式：从合同识别结果提取待确认事项"""
        try:
            contract_data = json.loads(contract_result) if isinstance(contract_result, str) else contract_result
        except (json.JSONDecodeError, TypeError):
            contract_data = {}

        # 解包 contract_result 中的 data 字段
        contract_data = self.unwrap_contract_data(contract_data)

        pending_items = contract_data.get("pending_items", [])
        summary = contract_data.get("contract_summary", {})

        # 转换为任务级待确认清单格式（使用英文 key 对齐前端）
        items = []
        for i, item in enumerate(pending_items, 1):
            pending_text = item.get("待确认事项", "") or item.get("pending_item", "")
            items.append({
                "item_id": f"pending_{i:03d}",
                "pending_item": pending_text,
                "reason": item.get("原因", "") or item.get("reason", ""),
                "related_tasks": "全部" if "日期" in pending_text or "责任人" in pending_text else "相关任务",
                "suggest_confirm_to": item.get("建议向谁确认", "") or item.get("suggest_confirm_to", ""),
                "impact_if_not_confirmed": item.get("不确认的影响", "") or item.get("impact_if_not_confirmed", ""),
                "status": "待确认",
                "confirmed_value": "",
            })

        # 如果合同识别没有 pending_items，从 summary 缺失字段补充生成
        if not items:
            items = self._generate_from_summary(summary)

        data = {
            "items": items,
            "total": len(items),
            "source": "合同识别结果",
            "generated_by": "rule_engine",
        }

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "合同原文",
            "service": self.service_name,
            "data": data,
        }

    def _generate_from_summary(self, summary: dict) -> list:
        """从合同摘要的缺失字段生成待确认事项"""
        items = []
        idx = 1

        sign_date = summary.get("合同签署日期", "待人工确认")
        if sign_date == "待人工确认" or not sign_date:
            items.append({
                "item_id": f"pending_{idx:03d}",
                "pending_item": "合同签署日期和项目启动日期",
                "reason": "合同签字页日期为空，无法确定服务起算日",
                "related_tasks": "全部",
                "suggest_confirm_to": "双方授权代表",
                "impact_if_not_confirmed": "任务排期无法准确设置，所有日期字段将为空",
                "status": "待确认",
                "confirmed_value": "",
            })
            idx += 1

        total_fee = summary.get("服务费用（总计）", "待人工确认")
        if total_fee == "待人工确认" or not total_fee:
            items.append({
                "item_id": f"pending_{idx:03d}",
                "pending_item": "合同服务费用总额确认",
                "reason": "合同金额未在原文中明确体现",
                "related_tasks": "付款节点任务",
                "suggest_confirm_to": "甲乙双方",
                "impact_if_not_confirmed": "无法设置付款提醒和费用回收跟踪",
                "status": "待确认",
                "confirmed_value": "",
            })
            idx += 1

        return items

    async def execute_real(self, task_list: str = "", contract_result: str = "", **kwargs) -> dict:
        """LLM 增强模式"""
        prompt = self.render_prompt({"任务主表": task_list, "合同识别结果": contract_result})
        if not prompt:
            return await self.execute_rule(contract_result=contract_result, task_list=task_list, **kwargs)

        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            return await self.execute_rule(contract_result=contract_result, task_list=task_list, **kwargs)

        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"合同原文(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": result,
        }
