"""
年度服务计划识别服务
"""
import re
from datetime import datetime

from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


class PlanRecognitionService(AIServiceBase):
    """年度服务计划识别服务"""

    service_name = "plan_recognition"
    mock_filename = "plan_result.json"
    prompt_name = "plan_recognition"

    # ---------- 规则解析：结构化提取 ----------
    def _normalize_date(self, raw: str) -> str:
        """归一化日期文本，支持 2026年3月、3月、Q1、第一季度等"""
        if not raw:
            return ""
        s = raw.strip()
        # 2026年3月 / 2026-03
        m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", s)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}"
        m = re.search(r"(\d{4})-(\d{1,2})", s)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}"
        # 季度
        qm = re.search(r"第\s*([一二三四1-4])\s*季度|^Q\s*([1-4])", s)
        if qm:
            num_map = {"一": 1, "二": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3, "4": 4}
            q = num_map.get(qm.group(1) or qm.group(2))
            if q:
                return f"第{['一','二','三','四'][q-1]}季度"
        return s

    def _parse_frequency(self, text: str) -> str:
        """识别服务频次"""
        if not text:
            return ""
        if re.search(r"每周|每周一次|周度", text):
            return "每周"
        if re.search(r"每月|月度|月度一次", text):
            return "每月"
        if re.search(r"每季度|季度|每季", text):
            return "每季度"
        if re.search(r"每半年|半年度", text):
            return "每半年"
        if re.search(r"每年|年度|每年一次", text):
            return "每年"
        if re.search(r"驻场|现场服务", text):
            return "驻场（按季度）"
        return ""

    def _extract_sections(self, plan_text: str) -> list:
        """按一级章节切分计划文本，便于按模块结构化提取"""
        # 一级标题特征：数字编号开头 / 关键词 + 冒号
        lines = plan_text.splitlines()
        sections: list[dict] = []
        current_title = "导言"
        current_lines: list[str] = []

        title_patterns = [
            r"^\s*[一二三四五六七八九十]+[、\.\s]",
            r"^\s*\d+[、\.\s]",
            r"^\s*[（(]\s*[一二三四五六七八九十\d]+\s*[)）]",
            r"^\s*(服务内容|服务模块|服务事项|工作内容|工作计划|实施计划|阶段安排|服务阶段|服务频次|交付成果|客户配合|时间安排|进度安排|项目周期|人员安排|风险与应对|质量管理|服务承诺|驻场安排|沟通机制)\s*[:：]",
        ]

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            is_title = any(re.search(p, stripped) for p in title_patterns)
            # 短行（<30字符）且以冒号或编号结尾，视为标题
            if is_title or (len(stripped) < 30 and stripped.endswith(("：", ":"))):
                if current_lines:
                    sections.append({"title": current_title, "text": "\n".join(current_lines)})
                current_title = stripped
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections.append({"title": current_title, "text": "\n".join(current_lines)})
        return sections

    def _extract_modules(self, sections: list, lines: list) -> list:
        """提取服务模块/工作内容，含模块名、依据、所属阶段"""
        module_keywords = r"(模块|阶段|专题|服务事项|工作内容|服务内容|实施内容|工作计划)"
        rows = []
        seen = set()

        # 优先从章节标题中提取模块
        for sec in sections:
            title = sec["title"]
            if re.search(module_keywords, title) or re.search(r"^\s*\d+[、\.\s]", title):
                # 提取模块名：去掉前缀编号
                name = re.sub(r"^\s*[一二三四五六七八九十\d]+[、\.\s（(]*[^）)]*[)）]*\s*", "", title).strip()
                name = name.rstrip("：:").strip()
                if name and name not in seen and len(name) < 60:
                    seen.add(name)
                    rows.append({
                        "服务模块/工作内容": name,
                        "所属阶段": "",
                        "依据摘要": title,
                    })

        # 从正文中补充提取
        for line in lines:
            if re.search(module_keywords, line):
                # 提取冒号后的内容
                m = re.search(r"(模块|阶段|专题|服务事项|工作内容|服务内容|实施内容)\s*[:：]\s*(.+)", line)
                if m:
                    name = m.group(2).strip()
                    if name and name not in seen and len(name) < 80:
                        seen.add(name)
                        rows.append({
                            "服务模块/工作内容": name,
                            "所属阶段": "",
                            "依据摘要": line[:80],
                        })

        return rows[:30]

    def _extract_milestones(self, lines: list, sections: list) -> list:
        """提取阶段节点：日期 + 事项 + 频次"""
        date_patterns = [
            r"(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*初|中|底)?)",
            r"(\d{4}-\d{1,2}(?:-\d{1,2})?)",
            r"(第\s*[一二三四1-4]\s*季度)",
            r"(Q\s*[1-4])",
            r"(\d{1,2}\s*月\s*底)",
            r"(\d{1,2}\s*月\s*\d{1,2}\s*日)",
        ]
        rows = []
        seen = set()
        for line in lines:
            for pat in date_patterns:
                m = re.search(pat, line)
                if m:
                    raw_date = m.group(1)
                    norm_date = self._normalize_date(raw_date)
                    # 事项：去掉日期部分后的剩余文本
                    event = re.sub(pat, "", line).strip(" :：、-")
                    event = re.sub(r"^[·•\-\*]+\s*", "", event)
                    if not event:
                        event = line[:60]
                    freq = self._parse_frequency(line)
                    key = f"{norm_date}__{event[:40]}"
                    if key not in seen:
                        seen.add(key)
                        rows.append({
                            "阶段节点": norm_date,
                            "事项": event[:100],
                            "服务频次": freq,
                            "依据摘要": line[:80],
                        })
                    break  # 一行只取一个日期
        return rows[:30]

    def _extract_client_data(self, lines: list) -> list:
        """提取客户需提供的资料/配合事项"""
        rows = []
        seen = set()
        for line in lines:
            if re.search(r"(客户|甲方|提供|配合|确认|资料|清单|数据|披露|配合事项)", line):
                # 跳过纯合同条款句式
                if re.search(r"乙方(应|应当|需|负责)", line) and not re.search(r"甲方|客户", line):
                    continue
                name = re.sub(r"^\s*[·•\-\*\d]+[、\.\s]*", "", line).strip()
                if not name:
                    name = line.strip()
                if name and name not in seen and len(name) < 120:
                    seen.add(name)
                    # 推断提交时间
                    date_m = re.search(r"(\d{4}\s*年\s*\d{1,2}\s*月|第\s*[一二三四1-4]\s*季度|\d{1,2}\s*月\s*底)", line)
                    submit_time = self._normalize_date(date_m.group(1)) if date_m else ""
                    rows.append({
                        "客户资料或配合事项": name[:100],
                        "建议提交时间": submit_time,
                        "依据摘要": line[:80],
                    })
        return rows[:25]

    def _extract_meetings(self, lines: list) -> list:
        """提取会议/沟通安排：类型、频次、参与方"""
        rows = []
        seen = set()
        for line in lines:
            if re.search(r"(会议|沟通|汇报|复盘|启动会|周报|月报|季度报告|例会|对接)", line):
                meeting_type = ""
                if re.search(r"启动会", line):
                    meeting_type = "启动会"
                elif re.search(r"周报|周例会", line):
                    meeting_type = "周例会"
                elif re.search(r"月报|月度例会", line):
                    meeting_type = "月度例会"
                elif re.search(r"季度|季报", line):
                    meeting_type = "季度评审会"
                elif re.search(r"复盘", line):
                    meeting_type = "复盘会"
                else:
                    meeting_type = "沟通会议"
                freq = self._parse_frequency(line)
                name = re.sub(r"^\s*[·•\-\*\d]+[、\.\s]*", "", line).strip()
                key = f"{meeting_type}__{freq}__{name[:30]}"
                if key not in seen and name:
                    seen.add(key)
                    rows.append({
                        "会议类型": meeting_type,
                        "服务频次": freq,
                        "会议或确认事项": name[:100],
                        "依据摘要": line[:80],
                    })
        return rows[:20]

    def _extract_deliverables(self, lines: list) -> list:
        """提取计划中承诺的交付物清单"""
        rows = []
        seen = set()
        for line in lines:
            if re.search(r"(交付物|交付成果|成果文件|输出物|报告|清单|方案|底稿)", line):
                name = re.sub(r"^\s*[·•\-\*\d]+[、\.\s]*", "", line).strip()
                if not name:
                    continue
                if name in seen:
                    continue
                seen.add(name)
                # 提取交付时间
                date_m = re.search(r"(\d{4}\s*年\s*\d{1,2}\s*月|第\s*[一二三四1-4]\s*季度|\d{1,2}\s*月\s*底)", line)
                deliver_time = self._normalize_date(date_m.group(1)) if date_m else ""
                rows.append({
                    "交付物": name[:80],
                    "计划交付时间": deliver_time,
                    "依据摘要": line[:80],
                })
        return rows[:25]

    def _extract_responsible(self, lines: list) -> list:
        """提取责任人/对接人安排"""
        rows = []
        seen = set()
        for line in lines:
            if re.search(r"(负责人|责任人|对接人|项目对接|项目经理|项目主管|带队|主办)", line):
                role_m = re.search(r"(项目负责人|项目责任人|对接人|项目经理|项目主管|带队|主办)", line)
                role = role_m.group(1) if role_m else "对接人"
                desc = re.sub(r"^\s*[·•\-\*\d]+[、\.\s]*", "", line).strip()
                if desc and desc not in seen:
                    seen.add(desc)
                    rows.append({
                        "角色": role,
                        "安排说明": desc[:100],
                        "依据摘要": line[:80],
                    })
        return rows[:10]

    def _extract_plan_summary(self, plan_text: str, sections: list) -> dict:
        """提取计划层面的总体摘要：项目周期、服务频次、驻场安排"""
        text = plan_text

        # 项目周期
        period = ""
        m = re.search(r"(\d{4}\s*年\s*\d{1,2}\s*月|\d{4}-\d{1,2})\s*[至到\-~]\s*(\d{4}\s*年\s*\d{1,2}\s*月|\d{4}-\d{1,2})", text)
        if m:
            period = f"{self._normalize_date(m.group(1))} 至 {self._normalize_date(m.group(2))}"
        elif re.search(r"(十二|12)\s*个月|一年|年度", text):
            period = "12 个月（年度服务）"

        # 总体服务频次
        freq = self._parse_frequency(text) or ""

        # 驻场安排
        onsite = ""
        m = re.search(r"(每季度[^\n。；,，]*?(?:现场|驻场|工作日)[^\n。；,，]*)", text)
        if m:
            onsite = m.group(1)
        elif re.search(r"驻场|现场服务", text):
            onsite = "约定驻场（具体安排见条款）"

        return {
            "项目周期": period,
            "总体服务频次": freq,
            "驻场安排": onsite,
        }

    async def execute_rule(self, plan_text: str = "", **kwargs) -> dict:
        """规则解析模式：结构化提取完整字段

        输出字段对齐需求：服务模块、阶段节点（含日期+事项+频次）、
        客户资料/配合事项（含提交时间）、会议/沟通安排（含类型+频次）、
        交付物清单（含交付时间）、责任人安排、计划总体摘要
        """
        if not plan_text or not plan_text.strip():
            return {
                "success": False,
                "mode": "rule",
                "mode_label": "真实解析模式(规则解析)",
                "data_source": "计划原文",
                "service": self.service_name,
                "message": "计划文本为空",
            }
        filename = kwargs.get("filename", "")
        lines = [line.strip() for line in plan_text.splitlines() if line.strip()]
        sections = self._extract_sections(plan_text)

        service_modules = self._extract_modules(sections, lines)
        milestones = self._extract_milestones(lines, sections)
        client_data = self._extract_client_data(lines)
        meetings = self._extract_meetings(lines)
        deliverables = self._extract_deliverables(lines)
        responsible = self._extract_responsible(lines)
        plan_summary = self._extract_plan_summary(plan_text, sections)

        # 待确认事项：仅当关键字段都为空时给出
        pending_items = []
        if not service_modules and not milestones:
            pending_items.append({
                "待确认事项": "年度服务计划未提取到明确模块或阶段节点",
                "原因": "规则解析未命中模块、阶段、日期等关键词，可能计划文本结构特殊",
                "建议向谁确认": "项目负责人",
                "不确认的影响": "任务拆分将缺少年度计划维度，需补充计划原文或人工确认",
            })
        if not deliverables:
            pending_items.append({
                "待确认事项": "计划未明确列出交付物清单",
                "原因": "未匹配到「交付物/成果文件/报告」等关键词",
                "建议向谁确认": "项目负责人",
                "不确认的影响": "交付成果归档将基于合同条款推断，可能与计划存在偏差",
            })
        if not plan_summary.get("项目周期"):
            pending_items.append({
                "待确认事项": "计划未明确项目起止周期",
                "原因": "未匹配到「YYYY年MM月 至 YYYY年MM月」或「十二个月」等周期表述",
                "建议向谁确认": "甲乙双方项目负责人",
                "不确认的影响": "任务排期缺少整体时间基准",
            })

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "计划原文",
            "service": self.service_name,
            "data": {
                "source_file": filename,
                "plan_summary": plan_summary,
                "service_modules": service_modules,
                "milestones": milestones,
                "client_data": client_data,
                "meetings": meetings,
                "deliverables": deliverables,
                "responsible_parties": responsible,
                "pending_items": pending_items,
                "raw_text": plan_text[:500],
                "parsed_at": datetime.now().isoformat(),
            },
        }

    async def execute_real(self, plan_text: str = "", **kwargs) -> dict:
        """真实模式：调用 LLM 进行计划识别

        需求3修复：LLM 返回结果可能字段不完整（缺 milestones/deliverables 等），
        用规则模式结果补全缺失字段，保证输出结构一致且完整。
        """
        prompt = self.render_prompt({"年度服务计划文本": plan_text})
        if not prompt:
            return await self.execute_rule(plan_text=plan_text, **kwargs)
        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            return await self.execute_rule(plan_text=plan_text, **kwargs)

        # 需求3修复：用规则模式补全 LLM 缺失的结构化字段
        rule_result = await self.execute_rule(plan_text=plan_text, **kwargs)
        rule_data = rule_result.get("data", {}) if rule_result.get("success") else {}

        # 关键结构化字段清单：若 LLM 未返回或为空，则用规则模式结果补全
        fallback_fields = [
            "plan_summary", "service_modules", "milestones",
            "client_data", "meetings", "deliverables",
            "responsible_parties", "pending_items",
        ]
        for field in fallback_fields:
            llm_val = result.get(field)
            if not llm_val and rule_data.get(field):
                result[field] = rule_data[field]

        # 兜底字段
        result.setdefault("source_file", kwargs.get("filename", ""))
        result.setdefault("raw_text", plan_text[:500] if plan_text else "")
        result.setdefault("parsed_at", datetime.now().isoformat())

        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"计划原文(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": result,
        }


# 全局实例
plan_recognition_service = PlanRecognitionService()
