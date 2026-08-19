"""
交付成果设计 AI 服务
为每个任务设计最合适的交付成果
"""
import json
import secrets
import uuid
from datetime import datetime
from typing import Optional

from services.ai_services.base import AIServiceBase
from services.deliverable_writer import deliverable_writer
from services.llm_client import llm_client


# 需求7：多模板池 - 同一类任务可随机轮换 5-8 套不同模板，刷新时切换
# 每个 pool_entry: {template_key, template_name, deliverable_type, outline}
MULTI_TEMPLATE_POOL: list[dict] = [
    {
        "template_key": "scheme_report_v1",
        "template_name": "方案报告",
        "deliverable_type": "报告",
        "outline": [
            "项目背景与目标",
            "现状诊断与问题分析",
            "解决方案与实施路径",
            "关键里程碑与时间节点",
            "风险识别与应对策略",
            "资源需求与责任分工",
            "验收标准与交付清单",
            "双方确认与签字栏",
        ],
    },
    {
        "template_key": "workpaper_v1",
        "template_name": "工作底稿",
        "deliverable_type": "底稿",
        "outline": [
            "底稿基本信息",
            "审计/核查程序与执行情况",
            "抽样方法与样本说明",
            "数据测算过程与公式",
            "发现的问题与证据链",
            "初步结论与建议调整",
            "复核记录与签字栏",
        ],
    },
    {
        "template_key": "checklist_v1",
        "template_name": "清单台账",
        "deliverable_type": "清单",
        "outline": [
            "清单目的与适用范围",
            "事项分类与编号规则",
            "逐项明细（含状态、责任人、时间）",
            "完整性核查与勾稽关系",
            "缺失项跟进与闭环机制",
            "归档与版本管理",
        ],
    },
    {
        "template_key": "assessment_opinion_v1",
        "template_name": "评估意见书",
        "deliverable_type": "意见书",
        "outline": [
            "评估对象与基准日",
            "评估依据与方法论",
            "关键假设与限制条件",
            "评估测算过程",
            "评估结论与价值区间",
            "风险提示与使用限制",
            "评估师签字与执业印章",
        ],
    },
    {
        "template_key": "memo_v1",
        "template_name": "备忘录",
        "deliverable_type": "备忘录",
        "outline": [
            "备忘事项与背景",
            "关键事实梳理",
            "适用的法规与政策",
            "处理建议与操作步骤",
            "后续跟踪事项",
            "经办人与复核人签字",
        ],
    },
    {
        "template_key": "inspection_report_v1",
        "template_name": "检查报告",
        "deliverable_type": "报告",
        "outline": [
            "检查范围与依据",
            "检查程序与方法",
            "检查发现（按事项分类）",
            "问题严重性评级",
            "整改建议与时限",
            "复查计划与闭环要求",
            "签发栏",
        ],
    },
    {
        "template_key": "confirmation_v1",
        "template_name": "确认单",
        "deliverable_type": "确认函",
        "outline": [
            "确认事项与依据",
            "交付物清单与验收标准",
            "验收过程与结果记录",
            "存在问题与改进措施",
            "下一阶段工作计划",
            "双方签字确认",
        ],
    },
    {
        "template_key": "minutes_v1",
        "template_name": "会议纪要",
        "deliverable_type": "纪要",
        "outline": [
            "会议基本信息",
            "会议议题与讨论要点",
            "双方达成的共识",
            "分歧事项与处理建议",
            "决议事项与责任人",
            "下次会议安排",
            "与会人员签到",
        ],
    },
]


class DeliverableDesignService(AIServiceBase):
    """交付成果设计服务"""

    service_name = "deliverable_design"
    prompt_name = "deliverable_design"

    async def execute_rule(self, task: dict, **kwargs) -> dict:
        """规则模式：基于模板匹配 + 任务字段生成内容丰满的交付成果设计

        需求7新增逻辑：
        - 支持传入 exclude_template_keys：避免重新生成时复用同一套模板
        - 若匹配到的模板被排除，则从多模板池随机挑选一套未用过的
        """
        service_module = task.get("service_module", "")
        task_type = task.get("task_type", "")
        task_name = task.get("task_name", "")
        exclude_keys = set(kwargs.get("exclude_template_keys", []) or [])

        # 尝试模板匹配
        matched = deliverable_writer.match_template(service_module, task_type, task_name)
        if matched and matched.get("template_key") in exclude_keys:
            # 已用过，从多模板池选另一套
            matched = None

        if matched:
            template_key = matched.get("template_key", "")
            template_name = matched.get("template_name", "")
            content_schema = matched.get("content_schema", {})
            outline = content_schema.get("sections", [])

            # 构建设计理由
            reason = (
                f"根据任务类型「{task_type}」和服务模块「{service_module}」"
                f"，匹配到标准模板「{template_name}」。"
                f"该成果用于规范{task_name}的交付标准，确保客户可验收、可留存。"
            )

            # 生成内容丰满的章节与字段（基于任务实际信息，无空段）
            content_sections = self._build_content_sections(task, outline, template_name)
            acceptance_criteria = self._build_acceptance_criteria(task, task_type)
            client_inputs = self._build_client_inputs(task, task_type)
            risk_notes = self._build_risk_notes(task, task_type)
            next_actions = self._build_next_actions(task, task_type)

            return {
                "success": True,
                "mode": "rule",
                "mode_label": "真实解析模式(规则解析)",
                "data_source": "合同原文",
                "service": self.service_name,
                "data": {
                    "deliverable_name": f"《{task_name}》{template_name}",
                    "deliverable_type": matched.get("deliverable_type", "文档"),
                    "file_format": "docx",
                    "template_key": template_key,
                    "template_name": template_name,
                    "ai_design_reason": reason,
                    "content_outline": outline,
                    "content_sections": content_sections,
                    "acceptance_criteria": acceptance_criteria,
                    "client_inputs": client_inputs,
                    "risk_notes": risk_notes,
                    "next_actions": next_actions,
                    "variables": self._build_variables_with_defaults(task),
                    "reusable": True,
                    "reuse_source": "模板复用",
                },
            }

        # 无匹配模板时，从多模板池挑选（排除已用过的）
        return self._generic_design(task, exclude_keys=exclude_keys)

    async def execute_real(self, task: dict, **kwargs) -> dict:
        """LLM 模式：调用 LLM 设计交付成果

        kwargs 支持 force_rule=True，用于批量生成时强制走规则/模板模式，
        避免对每个任务依次调用 LLM 导致前端请求超时（120s）。
        kwargs 支持 exclude_template_keys，用于重新生成时排除已用过的模板。
        """
        # 批量场景：强制规则/模板模式，单任务保持 LLM 深度解析
        if kwargs.get("force_rule"):
            rule_result = await self.execute_rule(task, **kwargs)
            rule_result["mode"] = "rule"
            rule_result["mode_label"] = "真实解析模式(规则解析·批量)"
            return rule_result

        exclude_keys = set(kwargs.get("exclude_template_keys", []) or [])

        prompt = self.render_prompt({"task_json": json.dumps(task, ensure_ascii=False)})
        if not prompt:
            return await self.execute_rule(task, **kwargs)

        try:
            data = await llm_client.chat_json(prompt)
            # 校验返回：包含 error 或 mock 视为不可用，回退规则模式
            if not isinstance(data, dict) or data.get("error") or data.get("mock"):
                rule_result = await self.execute_rule(task, **kwargs)
                rule_result["mode"] = "rule"
                rule_result["mode_label"] = "真实解析模式(规则解析)"
                return rule_result

            # 需求7修复：LLM 返回的 template_key 若在 exclude_keys 中，
            # 回退到 execute_rule（内部会从多模板池随机挑选一套未用过的）
            if exclude_keys and data.get("template_key") in exclude_keys:
                rule_result = await self.execute_rule(task, **kwargs)
                rule_result["mode"] = "rule"
                rule_result["mode_label"] = "真实解析模式(规则解析·模板切换)"
                return rule_result

            # 注入变量并标记来源
            data["variables"] = self._build_variables_with_defaults(task)
            data["reuse_source"] = data.get("reuse_source", "新生成")

            return {
                "success": True,
                "mode": "real",
                "mode_label": "真实解析模式(LLM)",
                "data_source": "合同原文(LLM深度解析)",
                "service": self.service_name,
                "data": data,
            }
        except Exception:
            # LLM 调用异常，回退规则模式
            rule_result = await self.execute_rule(task, **kwargs)
            rule_result["mode"] = "rule"
            rule_result["mode_label"] = "真实解析模式(规则解析)"
            return rule_result

    def _pick_from_pool(self, exclude_keys: set) -> dict:
        """从多模板池随机挑选一套模板，优先排除已用过的（需求7：随机刷新）

        若全部已用过，则清空排除列表允许复用，保证总能返回一套。
        """
        candidates = [t for t in MULTI_TEMPLATE_POOL if t["template_key"] not in exclude_keys]
        if not candidates:
            # 全用过，允许复用，但优先选最久未用的（按 MULTI_TEMPLATE_POOL 顺序即可）
            candidates = MULTI_TEMPLATE_POOL[:]
        return secrets.choice(candidates)

    def _generic_design(self, task: dict, exclude_keys: Optional[set] = None) -> dict:
        """通用设计：优先按 task_type 推断，未匹配时从多模板池随机挑选（需求7）

        exclude_keys：已使用过的 template_key 集合，重新生成时用于切换为另一套模板。
        """
        if exclude_keys is None:
            exclude_keys = set()

        task_name = task.get("task_name", "")
        task_type = task.get("task_type", "")
        service_module = task.get("service_module", "")

        # 根据任务类型推断默认 outline
        default_outline_map = {
            "客户资料": (["资料需求清单", "资料用途说明", "提交截止时间", "资料审核要点", "缺失资料跟进机制"],
                          "资料需求清单", "清单", "generic_document_list",
                          "该任务要求客户提供资料，生成资料清单可明确需求、提高效率、便于跟进。"),
            "会议沟通": (["会议基本信息", "会议议题与讨论内容", "双方达成的共识", "待落实事项与责任人", "下次会议安排"],
                          "会议纪要", "文档", "generic_meeting_minutes",
                          "会议类任务需形成纪要，确保双方对讨论内容和后续行动有一致理解。"),
            "交付验收": (["验收项目与内容", "交付物清单", "验收标准与结果", "存在问题与改进建议", "双方签字确认栏"],
                          "成果确认单", "确认函", "generic_confirmation",
                          "交付验收类任务必须形成书面确认，保障双方权益，明确责任边界。"),
            "服务执行": (["工作完成情况", "关键发现与分析", "存在问题与风险提示", "下一步工作计划", "需客户配合事项"],
                          "工作报告", "报告", "generic_work_report",
                          "服务执行类任务需形成工作报告，向客户展示工作成果和专业价值。"),
        }

        # 修复 Bug：原代码判断 "generic_" + task_type（中文 task_type），
        # 与 default_entry 中实际的 template_key（英文如 generic_meeting_minutes）不一致，
        # 导致即便已用过该默认模板，也无法排除。
        # 修复：用 default_entry 中实际的 template_key 判断。
        default_entry = default_outline_map.get(task_type)
        default_template_key = default_entry[3] if default_entry else None
        if default_entry and default_template_key not in exclude_keys:
            outline, default_name, d_type, template_key, reason = default_entry
            d_name = f"《{task_name}》{default_name}"
        else:
            # 从多模板池随机挑选一套未用过的（需求7：多模板随机轮换）
            picked = self._pick_from_pool(exclude_keys)
            outline = picked["outline"]
            d_type = picked["deliverable_type"]
            template_key = picked["template_key"]
            d_name = f"《{task_name}》{picked['template_name']}"
            reason = (
                f"为任务「{task_name}」应用「{picked['template_name']}」模板"
                f"，从多模板池随机轮换而来，刷新时可切换其他模板。"
            )

        # 通用设计也生成丰满内容
        content_sections = self._build_content_sections(task, outline, d_type)
        acceptance_criteria = self._build_acceptance_criteria(task, task_type)
        client_inputs = self._build_client_inputs(task, task_type)
        risk_notes = self._build_risk_notes(task, task_type)
        next_actions = self._build_next_actions(task, task_type)

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "合同原文",
            "service": self.service_name,
            "data": {
                "deliverable_name": d_name,
                "deliverable_type": d_type,
                "file_format": "docx",
                "template_key": template_key,
                "template_name": d_type,
                "ai_design_reason": reason,
                "content_outline": outline,
                "content_sections": content_sections,
                "acceptance_criteria": acceptance_criteria,
                "client_inputs": client_inputs,
                "risk_notes": risk_notes,
                "next_actions": next_actions,
                "variables": self._build_variables_with_defaults(task),
                "reusable": True,
                "reuse_source": "新生成",
            },
        }

    def _build_variables_with_defaults(self, task: dict) -> dict:
        """需求7：变量预填 - 所有变量填上建议值，用户只需微调

        相比 _extract_variables（仅提取原始字段），这里为缺失字段补上合理建议值。
        """
        variables = self._extract_variables(task)

        # 补充建议值（仅当原值为空时）
        if not variables.get("our_owner"):
            variables["our_owner"] = "乙方项目负责人（建议由咨询总监指派）"
        if not variables.get("client_contact"):
            variables["client_contact"] = "甲方财务负责人（建议由甲方书面指定）"
        if not variables.get("plan_start_date"):
            variables["plan_start_date"] = "合同签署日 + 7 个自然日"
        if not variables.get("plan_end_date"):
            variables["plan_end_date"] = "本服务模块完成节点 + 5 个工作日（验收期）"
        if not variables.get("milestone_goal"):
            variables["milestone_goal"] = "完成本任务约定的交付物并通过客户验收"
        if not variables.get("deliverables"):
            variables["deliverables"] = "本任务对应模块的成果文件（电子版 docx/pdf + 必要时纸质版）"

        # 补充额外建议字段（不强制，便于模板渲染时使用）
        variables.setdefault("project_period", "12 个月（按合同服务期限）")
        variables.setdefault("review_cycle", "每月一次进度评审 + 每季度阶段评审")
        variables.setdefault("acceptance_period", "5 个工作日内完成验收并书面确认")
        variables.setdefault("feedback_period", "3 个工作日内反馈书面意见")
        variables.setdefault("deliverable_format", "电子版 docx/pdf，必要时提供加盖公章的纸质版")
        variables.setdefault("archive_rule", "项目台账归档，保留至项目结束后 5 年")

        return variables

    def _build_content_sections(self, task: dict, outline: list, template_name: str) -> list:
        """基于任务实际信息构建内容章节，每章节含标题和 2-5 条正文要点。

        要点来源于任务的 service_module / milestone_goal / deliverables / client_requirements /
        next_action / ai_extraction_basis 等字段，确保每个任务的文档内容有差异。
        """
        task_name = task.get("task_name", "")
        service_module = task.get("service_module", "")
        task_type = task.get("task_type", "")
        milestone_goal = str(task.get("milestone_goal", ""))
        deliverables = str(task.get("deliverables", ""))
        client_req = str(task.get("client_requirements", ""))
        next_action = str(task.get("next_action", ""))
        our_owner = task.get("our_owner", "项目顾问")
        plan_start = task.get("plan_start_date", "")
        plan_end = task.get("plan_end_date", "")
        extraction_basis = str(task.get("ai_extraction_basis", ""))

        sections = []
        for section_title in outline:
            bullets = []
            title_lower = section_title

            if "基本信息" in title_lower or "任务信息" in title_lower:
                bullets.append(f"任务名称：{task_name}")
                bullets.append(f"所属服务模块：{service_module}")
                bullets.append(f"任务类型：{task_type}")
                bullets.append(f"负责顾问：{our_owner}")
                if plan_start or plan_end:
                    bullets.append(f"计划周期：{plan_start} 至 {plan_end}")
            elif "资料" in title_lower and "需求" in title_lower:
                if deliverables and deliverables != "待明确":
                    bullets.append(f"本任务需交付：{deliverables}")
                if client_req and client_req != "待明确":
                    bullets.append(f"客户需提供：{client_req}")
                bullets.append("资料提交后由顾问在 2 个工作日内完成审核并反馈意见")
                bullets.append("如资料缺失或不符，将通过邮件书面跟进，并记录在项目台账")
            elif "用途" in title_lower:
                bullets.append(f"本资料用于支撑「{service_module}」模块的{task_type}工作")
                if milestone_goal and milestone_goal != "待明确":
                    bullets.append(f"对应里程碑目标：{milestone_goal}")
                bullets.append("资料将作为后续交付成果的输入依据，并归档备查")
            elif "截止" in title_lower or "时间" in title_lower or "节点" in title_lower:
                if plan_end:
                    bullets.append(f"截止时间：{plan_end}")
                else:
                    bullets.append("截止时间：依据项目整体计划确定，由项目经理书面通知")
                bullets.append("如遇节假日顺延至下一个工作日")
                bullets.append("提前 3 个工作日提醒客户提交")
            elif "审核" in title_lower or "验收" in title_lower or "标准" in title_lower:
                bullets.append("内容完整性：覆盖任务要求的全部要点，无遗漏")
                bullets.append("数据准确性：关键数据与客户提供的原始资料一致")
                bullets.append("格式规范：符合本模板结构与字段要求，便于归档")
                bullets.append("由项目顾问与客户对接人共同确认后方可归档")
            elif "会议" in title_lower or "议题" in title_lower or "讨论" in title_lower:
                bullets.append(f"会议主题：{task_name}")
                bullets.append(f"讨论范围：{service_module} 模块相关事项")
                if milestone_goal and milestone_goal != "待明确":
                    bullets.append(f"重点关注：{milestone_goal}")
                bullets.append("由顾问提前 2 个工作日发送议程与资料")
            elif "共识" in title_lower or "结论" in title_lower:
                bullets.append("记录双方达成一致的关键结论，逐条列示")
                bullets.append("对未达成一致的事项，记录分歧点与下一步处理建议")
                bullets.append("结论需双方签字或邮件确认后生效")
            elif "待落实" in title_lower or "下一步" in title_lower or "行动" in title_lower:
                if next_action and next_action != "待明确":
                    bullets.append(f"顾问下一步：{next_action}")
                else:
                    bullets.append("顾问下一步：根据本任务结论制定执行计划并推进")
                bullets.append(f"客户配合：{client_req if client_req and client_req != '待明确' else '按顾问要求提供必要资料与反馈'}")
                bullets.append("责任人与截止时间在会议结束后 2 个工作日内确认")
            elif "风险" in title_lower or "问题" in title_lower:
                bullets.append("如客户资料延迟提交，将影响后续任务排期，需提前预警")
                bullets.append("如关键数据存在歧义，以书面方式与客户确认后再行使用")
                if task_type == "交付验收":
                    bullets.append("验收不合格项需明确整改责任人与完成时限")
            elif "完成情况" in title_lower or "工作内容" in title_lower or "发现" in title_lower:
                if deliverables and deliverables != "待明确":
                    bullets.append(f"已完成工作：{deliverables}")
                else:
                    bullets.append(f"已完成工作：{task_name} 相关的{service_module}服务内容")
                if milestone_goal and milestone_goal != "待明确":
                    bullets.append(f"对应节点目标：{milestone_goal}")
                bullets.append("工作过程严格遵循合同约定的工作范围与服务标准")
                bullets.append("关键发现与分析已结合客户实际情况给出专业建议")
            elif "交付" in title_lower and "清单" in title_lower:
                if deliverables and deliverables != "待明确":
                    bullets.append(f"交付物：{deliverables}")
                else:
                    bullets.append(f"交付物：{task_name} 成果文件")
                bullets.append("交付形式：电子版 docx/pdf，必要时提供纸质版")
                bullets.append("交付时间：依据项目计划节点")
            elif "签字" in title_lower or "确认" in title_lower:
                bullets.append("顾问签字：________________  日期：________")
                bullets.append("客户签字：________________  日期：________")
                bullets.append("本确认单一式两份，双方各执一份")
            elif "跟进" in title_lower or "缺失" in title_lower:
                bullets.append("建立资料跟进台账，记录每次催办时间与反馈")
                bullets.append("超过截止时间 3 个工作日未提交，升级至项目经理跟进")
                bullets.append("资料补齐后及时更新任务状态并通知相关人员")
            elif "安排" in title_lower:
                bullets.append("下次会议时间：双方协商后由顾问书面通知")
                bullets.append("下次会议议题：基于本次结论与待落实事项确定")
            else:
                # 兜底：用任务实际字段填充
                bullets.append(f"本章节对应「{section_title}」，围绕{task_name}展开")
                if milestone_goal and milestone_goal != "待明确":
                    bullets.append(f"节点目标：{milestone_goal}")
                if extraction_basis:
                    bullets.append(f"依据：{extraction_basis[:120]}")
                bullets.append(f"所属模块：{service_module}")
                bullets.append(f"交付成果：{deliverables if deliverables and deliverables != '待明确' else task_name + '相关成果文件'}")
                bullets.append(f"客户配合：{client_req if client_req and client_req != '待明确' else '按合同约定提供必要资料与反馈'}")
                bullets.append(f"下一步：{next_action if next_action and next_action != '待明确' else '依据项目计划推进'}")

            sections.append({
                "title": section_title,
                "bullets": bullets[:5],  # 最多 5 条
            })
        return sections

    def _build_acceptance_criteria(self, task: dict, task_type: str) -> list:
        """构建验收标准"""
        deliverables = str(task.get("deliverables", ""))
        criteria = []
        if deliverables and deliverables != "待明确":
            criteria.append(f"交付物完整覆盖：{deliverables}")
        criteria.append("内容完整性：覆盖本任务全部约定要点")
        criteria.append("数据准确性：与客户原始资料一致，无关键错误")
        criteria.append("格式规范：符合模板结构与归档要求")
        if task_type == "交付验收":
            criteria.append("双方书面签字确认")
        return criteria[:5]

    def _build_client_inputs(self, task: dict, task_type: str) -> list:
        """构建客户需提供的资料"""
        client_req = str(task.get("client_requirements", ""))
        inputs = []
        if client_req and client_req != "待明确":
            inputs.append(client_req)
        if task_type == "客户资料":
            inputs.append("资料需为最新版本，加盖公章或经授权人签字")
        elif task_type == "会议沟通":
            inputs.append("确认参会人员与会议时间")
            inputs.append("提前审阅顾问发送的议程与背景资料")
        elif task_type == "交付验收":
            inputs.append("安排授权人参与验收并签字确认")
        else:
            inputs.append("按顾问要求提供必要的背景资料与反馈")
        inputs.append("对顾问提交的成果在 3 个工作日内给出书面反馈")
        return inputs[:5]

    def _build_risk_notes(self, task: dict, task_type: str) -> list:
        """构建风险提示"""
        notes = []
        notes.append("如客户资料延迟提交，后续任务排期将相应顺延")
        notes.append("关键数据存在歧义时，以书面确认结果为准")
        if task_type == "交付验收":
            notes.append("验收不合格项需明确整改责任人与完成时限")
        if task_type == "服务执行":
            notes.append("工作范围以合同约定为准，超范围事项需另行确认")
        notes.append("本成果为初稿，最终内容以双方确认版本为准")
        return notes[:4]

    def _build_next_actions(self, task: dict, task_type: str) -> list:
        """构建下一步动作"""
        next_action = str(task.get("next_action", ""))
        actions = []
        if next_action and next_action != "待明确":
            actions.append(next_action)
        else:
            actions.append("顾问根据本任务结论制定执行计划并推进")
        actions.append("客户按约定提供资料或反馈")
        actions.append("双方确认成果后归档至项目台账")
        return actions[:4]

    def _extract_variables(self, task: dict) -> dict:
        """从任务中提取变量"""
        return {
            "customer_name": task.get("customer_name", ""),
            "project_name": task.get("project_name", ""),
            "task_name": task.get("task_name", ""),
            "service_module": task.get("service_module", ""),
            "task_type": task.get("task_type", ""),
            "our_owner": task.get("our_owner", ""),
            "client_contact": task.get("client_contact", ""),
            "plan_start_date": task.get("plan_start_date", ""),
            "plan_end_date": task.get("plan_end_date", ""),
            "milestone_goal": task.get("milestone_goal", ""),
            "deliverables": task.get("deliverables", ""),
        }


# 全局实例
deliverable_design_service = DeliverableDesignService()
