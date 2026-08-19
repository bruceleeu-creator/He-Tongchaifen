"""
风险提示生成服务
规则解析模式：从合同内容生成风险提示
"""
import json
from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


class RiskWarningService(AIServiceBase):
    """风险提示生成服务"""

    service_name = "risk_warning"
    mock_filename = "risk_list.json"
    prompt_name = "risk_warning"

    async def execute_rule(
        self,
        contract_result: str = "",
        plan_result: str = "",
        task_list: str = "",
        **kwargs,
    ) -> dict:
        """规则解析模式：从合同内容生成风险提示"""
        try:
            contract_data = json.loads(contract_result) if isinstance(contract_result, str) else contract_result
        except (json.JSONDecodeError, TypeError):
            contract_data = {}

        # 解包 contract_result 中的 data 字段
        contract_data = self.unwrap_contract_data(contract_data)

        summary = contract_data.get("contract_summary", {})
        pending_items = contract_data.get("pending_items", [])

        risks = []
        rid = 1

        # 1. 合同签署日期缺失风险
        sign_date = summary.get("合同签署日期", "待人工确认")
        if sign_date == "待人工确认" or not sign_date:
            risks.append({
                "risk_id": f"risk_{rid:03d}",
                "risk_point": "合同签署日期缺失",
                "risk_source": "合同签字页日期为空，服务起算时间不明确",
                "impact_scope": "全部任务排期",
                "severity": "高",
                "suggestion": "尽快与双方授权代表确认签署日期和项目启动日期",
                "basis": "合同签字页",
            })
            rid += 1

        # 2. 顺延暂停规则缺失风险
        has_delay_clause = "顺延" in str(contract_data.get("raw_text", ""))
        if not has_delay_clause:
            risks.append({
                "risk_id": f"risk_{rid:03d}",
                "risk_point": "顺延规则缺失",
                "risk_source": "合同未明确客户资料延迟后的顺延机制，可能导致我方承担延期责任",
                "impact_scope": "客户资料任务及相关后续任务",
                "severity": "高",
                "suggestion": "在启动会上与甲方确认顺延规则，形成书面补充协议",
                "basis": "合同未约定",
            })
            rid += 1

        # 3. 客户反馈超期风险
        risks.append({
            "risk_id": f"risk_{rid:03d}",
            "risk_point": "客户反馈超期",
            "risk_source": "合同要求客户10个工作日内给予书面反馈，逾期将影响后续任务推进",
            "impact_scope": "方案设计类任务",
            "severity": "中",
            "suggestion": "建立反馈跟踪机制，逾期3个工作日后发送催办通知",
            "basis": "合同第四条 甲方责任四",
        })
        rid += 1

        # 4. 交付确认超期风险
        risks.append({
            "risk_id": f"risk_{rid:03d}",
            "risk_point": "交付确认超期",
            "risk_source": "合同要求5个工作日内签署交付确认单，逾期可能导致服务成果无法及时验收",
            "impact_scope": "交付验收任务",
            "severity": "中",
            "suggestion": "发起确认后自动设置5个工作日倒计时，逾期转待客户状态",
            "basis": "合同第六条 一、交付物验收",
        })
        rid += 1

        # 5. 付款节点风险
        total_fee = summary.get("服务费用（总计）", "")
        if total_fee and total_fee != "待人工确认":
            risks.append({
                "risk_id": f"risk_{rid:03d}",
                "risk_point": "付款节点管理",
                "risk_source": f"合同费用{total_fee}，分首期款和尾期款两笔，需确保按时到账",
                "impact_scope": "交付验收任务",
                "severity": "中",
                "suggestion": "设置付款提醒，首期款在合同签订后3个工作日内跟进，尾期款在第七个月内跟进",
                "basis": "合同第五条 服务费用及付款方式",
            })
            rid += 1

        # 6. 响应时效风险
        response_time = summary.get("响应时效", "")
        if response_time and response_time != "待人工确认":
            risks.append({
                "risk_id": f"risk_{rid:03d}",
                "risk_point": "响应时效风险",
                "risk_source": f"合同要求{response_time}内回复紧急问题，需建立响应记录台账确保时效",
                "impact_scope": "陪跑服务任务",
                "severity": "中",
                "suggestion": "建立紧急问题响应记录台账，自动跟踪响应时间",
                "basis": "合同第三条 四、响应时效",
            })
            rid += 1

        # 7. 季度报告遗漏风险
        risks.append({
            "risk_id": f"risk_{rid:03d}",
            "risk_point": "季度报告遗漏",
            "risk_source": "合同要求每季度提交《服务进度与效果报告》，遗漏将影响服务价值证明",
            "impact_scope": "陪跑服务任务",
            "severity": "低",
            "suggestion": "设置季度报告提醒，每季度末自动生成报告模板",
            "basis": "合同第四条 乙方责任三",
        })
        rid += 1

        # 8. 驻场安排风险
        onsite = summary.get("驻场安排", "")
        if onsite and onsite != "待人工确认":
            risks.append({
                "risk_id": f"risk_{rid:03d}",
                "risk_point": "驻场安排风险",
                "risk_source": f"合同要求{onsite}，需提前与客户确认季度驻场时间",
                "impact_scope": "陪跑服务任务",
                "severity": "低",
                "suggestion": "每季度初与客户确认驻场时间，避免临时调整",
                "basis": "合同第三条 三、驻场安排",
            })

        data = {
            "risks": risks,
            "total": len(risks),
            "source": "合同原文",
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

    async def execute_real(
        self,
        contract_result: str = "",
        plan_result: str = "",
        task_list: str = "",
        **kwargs,
    ) -> dict:
        """LLM 增强模式"""
        prompt = self.render_prompt({
            "合同识别结果": contract_result,
            "年度服务计划识别结果": plan_result,
            "任务主表": task_list,
        })
        if not prompt:
            return await self.execute_rule(
                contract_result=contract_result,
                plan_result=plan_result,
                task_list=task_list,
                **kwargs,
            )

        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            return await self.execute_rule(
                contract_result=contract_result,
                plan_result=plan_result,
                task_list=task_list,
                **kwargs,
            )

        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"合同原文(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": result,
        }
