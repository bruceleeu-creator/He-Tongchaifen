"""
动态澄清表单生成服务
基于合同识别摘要动态生成追问问题，不套用固定模板
"""
import json
from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


class ClarificationFormService(AIServiceBase):
    """澄清表单生成服务"""

    service_name = "clarification_form"
    mock_filename = "clarification_form.json"
    prompt_name = "clarification_form"

    async def execute_rule(
        self,
        contract_result: str = "",
        task_list: str = "",
        **kwargs,
    ) -> dict:
        """规则解析模式：根据合同识别结果动态生成追问问题"""
        # 解析合同识别结果
        try:
            contract_data = json.loads(contract_result) if isinstance(contract_result, str) else contract_result
        except (json.JSONDecodeError, TypeError):
            contract_data = {}

        # 解包 contract_result 中的 data 字段
        contract_data = self.unwrap_contract_data(contract_data)

        summary = contract_data.get("contract_summary", {})
        pending_items = contract_data.get("pending_items", [])
        service_scope = contract_data.get("service_scope", [])

        # 动态生成问题
        questions = self._generate_dynamic_questions(summary, pending_items, service_scope)

        form_data = {
            "items": questions,
            "total": len(questions),
            "source": "contract_summary",
            "generated_by": "rule_engine",
        }

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "合同识别摘要",
            "service": self.service_name,
            "data": form_data,
        }

    async def execute_real(
        self,
        contract_result: str = "",
        task_list: str = "",
        **kwargs,
    ) -> dict:
        """LLM 增强模式：调用 LLM 生成更精准的追问问题

        需求4补充：LLM 返回后做后处理，强制将所有"时间节点"相关问题合并为 1 个综合问题，
        避免 LLM 不严格遵守提示词约束而把时间问题拆成多个。
        同时为缺失 suggested_answer 的问题补充建议值。
        """
        prompt = self.render_prompt({
            "合同识别结果": contract_result,
            "任务主表": task_list,
        })
        if not prompt:
            return await self.execute_rule(contract_result=contract_result, task_list=task_list, **kwargs)

        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            return await self.execute_rule(contract_result=contract_result, task_list=task_list, **kwargs)

        # 需求4后处理：强制合并时间相关问题 + 补充建议值
        if isinstance(result, dict) and isinstance(result.get("items"), list):
            result["items"] = self._post_process_llm_questions(result["items"])
            result["total"] = len(result["items"])

        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"合同识别摘要(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": result,
        }

    # 时间节点相关关键词（用于识别 LLM 输出中的时间类问题）
    _TIME_KEYWORDS = (
        "起算日", "起算", "服务期限", "服务起止", "项目周期",
        "阶段节点", "阶段评审", "评审节奏", "季度报告", "季度评审",
        "驻场", "现场服务", "现场", "驻场日期", "驻场时间",
        "阶段成果提交", "成果提交时间", "提交时间", "交付时间",
        "起止时间", "开始时间", "结束时间", "完成时间", "时间节点",
        "何时", "时间安排", "进度安排", "时间表", "排期",
    )

    def _is_time_related(self, item: dict) -> bool:
        """判断问题是否为时间节点相关"""
        text = " ".join([
            str(item.get("pending_item", "")),
            str(item.get("reason", "")),
            str(item.get("related_tasks", "")),
        ])
        return any(k in text for k in self._TIME_KEYWORDS)

    def _post_process_llm_questions(self, items: list) -> list:
        """LLM 输出后处理：合并时间相关问题为 1 个 + 补充缺失建议值

        合并策略：
        - 找出所有时间相关问题（_is_time_related）
        - 若多于 1 个，合并为 1 个综合问题，pending_item 标注"综合安排"
        - 保留第 1 个时间问题作为基础，把其余问题的 reason 拼接进来
        - 非时间问题保持原样
        - 重新编号 item_id
        - 对缺失 suggested_answer 的问题补一个通用建议值
        """
        if not items:
            return items

        time_items = [it for it in items if self._is_time_related(it)]
        other_items = [it for it in items if not self._is_time_related(it)]

        # 仅当时间问题 > 1 时合并
        if len(time_items) > 1:
            base = dict(time_items[0])
            sub_reasons = [it.get("pending_item", "") for it in time_items[1:]]
            base["pending_item"] = "服务时间节点综合安排（项目起算日 + 服务期限 + 阶段节点 + 季度评审节奏 + 驻场具体日期 + 成果提交时间）"
            base["reason"] = (
                str(base.get("reason", "")) +
                "；需统一确认的时间节点：" +
                "；".join(sub_reasons)
            )
            base["impact_if_not_confirmed"] = "任务排期、阶段评审、季度报告、驻场计划均缺少时间基准，全部日期字段将为空"
            base["suggest_confirm_to"] = base.get("suggest_confirm_to") or "甲乙双方项目负责人"
            if not base.get("suggested_answer"):
                base["suggested_answer"] = (
                    "建议项目起算日以合同签署日为准；服务期限按合同约定；"
                    "任务拆分粒度按服务模块阶段；阶段评审节奏每模块完成后评审 + 季度报告；"
                    "驻场具体日期由双方每季度初协商确定"
                )
            merged = [base] + other_items
        else:
            merged = items

        # 重新编号 + 补充建议值
        result = []
        for idx, it in enumerate(merged, start=1):
            it["item_id"] = f"q_{idx:03d}"
            # 补充缺失建议值
            if not it.get("suggested_answer"):
                it["suggested_answer"] = self._fallback_suggested_answer(it)
            it.setdefault("status", "待确认")
            it.setdefault("confirmed_value", "")
            result.append(it)
        return result

    def _fallback_suggested_answer(self, item: dict) -> str:
        """为缺失建议值的问题提供兜底建议"""
        pending = str(item.get("pending_item", ""))
        if "资料" in pending or "清单" in pending:
            return "建议清单：工商基础资料、近 3 年财报、税务申报底稿、银行流水、组织架构；提交时间：每季度驻场前 10 个工作日"
        if "负责人" in pending or "责任人" in pending or "对接人" in pending:
            return "建议：甲方指定财务总监或总经理助理为项目负责人；乙方指定咨询总监为项目负责人，双方各指定一名对接人"
        if "付款" in pending or "节点" in pending and "款" in pending:
            return "建议：首期款在合同签署后 15 个工作日内支付；尾期款在全部模块交付验收通过后 15 个工作日内支付"
        if "验收" in pending:
            return "建议：每模块交付后由甲方项目负责人在 5 个工作日内组织验收并签署确认单"
        if "沟通" in pending or "汇报" in pending:
            return "建议：月报 + 季度报告，月度沟通通过邮件或会议，季度评审会现场召开"
        if "风险" in pending:
            return "建议：发现风险后 3 个工作日内书面出具风险提示函，并跟踪闭环"
        return "建议双方项目负责人书面确认后形成执行依据"

    def _generate_dynamic_questions(self, summary: dict, pending_items: list, service_scope: list) -> list:
        """根据合同摘要动态生成追问问题

        调整原则（对应需求4）：
        - 服务时间节点相关问题统一合并为 1 个综合问题（项目起算日、服务期限、节点粒度、阶段评审节奏）
        - 重心放在服务计划方面：交付成果优先级、客户资料清单、责任人、付款节点、沟通机制
        - 每个问题给出"建议值"，供"我的输出"栏集中展示建议使用
        """
        questions = []
        qid = 1

        # 1. 服务时间节点综合问题（合并多个时间相关问题为 1 个）
        sign_date = summary.get("合同签署日期", "待人工确认")
        service_period = summary.get("服务期限", "")
        time_related_facts = []
        if sign_date == "待人工确认" or not sign_date:
            time_related_facts.append("合同签字页日期为空，无法确定服务起算日")
        if service_period and service_period != "待人工确认":
            time_related_facts.append(f"合同服务期限：{service_period}")
        time_related_facts.append("需确认任务拆分粒度（按季度/月度/服务模块阶段）")

        questions.append({
            "item_id": f"q_{qid:03d}",
            "pending_item": "服务时间节点综合安排（项目起算日 + 服务期限 + 任务拆分粒度 + 阶段评审节奏）",
            "related_tasks": "所有任务的时间基准、阶段评审、季度报告",
            "reason": "；".join(time_related_facts),
            "suggest_confirm_to": "甲乙双方项目负责人",
            "impact_if_not_confirmed": "任务排期、阶段评审、季度报告均缺少时间基准，全部日期字段将为空",
            "question_type": "text",
            "suggested_answer": (
                f"建议项目起算日：{sign_date if sign_date and sign_date != '待人工确认' else '合同签署日为准'}；"
                f"服务期限：{service_period if service_period and service_period != '待人工确认' else '12 个月（按合同）'}；"
                "任务拆分粒度：按服务模块阶段拆分（4 大阶段）；"
                "阶段评审节奏：每模块完成后评审 + 季度报告"
            ),
            "status": "待确认",
            "confirmed_value": "",
        })
        qid += 1

        # 2. 季度驻场安排（服务计划重心）
        onsite = summary.get("驻场安排", "")
        if onsite and onsite != "待人工确认":
            questions.append({
                "item_id": f"q_{qid:03d}",
                "pending_item": "季度驻场服务具体时间、对接人与工作内容",
                "related_tasks": "季度驻场服务任务",
                "reason": f"合同写明{onsite}，但未指定具体时间、客户对接人和每次驻场工作内容",
                "suggest_confirm_to": "甲方对接人",
                "impact_if_not_confirmed": "无法制定季度驻场计划，影响现场服务质量与交付节点",
                "question_type": "text",
                "suggested_answer": (
                    f"建议：每季度首月 15-21 日驻场 5 个工作日；"
                    f"甲方对接人由客户提供；驻场内容覆盖{summary.get('项目名称', '本项目')}各模块推进与季度评审"
                ),
                "status": "待确认",
                "confirmed_value": "",
            })
            qid += 1

        # 3. 交付成果优先级和阶段分配（服务计划重心）
        deliverable_count = summary.get("交付成果数量", 0)
        if deliverable_count and deliverable_count > 5:
            questions.append({
                "item_id": f"q_{qid:03d}",
                "pending_item": "交付成果优先级排序与阶段分配",
                "related_tasks": "所有服务执行和交付验收任务",
                "reason": f"合同列明{deliverable_count}项交付成果，未写明优先级和阶段归属",
                "suggest_confirm_to": "甲方决策人",
                "impact_if_not_confirmed": "无法确定任务执行顺序和资源投入优先级，可能影响关键模块按时交付",
                "question_type": "text",
                "suggested_answer": "建议按合同模块顺序推进：商业模式→股权架构→资产重塑→人效提升→业财合规，每模块交付后验收并归档",
                "status": "待确认",
                "confirmed_value": "",
            })
            qid += 1

        # 4. 客户资料清单（服务计划重心）
        questions.append({
            "item_id": f"q_{qid:03d}",
            "pending_item": "客户需提供的资料清单、提交时间和责任人",
            "related_tasks": "客户资料任务、各模块前置依赖",
            "reason": "合同只概括要求提供真实完整数据，未约定具体资料清单、提交节点和责任人",
            "suggest_confirm_to": "甲方对接人",
            "impact_if_not_confirmed": "无法启动资料收集任务，影响后续诊断和方案设计",
            "question_type": "text",
            "suggested_answer": "建议清单：工商基础资料、近 3 年财报、税务申报底稿、银行流水、组织架构、关键合同模板；提交时间：每季度驻场前 10 个工作日；责任人：甲方财务负责人",
            "status": "待确认",
            "confirmed_value": "",
        })
        qid += 1

        # 5. 双方项目责任人
        questions.append({
            "item_id": f"q_{qid:03d}",
            "pending_item": "双方具体项目责任人（姓名和职务）",
            "related_tasks": "全部任务",
            "reason": "合同仅列联系人，未指定项目负责人",
            "suggest_confirm_to": "甲乙双方",
            "impact_if_not_confirmed": "无法准确分配任务和发送催办通知",
            "question_type": "text",
            "suggested_answer": "建议：甲方指定财务总监或总经理助理为项目负责人；乙方指定咨询总监为项目负责人，双方各指定一名对接人处理日常事务",
            "status": "待确认",
            "confirmed_value": "",
        })
        qid += 1

        # 6. 付款节点管理（服务计划重心）
        total_fee = summary.get("服务费用（总计）", "")
        first_payment = summary.get("首期款", "")
        final_payment = summary.get("尾期款", "")
        if total_fee and total_fee != "待人工确认":
            questions.append({
                "item_id": f"q_{qid:03d}",
                "pending_item": "付款节点管理安排（首期/尾期触发条件与台账）",
                "related_tasks": "交付验收任务",
                "reason": f"合同费用{total_fee}，首期{first_payment or '未明确'}、尾期{final_payment or '未明确'}，未约定触发条件和提醒机制",
                "suggest_confirm_to": "双方项目负责人",
                "impact_if_not_confirmed": "可能遗漏付款节点，影响费用回收和现金流管理",
                "question_type": "text",
                "suggested_answer": (
                    f"建议：首期款{first_payment or '（按合同首期金额）'}在合同签署后 15 个工作日内支付；"
                    f"尾期款{final_payment or '（按合同尾期金额）'}在全部模块交付验收通过后 15 个工作日内支付；"
                    "设置付款提醒任务，由乙方项目负责人跟踪台账"
                ),
                "status": "待确认",
                "confirmed_value": "",
            })
            qid += 1

        # 7. 沟通机制（服务计划重心）
        questions.append({
            "item_id": f"q_{qid:03d}",
            "pending_item": "日常沟通机制偏好与汇报频率",
            "related_tasks": "会议沟通任务",
            "reason": "合同已要求季度报告，但未约定周报或月度沟通机制",
            "suggest_confirm_to": "双方项目负责人",
            "impact_if_not_confirmed": "缺少日常进度跟踪机制，问题可能积压",
            "question_type": "choice",
            "options": ["周报+季度报告", "月报+季度报告", "仅季度报告", "即时沟通+季度报告"],
            "suggested_answer": "月报+季度报告",
            "status": "待确认",
            "confirmed_value": "",
        })
        qid += 1

        # 8. 验收方式
        questions.append({
            "item_id": f"q_{qid:03d}",
            "pending_item": "阶段交付确认单的验收人和验收方式",
            "related_tasks": "交付验收任务",
            "reason": "合同要求5个工作日内签署交付确认单，未指定具体验收人",
            "suggest_confirm_to": "甲方项目负责人",
            "impact_if_not_confirmed": "无法及时完成阶段验收，影响后续任务推进",
            "question_type": "text",
            "suggested_answer": "建议：每模块交付后由甲方项目负责人在 5 个工作日内组织验收并签署确认单；验收标准以合同约定的交付物清单为准；不合格项需书面反馈整改意见",
            "status": "待确认",
            "confirmed_value": "",
        })

        return questions


# 全局实例
clarification_form_service = ClarificationFormService()
