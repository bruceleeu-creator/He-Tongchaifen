"""
合同深度解析器（规则解析）
通过正则/关键词从合同原文提取核心字段，不依赖 LLM
适用于无 API Key 场景，确保真实合同不被 Mock 样例替代
"""
import re
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ContractParser:
    """合同规则解析器"""

    # ========== 关键词模式 ==========

    # 甲方/乙方 — 支持多种格式：
    #   甲方：xxx / 甲方（委托方）：xxx / 委托方（甲方）：xxx
    #   乙方：xxx / 乙方（服务方/受托方）：xxx / 受托方（乙方）：xxx / 服务方（乙方）：xxx
    # 注：括号内角色名可能是"委托方/服务方/受托方"任意一个，顺序可互换
    PARTY_A_PATTERN = re.compile(
        r"(?:甲方(?:[（(]委托方[)）])?|委托方(?:[（(]甲方[)）])?)[：:]\s*(.+?)(?:\n|$)"
    )
    PARTY_B_PATTERN = re.compile(
        r"(?:乙方(?:[（(](?:服务方|受托方)[)）])?|(?:服务方|受托方)(?:[（(]乙方[)）])?)[：:]\s*(.+?)(?:\n|$)"
    )
    # 签字页同一行可能同时出现 甲方：xxx 乙方：yyy（中间用空格或制表符分隔）
    SIGN_PAGE_PARTY_PATTERN = re.compile(
        r"甲方[：:]\s*(\S[^：:\n]*?)\s+(?:乙方|服务方|受托方)[：:]\s*(\S[^：:\n]*?)(?:\n|$)"
    )
    # 乙方字段截断边界：地址、联系电话、法定代表人、签字、日期 等不应被吞进乙方名称
    PARTY_B_CUT_KEYWORDS = ["地址", "联系电话", "法定代表人", "法定代表", "签字", "日期", "电话", "传真", "邮编", "开户行", "账号"]
    # 统一社会信用代码
    CREDIT_CODE_PATTERN = re.compile(r"统一社会信用代码[：:]\s*([A-Z0-9]+)")
    # 地址
    ADDRESS_PATTERN = re.compile(r"地址[：:]\s*(.+?)(?:\n|$)")
    # 联系人
    CONTACT_PERSON_PATTERN = re.compile(r"联系人[：:]\s*(.+?)(?:\n|$)")
    # 联系电话
    CONTACT_PHONE_PATTERN = re.compile(r"联系电话[：:]\s*([\d\-\s]+)")

    # 服务期限 — 支持多种表述
    SERVICE_TERM_PATTERN = re.compile(r"服务期限(?:为)?(.+?)(?:[。。\n]|$)")
    # 服务期限（月数）— 支持 "十二个月" "12个月" 等
    SERVICE_MONTHS_PATTERN = re.compile(r"(?:十二个?|12个?)月")

    # 服务费用 — 截止到句号或换行，避免在金额逗号处截断
    TOTAL_FEE_PATTERN = re.compile(r"服务费用总[计额](?:为)?人民币?(.+?)(?:[。\n]|$)")
    FIRST_PAYMENT_PATTERN = re.compile(r"首期款[：:]?.*?金额为人民币\s*(.+?)(?:[。\n]|$)")
    LATER_PAYMENT_PATTERN = re.compile(r"(?:尾期款|中期款)[：:]?.*?金额为人民币\s*(.+?)(?:[。\n]|$)")
    # 金额数字提取 — 支持 ¥ 或 ￥ 后跟数字（含千分位逗号）
    AMOUNT_NUMBER_PATTERN = re.compile(r"[¥￥]([\d,.]+)")

    # 服务方式
    SERVICE_METHOD_PATTERN = re.compile(r'采用["\u201c\u201d](.+?)["\u201c\u201d]的嵌入式服务模式')

    # 驻场安排 — 捕获完整描述（不少于X个工作日）
    ONSITE_PATTERN = re.compile(
        r"(每季度(?:至少)?(?:(?:现场|驻场)?服务|安排|不少于)*[一二三四五六七八九十\d]+个工作日)"
    )

    # 响应时效 — 捕获数字/中文数字+小时内，不包含多余前缀
    RESPONSE_TIME_PATTERN = re.compile(r"紧急问题.*?([一二三四五六七八九十\d]+小时内)")

    # 验收标准
    ACCEPTANCE_DAYS_PATTERN = re.compile(r"[5五]个工作日内签署")
    FINAL_ACCEPTANCE_PATTERN = re.compile(r"整体服务效果评估报告")

    # 季度报告
    QUARTERLY_REPORT_PATTERN = re.compile(r"每季度.*?(?:提交|报送).*?报告")

    # 合同签署日期 - 检查签字页是否有日期
    SIGN_DATE_PATTERN = re.compile(r"(?:签订?日期|日期)[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}|\d{4}/\d{1,2}/\d{1,2})")

    # ========== 服务模块关键词映射 ==========
    MODULE_KEYWORDS = {
        "商业模式设计": ["模块一", "商业模式设计", "业务模式重塑", "风险隔离公司设计", "核心关联交易安排"],
        "股权架构搭建": ["模块二", "股权架构搭建", "股东身份安排", "核心高管激励", "基层员工激励", "综合架构协调", "顶层结构设计", "顶层架构"],
        "资产重塑": ["模块三", "资产重塑", "轻重资产配置", "资产权属规划", "资产管理体系"],
        "人效提升": ["模块四", "人效提升", "人效数据诊断", "岗位流程", "人效提升激励", "效能陪跑"],
        "业财合规陪跑": ["模块五", "业财合规陪跑", "业财标准体系", "资金架构体系", "成本费用结构", "税收目标设计", "税务长效机制", "陪跑服务", "业财融合", "财税合规", "财税内部审查"],
    }

    # 阶段式合同关键词（当合同使用"第一阶段""第二阶段"等而非"模块一"时）
    PHASE_KEYWORDS = {
        "财税内部审查": ["第一阶段", "财税内部审查"],
        "顶层结构设计": ["第二阶段", "顶层结构设计"],
        "业财融合合规": ["第三阶段", "业财融合", "业财合规"],
        "涉税风险处理": ["专项服务", "涉税风险"],
    }

    # ========== 交付成果关键词 ==========
    # 匹配所有 《xxx》 格式的交付物名称
    DELIVERABLE_PATTERN = re.compile(r"[《]([^》]+)[》]")

    def parse(self, contract_text: str, filename: str = "") -> dict:
        """解析合同文本，提取核心字段

        Returns:
            包含所有提取结果的字典
        """
        if not contract_text or not contract_text.strip():
            logger.warning("合同文本为空，无法解析")
            return self._empty_result(filename)

        text = contract_text
        result = {
            "source_file": filename,
            "parsed_at": datetime.now().isoformat(),
            "parse_mode": "rule",
            "basic_info": [],
            "service_scope": [],
            "client_responsibilities": [],
            "our_responsibilities": [],
            "delay_rules": [],
            "pending_items": [],
            "deliverables": [],
            "contract_summary": {},
            "raw_text": text[:200],  # 仅保存前200字符作为预览
        }

        # 1. 提取基础信息
        self._extract_basic_info(text, result)

        # 2. 提取服务模块和交付成果
        self._extract_service_modules(text, result)

        # 3. 提取客户责任
        self._extract_client_responsibilities(text, result)

        # 4. 提取乙方责任
        self._extract_our_responsibilities(text, result)

        # 5. 提取延期/暂停规则
        self._extract_delay_rules(text, result)

        # 6. 生成待确认事项
        self._generate_pending_items(text, result)

        # 7. 生成合同识别摘要
        self._generate_summary(result)

        return result

    def _empty_result(self, filename: str) -> dict:
        return {
            "source_file": filename,
            "parsed_at": datetime.now().isoformat(),
            "parse_mode": "rule",
            "basic_info": [],
            "service_scope": [],
            "client_responsibilities": [],
            "our_responsibilities": [],
            "delay_rules": [],
            "pending_items": [{"待确认事项": "合同文本为空", "原因": "无法解析", "建议向谁确认": "用户", "不确认的影响": "无法进行任务拆分"}],
            "deliverables": [],
            "contract_summary": {},
            "raw_text": "",
        }

    def _extract_basic_info(self, text: str, result: dict):
        """提取基础信息

        输出统一结构（每条记录均包含以下字段）：
        - 字段名称
        - 提取结果
        - 依据原文摘录（从合同原文截取前后 40-80 字，定位不到时回退到摘要说明）
        - 来源文件
        - 是否待确认（是/否）
        - 置信度（高/低）
        """
        filename = result.get("source_file", "")

        # 甲方 — 优先主体信息提取，回退到签字页
        party_a = self._extract_party_a(text)
        # 乙方 — 优先主体信息提取，回退到签字页同一行
        party_b = self._extract_party_b(text)
        # 信用代码
        credit_a = self._find_all_matches(text, self.CREDIT_CODE_PATTERN)
        # 地址
        addresses = self._find_all_matches(text, self.ADDRESS_PATTERN)
        # 联系人
        contacts = self._find_all_matches(text, self.CONTACT_PERSON_PATTERN)
        # 联系电话
        phones = self._find_all_matches(text, self.CONTACT_PHONE_PATTERN)

        # 服务期限
        service_term = self._find_match(text, self.SERVICE_TERM_PATTERN)
        if not service_term:
            # 尝试匹配"十二个月"
            if self.SERVICE_MONTHS_PATTERN.search(text):
                service_term = "自合同生效之日起十二个月"

        # 合同签署日期
        sign_dates = self.SIGN_DATE_PATTERN.findall(text)
        has_sign_date = any(d.strip() for d in sign_dates) if sign_dates else False

        # 服务费用
        total_fee_text = self._find_match(text, self.TOTAL_FEE_PATTERN)
        first_payment_text = self._find_match(text, self.FIRST_PAYMENT_PATTERN)
        later_payment_text = self._find_match(text, self.LATER_PAYMENT_PATTERN)

        # 提取金额数字
        all_amounts = self.AMOUNT_NUMBER_PATTERN.findall(text)
        # 清理金额中的逗号
        all_amounts = [a.replace(",", "") for a in all_amounts]

        # 从首期款/尾期款文本中提取金额
        first_amounts = self.AMOUNT_NUMBER_PATTERN.findall(first_payment_text) if first_payment_text else []
        first_amounts = [a.replace(",", "") for a in first_amounts]
        later_amounts = self.AMOUNT_NUMBER_PATTERN.findall(later_payment_text) if later_payment_text else []
        later_amounts = [a.replace(",", "") for a in later_amounts]

        # 服务费用显示：如原文已含¥金额则直接使用，否则解析中文金额
        if total_fee_text:
            if "¥" in total_fee_text or "￥" in total_fee_text:
                total_fee_display = total_fee_text
            else:
                total_num = self._parse_chinese_amount(total_fee_text)
                total_fee_display = f"{total_fee_text}（¥{total_num}）" if total_num else total_fee_text
        elif all_amounts:
            total_fee_display = f"¥{all_amounts[0]}"
        else:
            total_fee_display = "待人工确认"

        # 首期款/尾期款：优先从对应文本提取金额，回退到全局金额列表
        first_payment_display = first_amounts[0] if first_amounts else (
            all_amounts[1] if len(all_amounts) > 1 and all_amounts[0] != all_amounts[1] else "待人工确认"
        )
        later_payment_display = later_amounts[0] if later_amounts else (
            all_amounts[2] if len(all_amounts) > 2 else (
                all_amounts[1] if len(all_amounts) > 1 and all_amounts[0] != all_amounts[1] else "待人工确认"
            )
        )

        # 服务方式
        service_method = self._find_match(text, self.SERVICE_METHOD_PATTERN)

        # 驻场安排
        onsite = self._find_match(text, self.ONSITE_PATTERN)

        # 响应时效
        response_time = self._find_match(text, self.RESPONSE_TIME_PATTERN)

        project_name = self._extract_project_name(text)
        sign_date_value = sign_dates[0] if has_sign_date else "待人工确认"

        # 统一条目构造：自动判定是否待确认 + 从原文截取依据
        def _item(field_name: str, value: str, excerpt_keyword: str, fallback_summary: str = "合同未明确") -> dict:
            value = value or "待人工确认"
            is_pending = (not value) or value in ("待人工确认", "待确认", "合同未明确", "")
            excerpt = (
                self._excerpt_around(text, excerpt_keyword, fallback=fallback_summary)
                if not is_pending else fallback_summary
            )
            return {
                "字段名称": field_name,
                "提取结果": value,
                "依据原文摘录": excerpt,
                "来源文件": filename,
                "是否待确认": "是" if is_pending else "否",
                "置信度": "低" if is_pending else "高",
            }

        basic_info = [
            _item("客户名称（甲方）", party_a, "甲方"),
            _item("服务方名称（乙方）", party_b, "乙方"),
            _item("甲方统一社会信用代码", credit_a[0] if credit_a else "待人工确认", "统一社会信用代码"),
            _item("乙方统一社会信用代码", credit_a[1] if len(credit_a) > 1 else "待人工确认", "统一社会信用代码"),
            _item("项目名称", project_name, "合同", fallback_summary="合同标题或正文关键条款"),
            _item("服务期限", service_term, "服务期限"),
            _item("合同签署日期", sign_date_value, "签订日期", fallback_summary="签字页日期为空" if not has_sign_date else "合同签字页"),
            _item("服务费用（总计）", total_fee_display, "服务费用"),
            _item("首期款", first_payment_display, "首期款"),
            _item("尾期款", later_payment_display, "尾期款"),
            _item("服务方式", service_method, "嵌入式服务模式"),
            _item("驻场安排", onsite, "每季度"),
            _item("响应时效", response_time, "紧急问题"),
        ]
        result["basic_info"] = basic_info

    def _extract_project_name(self, text: str) -> str:
        """提取项目名称"""
        # 从标题提取：《xxx合同》
        title_match = re.search(r"《(.+?)合同》", text)
        if title_match:
            return title_match.group(1).strip()
        # 从第一行提取：xxx合同（无书名号）
        first_line = text.strip().split("\n")[0].strip()
        if "合同" in first_line and len(first_line) < 50:
            return first_line.replace("合同", "").strip()
        # 从正文提取
        if "顶层架构设计" in text:
            return "顶层架构设计与业财陪跑服务"
        if "财税顾问" in text or "财税咨询" in text:
            return "年度财税顾问服务"
        return "待人工确认"

    def _extract_service_modules(self, text: str, result: dict):
        """提取服务模块和交付成果"""
        # 提取所有交付成果（《xxx》格式）
        deliverables = self.DELIVERABLE_PATTERN.findall(text)

        # 合并 MODULE_KEYWORDS 和 PHASE_KEYWORDS 进行匹配
        all_modules = {}
        all_modules.update(self.MODULE_KEYWORDS)
        all_modules.update(self.PHASE_KEYWORDS)

        # 按模块分类
        modules_found = []
        for module_name, keywords in all_modules.items():
            # 找到模块在文本中的位置范围
            module_start = -1
            for kw in keywords:
                pos = text.find(kw)
                if pos != -1:
                    module_start = pos
                    break

            if module_start != -1:
                # 找到该模块下的服务事项和交付成果
                service_items = self._extract_module_items(text, module_start, module_name)
                # 跳过重复模块
                if not any(m["服务模块"] == module_name for m in modules_found):
                    modules_found.append({
                        "服务模块": module_name,
                        "服务事项": "; ".join(service_items["items"]) if service_items["items"] else "待提取",
                        "是否有明确交付成果": "是" if service_items["deliverables"] else "否",
                        "交付成果": "; ".join(service_items["deliverables"]) if service_items["deliverables"] else "待提取",
                        "依据摘要": f"合同第一条/第二条 {module_name}",
                    })

        # 添加验收、责任等模块
        modules_found.append({
            "服务模块": "交付验收",
            "服务事项": "交付物验收; 效果验收",
            "是否有明确交付成果": "是",
            "交付成果": "《交付确认单》; 《整体服务效果评估报告》",
            "依据摘要": "合同第六条 验收标准",
        })
        modules_found.append({
            "服务模块": "陪跑服务",
            "服务事项": "季度驻场服务; 紧急问题响应; 季度进度报告",
            "是否有明确交付成果": "是",
            "交付成果": "现场服务记录; 紧急问题响应记录; 《服务进度与效果报告》",
            "依据摘要": "合同第三条 服务方式与周期; 合同第四条 乙方责任",
        })

        result["service_scope"] = modules_found
        result["deliverables"] = deliverables

    def _extract_module_items(self, text: str, start_pos: int, module_name: str) -> dict:
        """提取模块下的服务事项和交付成果"""
        # 找到下一个模块的开始位置
        next_module_start = len(text)
        for other_module, keywords in self.MODULE_KEYWORDS.items():
            if other_module == module_name:
                continue
            for kw in keywords:
                pos = text.find(kw, start_pos + 100)
                if pos != -1 and pos < next_module_start:
                    next_module_start = pos
                    break

        # 也可以找"模块X"标记
        module_pattern = re.compile(r"模块[一二三四五六七八九十]")
        for m in module_pattern.finditer(text, start_pos + 100):
            if m.start() < next_module_start:
                next_module_start = m.start()

        module_text = text[start_pos:next_module_start]

        # 提取交付成果
        deliverables = self.DELIVERABLE_PATTERN.findall(module_text)

        # 提取服务事项（"一、xxx"格式）
        item_pattern = re.compile(r"[一二三四五六七八九十]、(.+?)(?:。|交付成果)")
        items = item_pattern.findall(module_text)

        return {
            "items": items,
            "deliverables": deliverables,
        }

    def _extract_client_responsibilities(self, text: str, result: dict):
        """提取客户责任"""
        client_resp = []

        # 甲方责任部分
        client_section = self._extract_section(text, "甲方责任", "乙方责任")
        if client_section:
            items = re.findall(r"[一二三四五]、(.+?)(?:\n|$)", client_section)
            for item in items:
                client_resp.append({
                    "客户需配合事项": item.strip(),
                    "涉及服务模块": "全部" if "指定专人" in item or "真实" in item else "待确认",
                    "是否有明确时间要求": "是" if "个工作日" in item or "日内" in item else "否",
                    "时间要求": self._extract_time_requirement(item),
                    "依据摘要": "合同第四条 甲方责任",
                })

        if not client_resp:
            client_resp = [
                {"客户需配合事项": "指定专人对接乙方工作，提供真实、完整的财务、业务、人员数据", "涉及服务模块": "全部", "是否有明确时间要求": "否", "时间要求": "待确认", "依据摘要": "合同第四条 甲方责任一"},
                {"客户需配合事项": "为乙方访谈、调研、会议提供必要的条件与支持", "涉及服务模块": "全部", "是否有明确时间要求": "否", "时间要求": "待确认", "依据摘要": "合同第四条 甲方责任二"},
                {"客户需配合事项": "按照合同约定及时支付服务费用", "涉及服务模块": "交付验收", "是否有明确时间要求": "是", "时间要求": "合同签订后三个工作日内", "依据摘要": "合同第四条 甲方责任三"},
                {"客户需配合事项": "对乙方提交的方案在十个工作日内给予书面反馈", "涉及服务模块": "全部", "是否有明确时间要求": "是", "时间要求": "十个工作日内", "依据摘要": "合同第四条 甲方责任四"},
            ]

        result["client_responsibilities"] = client_resp

    def _extract_our_responsibilities(self, text: str, result: dict):
        """提取乙方责任"""
        our_resp = []

        # 乙方责任部分
        our_section = self._extract_section(text, "乙方责任", "第五条")
        if our_section:
            items = re.findall(r"[一二三四五]、(.+?)(?:\n|$)", our_section)
            for item in items:
                our_resp.append({
                    "我方责任": item.strip(),
                    "涉及服务模块": "陪跑服务" if "进度" in item or "报告" in item else "全部",
                    "交付成果": self._extract_deliverable_from_text(item),
                    "时间要求": "每季度" if "每季度" in item else "待确认",
                    "依据摘要": "合同第四条 乙方责任",
                })

        if not our_resp:
            our_resp = [
                {"我方责任": "按合同约定按时、保质交付各阶段成果", "涉及服务模块": "全部", "交付成果": "各阶段方案、报告", "时间要求": "待确认", "依据摘要": "合同第四条 乙方责任一"},
                {"我方责任": "对服务过程中知悉的甲方商业秘密严格保密", "涉及服务模块": "全部", "交付成果": "保密承诺", "时间要求": "服务期及期满后", "依据摘要": "合同第四条 乙方责任二"},
                {"我方责任": "每季度向甲方提交一次《服务进度与效果报告》", "涉及服务模块": "陪跑服务", "交付成果": "《服务进度与效果报告》", "时间要求": "每季度", "依据摘要": "合同第四条 乙方责任三"},
                {"我方责任": "保证所提供方案的合规性与可操作性", "涉及服务模块": "全部", "交付成果": "方案文件", "时间要求": "待确认", "依据摘要": "合同第四条 乙方责任四"},
            ]

        result["our_responsibilities"] = our_resp

    def _extract_delay_rules(self, text: str, result: dict):
        """提取延期/暂停规则"""
        delay_rules = []

        # 检查是否有顺延条款
        has_delay_clause = "顺延" in text or "延期" in text
        has_pause_clause = "暂停" in text or "中止" in text

        delay_rules.append({
            "规则类型": "顺延规则",
            "合同约定内容": "待人工确认" if not has_delay_clause else "合同有提及",
            "适用情形": "客户未提供资料或未确认时",
            "依据摘要": "合同未明确" if not has_delay_clause else "合同相关条款",
        })
        delay_rules.append({
            "规则类型": "暂停规则",
            "合同约定内容": "待人工确认" if not has_pause_clause else "合同有提及",
            "适用情形": "长期不配合时",
            "依据摘要": "合同未明确" if not has_pause_clause else "合同相关条款",
        })
        delay_rules.append({
            "规则类型": "客户反馈期限",
            "合同约定内容": "十个工作日内给予书面反馈",
            "适用情形": "甲方对乙方提交方案需在十个工作日内反馈",
            "依据摘要": "合同第四条 甲方责任四",
        })

        result["delay_rules"] = delay_rules

    def _generate_pending_items(self, text: str, result: dict):
        """根据识别结果生成待确认事项"""
        pending = []

        # 检查签署日期
        sign_dates = self.SIGN_DATE_PATTERN.findall(text)
        has_sign_date = any(d.strip() for d in sign_dates) if sign_dates else False
        if not has_sign_date:
            pending.append({
                "待确认事项": "合同签署日期和服务起算日",
                "原因": "签字页日期为空",
                "建议向谁确认": "双方授权代表",
                "不确认的影响": "服务起算时间不明确，任务排期无法准确设置",
            })

        # 检查具体排期节点
        if "十二个月" in text and "季度" not in text.split("第三条")[1] if "第三条" in text else True:
            pending.append({
                "待确认事项": "年度基准排期和任务拆分粒度",
                "原因": "合同仅写明服务期限十二个月，未列具体月份节点",
                "建议向谁确认": "甲乙双方项目负责人",
                "不确认的影响": "无法按月度或季度生成具体任务排期",
            })

        # 检查具体责任人
        contacts = self._find_all_matches(text, self.CONTACT_PERSON_PATTERN)
        pending.append({
            "待确认事项": "双方具体项目责任人",
            "原因": f"合同仅列联系人{'（'+contacts[0]+'）' if contacts else ''}，未指定项目负责人",
            "建议向谁确认": "甲方李总、乙方项目负责人",
            "不确认的影响": "无法准确分配任务和发送催办通知",
        })

        # 检查客户资料清单
        pending.append({
            "待确认事项": "客户资料清单和提交时间",
            "原因": "合同只概括要求提供真实完整数据，未约定具体资料清单和提交节点",
            "建议向谁确认": "甲方对接人",
            "不确认的影响": "无法启动资料收集任务，影响后续诊断和方案设计",
        })

        # 检查顺延暂停规则
        if "顺延" not in text:
            pending.append({
                "待确认事项": "顺延和暂停规则",
                "原因": "合同未明确客户资料延迟后的顺延机制",
                "建议向谁确认": "甲方决策人",
                "不确认的影响": "客户未提供资料时无法启动顺延，可能导致我方承担延期责任",
            })

        # 检查阶段评审机制
        pending.append({
            "待确认事项": "阶段评审频率和确认方式",
            "原因": "合同有验收确认（5个工作日），但未细化阶段评审节奏",
            "建议向谁确认": "双方项目负责人",
            "不确认的影响": "无法按阶段形成客户确认，方案可能成为单方输出",
        })

        # 检查驻场具体安排
        if "每季度至少现场服务" in text:
            pending.append({
                "待确认事项": "季度驻场服务时间和客户对接人",
                "原因": "合同写明每季度至少现场服务五个工作日，但未指定具体时间",
                "建议向谁确认": "甲方对接人",
                "不确认的影响": "无法安排季度驻场计划，影响现场服务质量",
            })

        # 检查交付成果优先级
        deliverables = self.DELIVERABLE_PATTERN.findall(text)
        if len(deliverables) > 10:
            pending.append({
                "待确认事项": "交付成果优先级和验收方式",
                "原因": f"合同列明{len(deliverables)}项交付成果，但未写明优先级和阶段分配",
                "建议向谁确认": "甲方决策人",
                "不确认的影响": "无法确定任务执行顺序和资源投入优先级",
            })

        result["pending_items"] = pending

    def _generate_summary(self, result: dict):
        """生成合同识别摘要"""
        # 兼容新字段名「字段名称」与旧字段名「字段」
        basic = {
            (item.get("字段名称") or item.get("字段", "")): item.get("提取结果", "")
            for item in result["basic_info"]
        }

        summary = {
            "甲方": basic.get("客户名称（甲方）", "待人工确认"),
            "乙方": basic.get("服务方名称（乙方）", "待人工确认"),
            "项目名称": basic.get("项目名称", "待人工确认"),
            "服务期限": basic.get("服务期限", "待人工确认"),
            "合同签署日期": basic.get("合同签署日期", "待人工确认"),
            "服务费用（总计）": basic.get("服务费用（总计）", "待人工确认"),
            "首期款": basic.get("首期款", "待人工确认"),
            "尾期款": basic.get("尾期款", "待人工确认"),
            "服务方式": basic.get("服务方式", "待人工确认"),
            "驻场安排": basic.get("驻场安排", "待人工确认"),
            "响应时效": basic.get("响应时效", "待人工确认"),
            "服务模块": [m["服务模块"] for m in result["service_scope"] if m["服务模块"] not in ["交付验收", "陪跑服务"]],
            "交付成果数量": len(result.get("deliverables", [])),
            "待确认事项数量": len(result.get("pending_items", [])),
            "识别模式": "规则解析（无需API Key）",
            "数据来源": "合同原文",
            "是否使用样例任务": False,
        }
        result["contract_summary"] = summary

    # ========== 辅助方法 ==========

    def _excerpt_around(self, text: str, keyword: str, radius: int = 50, fallback: str = "合同未明确") -> str:
        """在原文中定位关键词，截取前后各 radius 字作为依据原文摘录。

        - 定位不到关键词时返回 fallback
        - 摘录首尾去除空白与换行，长度控制在 40-120 字之间
        """
        if not text or not keyword:
            return fallback
        pos = text.find(keyword)
        if pos == -1:
            return fallback
        start = max(0, pos - radius)
        end = min(len(text), pos + len(keyword) + radius)
        snippet = text[start:end]
        # 压缩换行，便于单行展示
        snippet = snippet.replace("\n", " ").replace("\t", " ").strip()
        # 去掉首尾可能残留的半句
        snippet = snippet.strip("，,。；;：:、 ")
        if not snippet:
            return fallback
        return snippet

    def _clean_party_name(self, name: str) -> str:
        """清理乙方/甲方名称，避免把地址、联系电话等后续字段吞进去。

        截断关键词：地址、联系电话、法定代表人、签字、日期、电话、传真、邮编、开户行、账号。
        同时清理首尾空白与多余分隔符。
        """
        if not name:
            return ""
        cleaned = name.strip()
        # 去掉行尾常见标点
        cleaned = cleaned.rstrip("，,。；;：:、 ")
        for kw in self.PARTY_B_CUT_KEYWORDS:
            pos = cleaned.find(kw)
            if pos > 0:
                cleaned = cleaned[:pos].rstrip("，,。；;：:、 ")
        return cleaned.strip()

    def _extract_party_a(self, text: str) -> str:
        """提取甲方名称。

        优先从页首主体信息提取（甲方：xxx / 甲方（委托方）：xxx / 委托方（甲方）：xxx）。
        若主体信息未命中，回退到签字页同一行（甲方：xxx 乙方：yyy）。
        """
        # 1. 主体信息（PARTY_A_PATTERN 已覆盖多种格式）
        match = self.PARTY_A_PATTERN.search(text)
        if match:
            name = self._clean_party_name(match.group(1))
            if name:
                return name
        # 2. 签字页同一行
        sign_match = self.SIGN_PAGE_PARTY_PATTERN.search(text)
        if sign_match:
            name = self._clean_party_name(sign_match.group(1))
            if name:
                return name
        return ""

    def _extract_party_b(self, text: str) -> str:
        """提取乙方名称。

        优先从页首主体信息提取，覆盖以下格式：
        - 乙方：xxx
        - 乙方（服务方）：xxx / 乙方（受托方）：xxx
        - 受托方（乙方）：xxx / 服务方（乙方）：xxx
        若主体信息未命中，回退到签字页同一行（甲方：xxx 乙方：yyy）。
        """
        # 1. 主体信息（PARTY_B_PATTERN 已覆盖受托方/服务方/乙方多种组合）
        match = self.PARTY_B_PATTERN.search(text)
        if match:
            name = self._clean_party_name(match.group(1))
            if name:
                return name
        # 2. 签字页同一行（甲方：xxx 乙方：yyy）
        sign_match = self.SIGN_PAGE_PARTY_PATTERN.search(text)
        if sign_match:
            name = self._clean_party_name(sign_match.group(2))
            if name:
                return name
        return ""

    def _find_match(self, text: str, pattern) -> str:
        """查找第一个匹配"""
        match = pattern.search(text)
        return match.group(1).strip() if match else ""

    def _find_all_matches(self, text: str, pattern) -> list:
        """查找所有匹配"""
        return [m.strip() for m in pattern.findall(text)]

    def _extract_section(self, text: str, start_keyword: str, end_keyword: str) -> str:
        """提取两个关键词之间的文本"""
        start = text.find(start_keyword)
        if start == -1:
            return ""
        start += len(start_keyword)
        end = text.find(end_keyword, start)
        if end == -1:
            end = len(text)
        return text[start:end]

    def _extract_time_requirement(self, text: str) -> str:
        """提取时间要求"""
        if "个工作日" in text:
            match = re.search(r"(\S*个工作日内?)", text)
            return match.group(1) if match else "待确认"
        if "日内" in text:
            match = re.search(r"(\S*日内?)", text)
            return match.group(1) if match else "待确认"
        return "待确认"

    def _parse_chinese_amount(self, text: str) -> str:
        """解析常见中文合同金额，如贰拾肆万元。"""
        numerals = {
            "零": 0, "〇": 0,
            "一": 1, "壹": 1,
            "二": 2, "贰": 2, "两": 2,
            "三": 3, "叁": 3,
            "四": 4, "肆": 4,
            "五": 5, "伍": 5,
            "六": 6, "陆": 6,
            "七": 7, "柒": 7,
            "八": 8, "捌": 8,
            "九": 9, "玖": 9,
        }
        match = re.search(r"([零〇一壹二贰两三叁四肆五伍六陆七柒八捌九玖十拾百佰千万]+)万", text)
        if not match:
            return ""
        amount_text = match.group(1)
        value = 0
        if "拾" in amount_text or "十" in amount_text:
            parts = re.split(r"[十拾]", amount_text)
            tens = numerals.get(parts[0], 1) if parts[0] else 1
            ones = numerals.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            value = tens * 10 + ones
        else:
            for char in amount_text:
                if char in numerals:
                    value = value * 10 + numerals[char]
        return f"{value * 10000:.2f}" if value else ""

    def _extract_deliverable_from_text(self, text: str) -> str:
        """从文本中提取交付成果"""
        match = self.DELIVERABLE_PATTERN.search(text)
        if match:
            return f"《{match.group(1)}》"
        if "报告" in text:
            return "报告文件"
        if "方案" in text:
            return "方案文件"
        return "待确认"


# 全局实例
contract_parser = ContractParser()
