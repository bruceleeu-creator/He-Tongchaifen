"""
任务拆分服务
基于合同识别结果 + 用户回答动态生成真实任务主表

设计原则（动态拆分 v2，2026-07-14）：
- 禁止使用固定 34 条模板
- 任务数量与内容由输入资料决定（合同/计划/交叉核验/用户回答）
- 每条任务的 ai_extraction_basis 必须写明来自合同/计划/澄清回答的依据
- LLM 可用时优先让 LLM 直接输出完整任务列表，失败时回退到动态规则模式
- 资料很少时只生成资料能支撑的任务，不编造模块
- 任务数量边界：通常不少于 5 条，建议上限 80 条
"""
import json
import re
import uuid
from datetime import datetime
from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


# 任务数量上限（防止 LLM 或规则失控膨胀）
_MAX_TASKS = 80
# 任务数量下限（资料不足时也至少给出可执行的占位任务）
_MIN_TASKS = 5


class TaskSplitService(AIServiceBase):
    """任务拆分服务"""

    service_name = "task_split"
    mock_filename = "task_list.json"
    prompt_name = "task_split"

    async def execute_rule(
        self,
        contract_result: str = "",
        plan_result: str = "",
        cross_check_result: str = "",
        user_answers: str = "",
        auxiliary_context: str = "",
        **kwargs,
    ) -> dict:
        """规则解析模式：基于合同+计划+用户回答动态生成任务

        合同是任务主表的权威来源，计划用于补充里程碑、时间节点和客户配合事项。
        启动会纪要等辅助资料作为补充上下文，不覆盖合同字段。
        计划不会覆盖合同已有的字段，只做增强。
        """
        # 解析合同识别结果
        try:
            contract_data = json.loads(contract_result) if isinstance(contract_result, str) else contract_result
        except (json.JSONDecodeError, TypeError):
            contract_data = {}

        # 解包 contract_result 中的 data 字段
        contract_data = self.unwrap_contract_data(contract_data)

        # 解析计划识别结果（不覆盖合同，仅做增强）
        plan_data = self._parse_plan_result(plan_result)

        # 解析交叉核验结果（补充差异提示）
        cross_check_data = self._parse_cross_check(cross_check_result)

        # 解析用户回答
        answers = {}
        if user_answers:
            try:
                answers = json.loads(user_answers) if isinstance(user_answers, str) else user_answers
            except (json.JSONDecodeError, TypeError):
                answers = {}

        summary = contract_data.get("contract_summary", {}) or {}
        service_scope = contract_data.get("service_scope", []) or []
        deliverables = contract_data.get("deliverables", []) or []
        client_resp = contract_data.get("client_responsibilities", []) or []
        our_resp = contract_data.get("our_responsibilities", []) or []
        pending_items = contract_data.get("pending_items", []) or []
        delay_rules = contract_data.get("delay_rules", []) or []

        # 动态生成任务列表（基于合同 + 计划 + 用户回答）
        tasks = self._generate_dynamic_tasks(
            summary=summary,
            service_scope=service_scope,
            deliverables=deliverables,
            client_resp=client_resp,
            our_resp=our_resp,
            pending_items=pending_items,
            delay_rules=delay_rules,
            plan_data=plan_data,
            cross_check_data=cross_check_data,
            answers=answers,
            auxiliary_context=auxiliary_context or "",
        )

        # 用计划数据增强任务（不覆盖合同字段，只补充空字段）
        plan_summary = plan_data.get("plan_summary", {})
        plan_service_modules = plan_data.get("service_modules", [])
        plan_milestones = plan_data.get("milestones", [])
        plan_enriched_count = self._enrich_tasks_with_plan(tasks, plan_service_modules, plan_milestones, plan_summary)

        # 用交叉核验结果补充风险提示
        cross_check_notes = cross_check_data.get("differences", [])

        data_source_parts = ["合同原文"]
        if plan_data.get("has_plan"):
            data_source_parts.append("年度服务计划")
        if cross_check_data.get("has_cross_check"):
            data_source_parts.append("交叉核验")
        if auxiliary_context:
            data_source_parts.append("启动会纪要(辅助)")

        task_data = {
            "tasks": tasks,
            "total": len(tasks),
            "generated_at": datetime.now().isoformat(),
            "mode": "rule",
            "data_source": " + ".join(data_source_parts),
            "contract_summary": summary,
            "plan_summary": plan_summary if plan_data.get("has_plan") else {},
            "plan_enriched_count": plan_enriched_count,
            "cross_check_notes": cross_check_notes,
            "has_auxiliary_context": bool(auxiliary_context),
            "split_strategy": "dynamic_rule",
        }

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": " + ".join(data_source_parts),
            "service": self.service_name,
            "data": task_data,
        }

    async def execute_real(
        self,
        contract_result: str = "",
        plan_result: str = "",
        cross_check_result: str = "",
        user_answers: str = "",
        auxiliary_context: str = "",
        **kwargs,
    ) -> dict:
        """LLM 增强模式

        动态拆分 v2：把合同/计划/交叉核验/用户回答完整传给 LLM，
        要求 LLM 直接输出完整任务列表（数量由 LLM 根据资料判断）。
        LLM 失败或返回 mock 时，回退到 execute_rule（动态规则模式）。
        """
        # 先用动态规则模式生成保底结果
        rule_result = await self.execute_rule(
            contract_result=contract_result,
            plan_result=plan_result,
            cross_check_result=cross_check_result,
            user_answers=user_answers,
            auxiliary_context=auxiliary_context,
            **kwargs,
        )
        if not rule_result.get("success"):
            return rule_result

        # 解析合同与计划，把完整资料传给 LLM
        try:
            contract_data = json.loads(contract_result) if isinstance(contract_result, str) else contract_result
        except (json.JSONDecodeError, TypeError):
            contract_data = {}
        contract_data = self.unwrap_contract_data(contract_data)

        plan_data = self._parse_plan_result(plan_result)
        cross_check_data = self._parse_cross_check(cross_check_result)

        # 构造 LLM 输入资料（去掉 raw_text 避免超长）
        contract_brief = {
            k: v for k, v in contract_data.items()
            if k not in ("raw_text",)
        }
        plan_brief = {
            "plan_summary": plan_data.get("plan_summary", {}),
            "service_modules": plan_data.get("service_modules", []),
            "milestones": plan_data.get("milestones", []),
            "client_data": plan_data.get("client_data", []),
            "meetings": plan_data.get("meetings", []),
        }
        cross_check_brief = cross_check_data.get("differences", [])

        prompt = f"""你是年度财税顾问项目的任务拆分助手。请基于以下合同识别结果、年度服务计划、交叉核验差异和用户澄清回答，动态拆分出完整任务主表。

【任务数量原则】
- 由资料决定，不要固定为 34 条
- 资料少时少拆，资料丰富时多拆
- 任务数量范围：5 到 80 条
- 不得编造合同/计划中没有的模块（例如不要默认出现"商业模式设计/股权架构搭建"等，除非资料中明确出现）

【任务字段】（每条任务都需包含）
- task_name: 任务名称（具体动作）
- service_module: 服务模块（取自合同 service_scope 或计划 service_modules）
- task_type: 任务类型（服务执行/客户资料/会议沟通/交付验收/客户确认/陪跑服务 之一）
- plan_start_date / plan_end_date: 计划起止时间（无则填"待确认"）
- our_owner: 我方负责人（无具体姓名则填"项目经理"）
- client_contact: 客户对接人（无具体姓名则填"客户项目负责人"）
- client_requirements: 客户需提供的资料或配合事项
- current_status: 当前状态，固定填"未开始"
- delay_responsibility: 延期责任归属，固定填"无延期"
- milestone_goal: 节点目标/达到效果
- next_action: 下一步动作及承诺完成时间
- deliverables: 交付成果或完成凭证（取自合同 deliverables 或计划交付成果）
- ai_deliverable_desc: AI 定制交付成果说明（面向应用端的交付描述）
- ai_extraction_basis: AI 提取依据，必须写明来自合同/计划/澄清回答的具体条款或来源

【输入资料】
【合同识别结果（精简）】
{json.dumps(contract_brief, ensure_ascii=False)}

【年度服务计划】
{json.dumps(plan_brief, ensure_ascii=False) if plan_data.get("has_plan") else "未上传计划"}

【交叉核验差异提示】
{json.dumps(cross_check_brief, ensure_ascii=False) if cross_check_brief else "无"}

【用户补充回答】
{user_answers or "无"}

【输出要求】
只输出合法 JSON，禁止输出 Markdown、解释文字或代码块。

JSON 结构：
{{
  "tasks": [
    {{
      "task_name": "...",
      "service_module": "...",
      "task_type": "...",
      "plan_start_date": "...",
      "plan_end_date": "...",
      "our_owner": "...",
      "client_contact": "...",
      "client_requirements": "...",
      "current_status": "未开始",
      "delay_responsibility": "无延期",
      "milestone_goal": "...",
      "next_action": "...",
      "deliverables": "...",
      "ai_deliverable_desc": "...",
      "ai_extraction_basis": "合同X条 / 计划模块 / 澄清回答"
    }}
  ],
  "split_summary": "本次拆分依据和拆分逻辑说明"
}}

要求：
1. tasks 数量由资料决定，5-80 条之间。
2. 每条 ai_extraction_basis 必须引用合同/计划/澄清回答的真实条款或来源。
3. 不得编造合同没有的具体日期、负责人姓名或金额。
4. 不得使用通用模板任务，必须紧扣输入资料。
"""

        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            # LLM 不可用或失败：返回动态规则结果
            return rule_result

        llm_tasks_raw = result.get("tasks", [])
        if not isinstance(llm_tasks_raw, list) or not llm_tasks_raw:
            return rule_result

        # 规范化 LLM 输出任务，补齐 task_id / seq / created_at / review_status
        customer = (contract_data.get("contract_summary", {}) or {}).get("甲方", "待人工确认")
        project = (contract_data.get("contract_summary", {}) or {}).get("项目名称", "待人工确认")
        now_iso = datetime.now().isoformat()
        normalized: list[dict] = []
        allowed_fields = {
            "task_name", "service_module", "task_type",
            "plan_start_date", "plan_end_date",
            "our_owner", "client_contact", "client_requirements",
            "current_status", "delay_responsibility",
            "milestone_goal", "next_action",
            "deliverables", "ai_deliverable_desc", "ai_extraction_basis",
        }
        for raw in llm_tasks_raw:
            if not isinstance(raw, dict):
                continue
            task_name = str(raw.get("task_name", "")).strip()
            if not task_name:
                continue
            task = {
                "task_id": f"task_{len(normalized)+1:03d}_{uuid.uuid4().hex[:6]}",
                "seq": len(normalized) + 1,
                "customer_name": customer,
                "project_name": project,
                "current_status": "未开始",
                "delay_responsibility": "无延期",
                "review_status": "待复核",
                "created_at": now_iso,
            }
            for field in allowed_fields:
                value = raw.get(field)
                if isinstance(value, str) and value.strip():
                    task[field] = value.strip()
                else:
                    # 缺失字段填默认占位
                    task.setdefault(field, "")
            # 关键兜底
            task.setdefault("plan_start_date", "待确认")
            task.setdefault("plan_end_date", "待确认")
            task.setdefault("our_owner", "项目经理")
            task.setdefault("client_contact", "客户项目负责人")
            normalized.append(task)
            if len(normalized) >= _MAX_TASKS:
                break

        if len(normalized) < _MIN_TASKS:
            # LLM 输出过少，不可信，回退到规则模式
            return rule_result

        rule_data_source = rule_result.get("data_source", "合同原文")
        task_data = {
            "tasks": normalized,
            "total": len(normalized),
            "generated_at": now_iso,
            "mode": "llm",
            "data_source": f"{rule_data_source}(LLM动态拆分: {llm_client.model})",
            "contract_summary": contract_data.get("contract_summary", {}) or {},
            "plan_summary": plan_data.get("plan_summary", {}) if plan_data.get("has_plan") else {},
            "plan_enriched_count": 0,
            "cross_check_notes": cross_check_brief,
            "has_auxiliary_context": bool(auxiliary_context),
            "split_strategy": "llm_dynamic",
            "llm_enhancement": {
                "model": llm_client.model,
                "model_source": llm_client.model_source,
                "task_count": len(normalized),
                "split_summary": result.get("split_summary", ""),
            },
        }

        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM动态拆分)",
            "data_source": task_data["data_source"],
            "service": self.service_name,
            "data": task_data,
        }

    def _parse_plan_result(self, plan_result) -> dict:
        """解析计划识别结果，返回结构化字典。

        plan_result 可能是 dict 或 JSON 字符串，可能包含 data 嵌套。
        实际 plan_result.json 的 data 字段包含：
        service_modules / stage_nodes / client_requirements / meetings / pending_items
        也兼容 milestones / client_data 等别名。
        """
        empty = {
            "has_plan": False, "plan_summary": {},
            "service_modules": [], "milestones": [],
            "client_data": [], "meetings": [],
        }
        if not plan_result:
            return empty
        try:
            data = json.loads(plan_result) if isinstance(plan_result, str) else plan_result
        except (json.JSONDecodeError, TypeError):
            return empty
        if not isinstance(data, dict):
            return empty
        # 解包 data 嵌套
        inner = data.get("data", data)
        if not isinstance(inner, dict):
            inner = {}

        # 提取各类计划数据（兼容别名）
        service_modules = inner.get("service_modules", [])
        if not isinstance(service_modules, list):
            service_modules = []

        # milestones 兼容 stage_nodes / milestone_list
        milestones = inner.get("milestones", inner.get("stage_nodes", inner.get("milestone_list", [])))
        if not isinstance(milestones, list):
            milestones = []

        # client_data 兼容 client_requirements
        client_data = inner.get("client_data", inner.get("client_requirements", []))
        if not isinstance(client_data, list):
            client_data = []

        meetings = inner.get("meetings", [])
        if not isinstance(meetings, list):
            meetings = []

        # has_plan：任一列表非空即为真
        has_plan = bool(service_modules or milestones or client_data or meetings)

        # 构建 plan_summary（含统计与样本，便于追溯）
        source_file = inner.get("source_file", inner.get("filename", data.get("source_file", "")))
        plan_summary = {
            "source_file": source_file,
            "module_count": len(service_modules),
            "milestone_count": len(milestones),
            "client_data_count": len(client_data),
            "meeting_count": len(meetings),
            "module_samples": service_modules[:3],
            "milestone_samples": milestones[:2],
        }

        return {
            "has_plan": has_plan,
            "plan_summary": plan_summary,
            "service_modules": service_modules,
            "milestones": milestones,
            "client_data": client_data,
            "meetings": meetings,
        }

    def _parse_cross_check(self, cross_check_result) -> dict:
        """解析交叉核验结果"""
        if not cross_check_result:
            return {"has_cross_check": False, "differences": []}
        try:
            data = json.loads(cross_check_result) if isinstance(cross_check_result, str) else cross_check_result
        except (json.JSONDecodeError, TypeError):
            return {"has_cross_check": False, "differences": []}
        if not isinstance(data, dict):
            return {"has_cross_check": False, "differences": []}
        inner = data.get("data", data)
        if not isinstance(inner, dict):
            inner = {}
        differences = inner.get("differences", inner.get("issues", []))
        if not isinstance(differences, list):
            differences = []
        return {
            "has_cross_check": True,
            "differences": differences,
        }

    def _enrich_tasks_with_plan(self, tasks: list, service_modules: list, milestones: list, plan_summary: dict) -> int:
        """用计划服务模块和阶段节点增强任务，不覆盖合同已有字段。

        策略：
        1. 按 service_module / task_name 关键词匹配计划服务模块条目
        2. 将匹配到的计划依据追加到 ai_extraction_basis（不覆盖原有合同依据）
        3. 填充空的 next_action / milestone_goal（仅当原值为空或以"待"开头时）
        返回增强的任务数量。
        """
        if not service_modules and not milestones:
            return 0

        enriched = 0

        # 构建服务模块匹配索引：关键词 -> 计划条目文本
        module_index: list[tuple[str, str]] = []
        for sm in service_modules:
            if not isinstance(sm, dict):
                continue
            module_name = str(sm.get("服务模块", ""))
            item_name = str(sm.get("服务事项", ""))
            deliverable = str(sm.get("计划交付成果", ""))
            period = str(sm.get("计划月份或周期", ""))
            basis = str(sm.get("依据摘要", ""))
            keywords = []
            for text in [module_name, item_name]:
                if not text:
                    continue
                keywords.append(text)
                segs = re.split(r'[、，,\-·\s]+', text)
                for seg in segs:
                    seg = seg.strip()
                    if len(seg) >= 2:
                        keywords.append(seg)
                    if len(seg) >= 5:
                        for i in range(len(seg) - 3):
                            sub = seg[i:i+4]
                            if len(sub) >= 3:
                                keywords.append(sub)
            evidence_parts = [f"模块:{module_name}"]
            if item_name:
                evidence_parts.append(f"事项:{item_name}")
            if period:
                evidence_parts.append(f"周期:{period}")
            if deliverable:
                evidence_parts.append(f"计划交付:{deliverable[:80]}")
            if basis:
                evidence_parts.append(f"来源:{basis}")
            evidence = "[计划依据] " + "; ".join(evidence_parts)
            for kw in keywords:
                module_index.append((kw, evidence))

        # 阶段节点文本（用于补充 milestone_goal）
        stage_texts: list[str] = []
        for stage in milestones:
            if not isinstance(stage, dict):
                continue
            stage_name = stage.get("阶段", stage.get("name", ""))
            stage_goal = stage.get("阶段目标", stage.get("target", ""))
            stage_tasks = stage.get("关键任务", stage.get("key_tasks", ""))
            stage_deliverable = stage.get("交付成果", stage.get("deliverables", ""))
            stage_texts.append(f"阶段「{stage_name}」目标:{stage_goal}; 关键任务:{stage_tasks}; 交付:{stage_deliverable}")

        for task in tasks:
            task_module = str(task.get("service_module", ""))
            task_name = str(task.get("task_name", ""))
            matched_evidences: list[str] = []

            for kw, evidence in module_index:
                if not kw:
                    continue
                if kw in task_module or kw in task_name or task_module in kw:
                    if evidence not in matched_evidences:
                        matched_evidences.append(evidence)

            task_changed = False

            if matched_evidences:
                existing_basis = str(task.get("ai_extraction_basis", ""))
                plan_evidence = " | ".join(matched_evidences[:2])
                if plan_evidence not in existing_basis:
                    if existing_basis:
                        task["ai_extraction_basis"] = f"{existing_basis}\n{plan_evidence}"
                    else:
                        task["ai_extraction_basis"] = plan_evidence
                    task_changed = True

            next_action = str(task.get("next_action", ""))
            if not next_action or next_action.startswith("待"):
                if matched_evidences:
                    task["next_action"] = f"参考年度服务计划: {matched_evidences[0][:150]}"
                    task_changed = True
                elif stage_texts:
                    task["next_action"] = f"参考计划阶段: {stage_texts[0][:150]}"
                    task_changed = True

            milestone_goal = str(task.get("milestone_goal", ""))
            if not milestone_goal or milestone_goal.startswith("待"):
                if stage_texts:
                    matched_stage = None
                    for st in stage_texts:
                        if task_module and task_module in st:
                            matched_stage = st
                            break
                    if not matched_stage:
                        matched_stage = stage_texts[0]
                    task["milestone_goal"] = f"参考计划阶段目标: {matched_stage[:150]}"
                    task_changed = True

            if task_changed:
                enriched += 1

        return enriched

    # ============================================================
    # 动态任务生成（替代旧版固定 34 条模板）
    # ============================================================

    def _generate_dynamic_tasks(
        self,
        summary: dict,
        service_scope: list,
        deliverables: list,
        client_resp: list,
        our_resp: list,
        pending_items: list,
        delay_rules: list,
        plan_data: dict,
        cross_check_data: dict,
        answers: dict,
        auxiliary_context: str,
    ) -> list:
        """基于合同+计划+澄清回答动态生成任务列表

        生成策略（每条任务的依据来自输入资料，不使用固定模板）：
        1. 启动会与基准计划任务：仅当合同/计划出现"会议沟通"或"启动"类内容时生成
        2. 客户资料收集任务：基于 client_responsibilities 逐条生成
        3. 服务模块执行任务：基于 service_scope 每个服务事项生成 1 条任务
        4. 我方执行任务：基于 our_responsibilities 逐条生成
        5. 交付成果验收任务：基于 deliverables 逐条生成
        6. 待确认事项任务：基于 pending_items 生成
        7. 计划里程碑任务：基于 plan milestones 生成阶段任务
        8. 付款节点任务：仅当合同摘要包含首期款/尾期款且用户要求时生成
        9. 驻场与响应任务：仅当合同摘要包含驻场安排/响应时效时生成
        10. 阶段评审任务：仅当合同/计划包含评审类内容时生成
        """
        tasks: list[dict] = []
        customer = summary.get("甲方", "待人工确认") or "待人工确认"
        project = summary.get("项目名称", "待人工确认") or "待人工确认"
        service_term = summary.get("服务期限", "") or ""
        total_fee = summary.get("服务费用（总计）", "") or ""
        first_payment = summary.get("首期款", "") or ""
        later_payment = summary.get("尾期款", "") or ""
        onsite = summary.get("驻场安排", "") or ""
        response_time = summary.get("响应时效", "") or ""
        sign_date = summary.get("合同签署日期", "") or ""

        # 从用户回答提取补充信息
        start_date = str(answers.get("合同签署日期和项目启动日期", "")) or ""
        project_owners = str(answers.get("双方具体项目责任人（姓名和职务）", "")) or ""
        need_response_log = str(answers.get("是否需要建立紧急问题响应记录台账", "")) or ""
        payment_mgmt = str(answers.get("付款节点是否需要进入项目提醒或管理台账", "")) or ""
        review_frequency = str(answers.get("阶段评审频率和确认方式", "")) or ""

        date_placeholder = start_date or (sign_date if sign_date and sign_date != "待人工确认" else "待确认")
        our_owner = project_owners.split("、")[0] if project_owners else "项目经理"
        client_owner = project_owners.split("、")[-1] if project_owners else "客户项目负责人"

        def _basis(*parts: str) -> str:
            """拼接 ai_extraction_basis，过滤空片段"""
            return "; ".join([p for p in parts if p])

        # ---------- 1. 启动会与基准计划任务 ----------
        # 仅当 service_scope 或计划包含会议沟通/启动类内容时生成
        has_meeting_module = any(
            self._contains_keyword(self._scope_module_text(s), ["会议沟通", "启动", "评审"])
            for s in service_scope if isinstance(s, dict)
        ) or any(
            self._contains_keyword(str(m.get("服务模块", "")), ["会议沟通", "启动", "评审"])
            for m in plan_data.get("service_modules", []) if isinstance(m, dict)
        )
        if has_meeting_module:
            scope_basis = self._find_scope_basis(service_scope, ["会议沟通", "启动", "评审"])
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "召开项目启动会并确认年度基准计划",
                "会议沟通", "会议沟通",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "确认服务范围、服务期、双方责任人、资料清单、沟通机制、顺延暂停规则",
                "未开始", "无延期",
                "完成项目启动和年度基准计划锁定，后续所有任务有明确时间、责任和确认口径",
                "待启动会确认年度基准时间表",
                "启动会纪要、年度基准时间表、双方责任人清单、客户资料清单、顺延暂停确认条款",
                "应用端应根据合同缺口自动生成启动会确认议程，并把缺失项转为待确认事项",
                _basis(scope_basis, self._delay_basis(delay_rules)),
            ))

        # ---------- 2. 客户资料收集任务 ----------
        for cr in client_resp:
            if not isinstance(cr, dict):
                continue
            item_text = str(cr.get("客户需配合事项", "")).strip()
            if not item_text:
                continue
            module = str(cr.get("涉及服务模块", "客户资料")) or "客户资料"
            time_req = str(cr.get("时间要求", "")) or ""
            basis = str(cr.get("依据摘要", "")) or ""
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                f"客户配合：{item_text[:60]}",
                module, "客户资料",
                date_placeholder, time_req or date_placeholder,
                our_owner, client_owner,
                item_text,
                "未开始", "无延期",
                f"客户按时提供：{item_text[:80]}",
                time_req or "按合同约定时间跟进",
                "资料签收清单、缺失资料清单",
                "应用端应跟踪客户资料提交情况并自动提示",
                _basis(f"客户责任: {item_text}", basis, self._delay_basis(delay_rules)),
            ))
            if len(tasks) >= _MAX_TASKS:
                break

        # ---------- 3. 服务模块执行任务 ----------
        # 每个 service_scope 条目按服务事项拆分生成 1~N 条任务
        for scope in service_scope:
            if len(tasks) >= _MAX_TASKS:
                break
            if not isinstance(scope, dict):
                continue
            module = str(scope.get("服务模块", "")).strip() or "服务执行"
            items_text = str(scope.get("服务事项", "")).strip()
            scope_deliverables = str(scope.get("交付成果", "")).strip()
            basis = str(scope.get("依据摘要", "")).strip()
            # 把多条服务事项按分号/换行拆开
            item_list = [s.strip() for s in re.split(r'[;\n]+', items_text) if s.strip()]
            if not item_list:
                # 服务事项为空时，仅基于模块生成 1 条任务
                item_list = [f"推进{module}相关工作"]
            for item in item_list:
                if len(tasks) >= _MAX_TASKS:
                    break
                # 跳过会议沟通/启动会（已在 1 中处理）
                if module == "会议沟通" and self._contains_keyword(item, ["启动会", "评审会"]):
                    continue
                # 跳过客户资料类（已在 2 中处理）
                if module == "客户资料":
                    continue
                # 跳过交付验收类（将在 5 中处理）
                if module == "交付验收":
                    continue
                tasks.append(self._make_task(
                    len(tasks) + 1, customer, project,
                    item[:80],
                    module, "服务执行",
                    date_placeholder, date_placeholder,
                    our_owner, client_owner,
                    f"客户配合提供{module}相关资料与确认",
                    "未开始", "无延期",
                    f"完成{module}模块：{item[:60]}",
                    "待启动会确认年度基准时间表",
                    scope_deliverables or "模块交付成果",
                    "应用端应根据合同条款定制任务内容",
                    _basis(f"合同服务范围[{module}]: {item}", basis),
                ))

        # ---------- 4. 我方执行任务 ----------
        for our in our_resp:
            if len(tasks) >= _MAX_TASKS:
                break
            if not isinstance(our, dict):
                continue
            resp_text = str(our.get("我方责任", "")).strip()
            if not resp_text:
                continue
            module = str(our.get("涉及服务模块", "服务执行")) or "服务执行"
            our_deliverable = str(our.get("交付成果", "")).strip()
            time_req = str(our.get("时间要求", "")) or ""
            basis = str(our.get("依据摘要", "")).strip()
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                f"我方执行：{resp_text[:60]}",
                module, "服务执行",
                date_placeholder, time_req or date_placeholder,
                our_owner, client_owner,
                "客户确认相关方向与边界",
                "未开始", "无延期",
                f"按合同要求完成：{resp_text[:60]}",
                time_req or "按合同约定节点推进",
                our_deliverable or "对应模块交付成果",
                "应用端应按合同我方责任条款跟踪执行进度",
                _basis(f"合同我方责任[{module}]: {resp_text}", basis),
            ))

        # ---------- 5. 交付成果验收任务 ----------
        # deliverables 可能是字符串列表，也可能从 service_scope 交付成果提取
        deliverable_list: list[str] = []
        if isinstance(deliverables, list):
            for d in deliverables:
                if isinstance(d, str) and d.strip():
                    deliverable_list.append(d.strip())
                elif isinstance(d, dict):
                    name = str(d.get("交付成果", d.get("名称", ""))).strip()
                    if name:
                        deliverable_list.append(name)
        if deliverable_list:
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "提交阶段交付成果并发起书面确认",
                "交付验收", "交付验收",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "客户在5个工作日内签署交付确认单",
                "未开始", "无延期",
                "每阶段交付成果后发起客户确认，形成书面验收记录",
                "每阶段完成后发起确认",
                "《交付确认单》",
                "应用端应按合同自动生成确认流程",
                _basis("合同交付物验收条款", self._deliverable_list_basis(deliverable_list)),
            ))
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "服务期满提交整体服务效果评估报告",
                "交付验收", "交付验收",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "全年服务成果汇总、合同服务目标逐项对照",
                "未开始", "无延期",
                "对照合同服务目标逐项验收，形成整体服务效果评估",
                "服务期满后提交",
                "《整体服务效果评估报告》",
                "应用端应按合同服务目标自动生成验收清单",
                _basis("合同效果验收条款", self._deliverable_list_basis(deliverable_list)),
            ))

        # ---------- 6. 待确认事项任务 ----------
        for pi in pending_items:
            if len(tasks) >= _MAX_TASKS:
                break
            if not isinstance(pi, dict):
                continue
            pending_text = str(pi.get("待确认事项", "")).strip()
            if not pending_text:
                continue
            reason = str(pi.get("原因", "")).strip()
            suggest = str(pi.get("建议向谁确认", "客户")).strip() or "客户"
            impact = str(pi.get("不确认的影响", "")).strip()
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                f"待确认：{pending_text[:60]}",
                "待确认事项", "客户确认",
                date_placeholder, date_placeholder,
                our_owner, suggest,
                pending_text,
                "未开始", "无延期",
                f"向{suggest}确认：{pending_text[:60]}",
                "项目启动后尽快确认",
                "确认记录、更新任务字段",
                "应用端应把待确认事项转为可跟踪的提醒任务",
                _basis(f"合同待确认事项: {pending_text}", f"原因: {reason}" if reason else "", f"影响: {impact}" if impact else ""),
            ))

        # ---------- 7. 计划里程碑任务 ----------
        plan_milestones = plan_data.get("milestones", []) or []
        for ms in plan_milestones:
            if len(tasks) >= _MAX_TASKS:
                break
            if not isinstance(ms, dict):
                continue
            stage_name = str(ms.get("阶段", ms.get("name", ""))).strip()
            stage_goal = str(ms.get("阶段目标", ms.get("target", ""))).strip()
            stage_tasks_text = str(ms.get("关键任务", ms.get("key_tasks", ""))).strip()
            stage_deliverable = str(ms.get("交付成果", ms.get("deliverables", ""))).strip()
            if not stage_name and not stage_goal:
                continue
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                f"推进计划阶段：{stage_name or '阶段节点'}",
                stage_name or "计划阶段", "服务执行",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "客户配合确认阶段方向与交付",
                "未开始", "无延期",
                stage_goal or f"完成计划阶段「{stage_name}」",
                "按计划节点推进",
                stage_deliverable or "阶段交付成果",
                "应用端应按年度服务计划阶段节点跟踪",
                _basis(f"年度服务计划阶段: {stage_name}", f"阶段目标: {stage_goal}" if stage_goal else "", f"关键任务: {stage_tasks_text}" if stage_tasks_text else ""),
            ))

        # ---------- 8. 付款节点任务（仅当用户要求且合同有付款信息时） ----------
        if "需要" in payment_mgmt and (first_payment or later_payment or total_fee):
            if first_payment:
                tasks.append(self._make_task(
                    len(tasks) + 1, customer, project,
                    "跟进首期款支付",
                    "交付验收", "客户确认",
                    date_placeholder, date_placeholder,
                    our_owner, client_owner,
                    "合同签订后按时支付首期款",
                    "未开始", "无延期",
                    "确保首期款按时到账",
                    "合同签订后跟进",
                    "首期款支付凭证、增值税普通发票",
                    "应用端应根据合同付款条款自动设置提醒",
                    _basis(f"合同首期款条款: {first_payment}", f"用户回答: {payment_mgmt}"),
                ))
            if later_payment:
                tasks.append(self._make_task(
                    len(tasks) + 1, customer, project,
                    "跟进尾期款支付",
                    "交付验收", "客户确认",
                    date_placeholder, date_placeholder,
                    our_owner, client_owner,
                    "按合同约定时间支付尾期款",
                    "未开始", "无延期",
                    "确保尾期款按时到账",
                    "按合同节点跟进",
                    "尾期款支付凭证、增值税普通发票",
                    "应用端应根据合同付款条款自动设置提醒",
                    _basis(f"合同尾期款条款: {later_payment}", f"用户回答: {payment_mgmt}"),
                ))

        # ---------- 9. 驻场与响应任务（仅当合同包含相关条款时） ----------
        if onsite:
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "制定季度驻场服务计划",
                "陪跑服务", "服务执行",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                f"按合同驻场安排排期：{onsite}",
                "未开始", "无延期",
                "形成可执行的季度驻场排期",
                "项目启动后制定",
                "季度驻场计划",
                "应用端应根据合同驻场安排自动生成季度计划模板",
                _basis(f"合同驻场安排: {onsite}"),
            ))
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "完成季度现场服务并形成记录",
                "陪跑服务", "服务执行",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "现场服务内容、客户反馈、问题记录",
                "未开始", "无延期",
                "每次现场服务后形成完整记录",
                "每季度驻场后3个工作日内完成记录",
                "现场服务记录",
                "应用端应提供现场服务记录模板",
                _basis(f"合同驻场安排: {onsite}"),
            ))
        if response_time:
            task_name = "建立紧急问题48小时响应台账" if "需要" in need_response_log else "建立紧急问题响应机制"
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                task_name,
                "陪跑服务", "服务执行",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "紧急问题记录、响应时间追踪、解决方案存档",
                "未开始", "无延期",
                f"确保紧急问题按时回复：{response_time}",
                "项目启动后建立台账并持续维护",
                "紧急问题响应记录",
                "应用端应根据合同响应时效自动建立台账",
                _basis(f"合同响应时效: {response_time}", f"用户回答: {need_response_log}" if need_response_log else ""),
            ))
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "每季度提交服务进度与效果报告",
                "陪跑服务", "交付验收",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "季度服务内容、进度、效果数据、客户反馈",
                "未开始", "无延期",
                "按合同要求每季度提交进度报告",
                "每季度末提交",
                "《服务进度与效果报告》",
                "应用端应按季度自动生成报告模板",
                _basis("合同乙方责任: 每季度提交服务进度报告"),
            ))

        # ---------- 10. 阶段评审任务（仅当合同/计划包含评审内容时） ----------
        has_review = bool(review_frequency) or any(
            self._contains_keyword(self._scope_module_text(s), ["评审", "复盘", "验收"])
            for s in service_scope if isinstance(s, dict)
        )
        if has_review:
            tasks.append(self._make_task(
                len(tasks) + 1, customer, project,
                "召开阶段方案评审会",
                "会议沟通", "会议沟通",
                date_placeholder, date_placeholder,
                our_owner, client_owner,
                "客户确认阶段方案方向、调整意见、落地边界和下一阶段重点",
                "未开始", "无延期",
                "每个模块完成后形成客户确认，确保方案不是单方输出",
                f"各模块完成后召开评审会; 评审频率: {review_frequency}" if review_frequency else "各模块完成后召开评审会",
                "阶段评审会议纪要、客户确认记录、调整事项清单",
                "应用端应按阶段成果自动生成评审议程",
                _basis("合同服务方式: 嵌入式服务", f"用户回答评审频率: {review_frequency}" if review_frequency else ""),
            ))

        # ---------- 兜底：任务数过少时补充启动类任务 ----------
        if len(tasks) < _MIN_TASKS:
            # 资料极少：基于合同摘要关键字段生成最小可执行任务集
            if not any("启动会" in t.get("task_name", "") for t in tasks):
                tasks.append(self._make_task(
                    len(tasks) + 1, customer, project,
                    "召开项目启动会并确认服务范围",
                    "会议沟通", "会议沟通",
                    date_placeholder, date_placeholder,
                    our_owner, client_owner,
                    "确认服务范围、服务期、双方责任人",
                    "未开始", "无延期",
                    "完成项目启动和服务范围锁定",
                    "待确认启动时间",
                    "启动会纪要、服务范围确认书",
                    "应用端应基于合同摘要生成启动任务",
                    _basis(f"合同甲方: {customer}", f"合同项目名称: {project}", f"合同服务期限: {service_term}" if service_term else ""),
                ))
            while len(tasks) < _MIN_TASKS:
                idx = len(tasks) + 1
                tasks.append(self._make_task(
                    idx, customer, project,
                    f"按合同服务范围推进第 {idx - 1} 阶段工作",
                    "服务执行", "服务执行",
                    date_placeholder, date_placeholder,
                    our_owner, client_owner,
                    "客户配合提供阶段所需资料",
                    "未开始", "无延期",
                    "按合同服务范围推进",
                    "按合同节点推进",
                    "阶段交付成果",
                    "应用端应基于合同摘要补充任务",
                    _basis(f"合同项目名称: {project}", f"合同服务期限: {service_term}" if service_term else ""),
                ))

        # 重新编号 seq，确保连续
        for i, t in enumerate(tasks, start=1):
            t["seq"] = i
            t["task_id"] = f"task_{i:03d}_{uuid.uuid4().hex[:6]}"

        return tasks

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _contains_keyword(text: str, keywords: list[str]) -> bool:
        if not text:
            return False
        return any(kw in text for kw in keywords)

    @staticmethod
    def _scope_module_text(scope: dict) -> str:
        """从 service_scope 条目拼接可搜索的文本"""
        if not isinstance(scope, dict):
            return ""
        return " ".join([
            str(scope.get("服务模块", "")),
            str(scope.get("服务事项", "")),
            str(scope.get("交付成果", "")),
        ])

    @staticmethod
    def _find_scope_basis(service_scope: list, keywords: list[str]) -> str:
        """从 service_scope 中查找含关键词的条目，返回依据文本"""
        for scope in service_scope:
            if not isinstance(scope, dict):
                continue
            text = TaskSplitService._scope_module_text(scope)
            if TaskSplitService._contains_keyword(text, keywords):
                module = str(scope.get("服务模块", ""))
                item = str(scope.get("服务事项", ""))
                basis = str(scope.get("依据摘要", ""))
                return f"合同服务范围[{module}]: {item}" + (f"; 来源: {basis}" if basis else "")
        return "合同服务范围(会议沟通/启动类)"

    @staticmethod
    def _delay_basis(delay_rules: list) -> str:
        """从 delay_rules 提取顺延/暂停依据"""
        if not delay_rules:
            return ""
        parts = []
        for r in delay_rules:
            if not isinstance(r, dict):
                continue
            rule_type = str(r.get("规则类型", "")).strip()
            content = str(r.get("合同约定内容", "")).strip()
            if rule_type and content:
                parts.append(f"{rule_type}: {content[:60]}")
        if not parts:
            return ""
        return "合同延期规则: " + " | ".join(parts[:2])

    @staticmethod
    def _deliverable_list_basis(deliverable_list: list[str]) -> str:
        """从交付成果列表生成依据"""
        if not deliverable_list:
            return ""
        sample = deliverable_list[:5]
        return "合同交付成果: " + "、".join(sample)

    def _make_task(
        self, seq, customer, project, task_name, service_module, task_type,
        plan_start, plan_end, our_owner, client_contact, client_requirements,
        status, delay_resp, milestone, next_action, deliverables, ai_desc, ai_basis,
    ) -> dict:
        """创建单个任务"""
        return {
            "task_id": f"task_{seq:03d}_{uuid.uuid4().hex[:6]}",
            "seq": seq,
            "customer_name": customer,
            "project_name": project,
            "task_name": task_name,
            "service_module": service_module,
            "task_type": task_type,
            "plan_start_date": plan_start,
            "plan_end_date": plan_end,
            "our_owner": our_owner,
            "client_contact": client_contact,
            "client_requirements": client_requirements,
            "current_status": status,
            "delay_responsibility": delay_resp,
            "milestone_goal": milestone,
            "next_action": next_action,
            "deliverables": deliverables,
            "ai_deliverable_desc": ai_desc,
            "ai_extraction_basis": ai_basis,
            "review_status": "待复核",
            "created_at": datetime.now().isoformat(),
        }


# 全局实例
task_split_service = TaskSplitService()
