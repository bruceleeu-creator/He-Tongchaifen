"""
报告校验规则服务
在导出前校验报告内容是否符合合同真实信息
阻止不符合校验规则的正式报告导出
"""
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportValidator:
    """报告校验器"""

    # 样例数据关键词（出现则说明使用了 Mock 数据）
    MOCK_KEYWORDS = ["客户A", "农业公司", "年度综合财税服务项目", "2026-07-15", "2027-07-14"]

    # 合同必须覆盖的核心模块
    REQUIRED_MODULES = [
        "商业模式设计", "股权架构搭建", "资产重塑", "人效提升", "业财合规陪跑",
        "交付验收", "陪跑服务",
    ]

    def validate(
        self,
        contract_summary: dict,
        task_list: dict,
        pending_list: dict = None,
        risk_list: dict = None,
        run_mode: str = "rule",
        has_plan: bool = False,
    ) -> dict:
        """执行全部校验规则

        Returns:
            {
                "passed": bool,
                "errors": list[dict],  # 阻断性错误
                "warnings": list[dict],  # 警告但不阻断
                "checks": list[dict],  # 所有检查项明细
                "validated_at": str,
            }
        """
        errors = []
        warnings = []
        checks = []

        tasks = task_list.get("tasks", []) if isinstance(task_list, dict) else []

        # 1. 客户名称必须来自合同主体
        check = self._check_customer_name(contract_summary, tasks)
        checks.append(check)
        if not check["passed"]:
            errors.append(check)

        # 2. 项目名称必须来自合同
        check = self._check_project_name(contract_summary, tasks)
        checks.append(check)
        if not check["passed"]:
            errors.append(check)

        # 3. 合同金额不得显示"未明确"
        check = self._check_amount(contract_summary, tasks)
        checks.append(check)
        if not check["passed"]:
            errors.append(check)

        # 4. 不得虚构日期
        check = self._check_dates(contract_summary, tasks)
        checks.append(check)
        if not check["passed"]:
            errors.append(check)

        # 5. 只上传合同时不得引用不存在的计划
        check = self._check_source_reference(tasks, has_plan)
        checks.append(check)
        if not check["passed"]:
            errors.append(check)

        # 6. 不得使用 Mock 样例数据
        check = self._check_no_mock_data(tasks)
        checks.append(check)
        if not check["passed"]:
            errors.append(check)

        # 7. 任务模块必须覆盖合同核心模块
        check = self._check_module_coverage(tasks)
        checks.append(check)
        if not check["passed"]:
            warnings.append(check)

        # 8. 验收、响应、季度报告、现场服务条款必须进入任务或风险
        check = self._check_execution_clauses(tasks, pending_list, risk_list)
        checks.append(check)
        if not check["passed"]:
            warnings.append(check)

        # 9. 报告首页必须显示运行模式
        check = self._check_mode_label(run_mode)
        checks.append(check)
        if not check["passed"]:
            warnings.append(check)

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "validated_at": datetime.now().isoformat(),
        }

    def _check_customer_name(self, summary: dict, tasks: list) -> dict:
        """校验1: 客户名称必须来自合同主体"""
        contract_customer = summary.get("甲方", "")
        if not contract_customer or contract_customer == "待人工确认":
            return {
                "rule": "客户名称一致性",
                "passed": False,
                "message": "合同识别摘要中甲方名称未提取成功",
                "detail": f"摘要甲方: {contract_customer}",
            }

        # 检查任务表中的客户名称
        wrong_names = []
        for task in tasks:
            name = task.get("customer_name", "") or task.get("客户名称", "")
            if name and name != contract_customer:
                wrong_names.append(name)

        if wrong_names:
            return {
                "rule": "客户名称一致性",
                "passed": False,
                "message": f"任务表中出现与合同甲方不一致的客户名称: {', '.join(set(wrong_names))}",
                "detail": f"合同甲方: {contract_customer}",
            }

        return {
            "rule": "客户名称一致性",
            "passed": True,
            "message": f"客户名称一致: {contract_customer}",
            "detail": "",
        }

    def _check_project_name(self, summary: dict, tasks: list) -> dict:
        """校验2: 项目名称必须来自合同"""
        contract_project = summary.get("项目名称", "")
        if not contract_project or contract_project == "待人工确认":
            return {
                "rule": "项目名称一致性",
                "passed": False,
                "message": "合同识别摘要中项目名称未提取成功",
                "detail": "",
            }

        wrong_projects = []
        for task in tasks:
            name = task.get("project_name", "") or task.get("项目名称", "")
            if name and contract_project not in name and name not in contract_project:
                wrong_projects.append(name)

        if wrong_projects:
            return {
                "rule": "项目名称一致性",
                "passed": False,
                "message": f"任务表中出现与合同不一致的项目名称: {', '.join(set(wrong_projects))}",
                "detail": f"合同项目名称: {contract_project}",
            }

        return {
            "rule": "项目名称一致性",
            "passed": True,
            "message": f"项目名称一致: {contract_project}",
            "detail": "",
        }

    def _check_amount(self, summary: dict, tasks: list) -> dict:
        '''校验3: 合同金额如果原文存在，不得显示"未明确"'''
        total_fee = summary.get("服务费用（总计）", "")
        if not total_fee or total_fee == "待人工确认":
            return {
                "rule": "合同金额识别",
                "passed": False,
                "message": "合同识别摘要中服务费用未提取成功，但合同原文可能包含金额",
                "detail": "请检查合同第五条",
            }

        # 检查待确认清单中是否有"服务费用未明确"
        for task in tasks:
            basis = task.get("ai_extraction_basis", "") or task.get("AI提取依据", "")
            if "费用" in basis and "未明确" in basis:
                return {
                    "rule": "合同金额识别",
                    "passed": False,
                    "message": f"任务依据中仍写'费用未明确'，但合同已识别费用: {total_fee}",
                    "detail": "",
                }

        return {
            "rule": "合同金额识别",
            "passed": True,
            "message": f"服务费用已识别: {total_fee}",
            "detail": "",
        }

    def _check_dates(self, summary: dict, tasks: list) -> dict:
        """校验4: 合同未给出具体日期时，不得虚构日期"""
        sign_date = summary.get("合同签署日期", "")
        if sign_date and sign_date != "待人工确认":
            # 有签署日期，可以生成具体排期
            return {
                "rule": "日期来源校验",
                "passed": True,
                "message": f"合同签署日期已确认: {sign_date}",
                "detail": "",
            }

        # 无签署日期，检查任务中是否有虚构日期
        fabricated_dates = []
        for task in tasks:
            start = task.get("plan_start_date", "") or task.get("计划开始时间", "")
            end = task.get("plan_end_date", "") or task.get("计划完成时间", "")

            for date_str in [start, end]:
                if date_str and date_str.strip() and date_str != "待确认" and date_str != "待人工确认":
                    # 检查是否是样例日期
                    if "2026-07-15" in date_str or "2027-07-14" in date_str:
                        fabricated_dates.append(date_str)
                    # 检查是否是虚构的具体日期（格式为 YYYY-MM-DD）
                    elif len(date_str) >= 10 and date_str[4] == "-":
                        fabricated_dates.append(date_str)

        if fabricated_dates:
            return {
                "rule": "日期来源校验",
                "passed": False,
                "message": f"合同签署日期为空，但任务中存在虚构日期: {', '.join(set(fabricated_dates[:5]))}",
                "detail": "合同未写明签署日期，具体日期应留空或标'待确认'",
            }

        return {
            "rule": "日期来源校验",
            "passed": True,
            "message": "合同签署日期为空，任务日期已正确留空或标为待确认",
            "detail": "",
        }

    def _check_source_reference(self, tasks: list, has_plan: bool) -> dict:
        """校验5: 只上传合同时，不得引用不存在的服务计划"""
        if has_plan:
            return {
                "rule": "依据来源校验",
                "passed": True,
                "message": "已上传年度服务计划，可引用计划内容",
                "detail": "",
            }

        wrong_refs = []
        for task in tasks:
            basis = task.get("ai_extraction_basis", "") or task.get("AI提取依据", "")
            if basis and "计划" in basis and "合同" not in basis:
                wrong_refs.append(basis[:50])

        if wrong_refs:
            return {
                "rule": "依据来源校验",
                "passed": False,
                "message": f"未上传年度服务计划，但任务依据中引用了'计划': {', '.join(set(wrong_refs[:3]))}",
                "detail": "只能引用合同条款，不能引用不存在的计划",
            }

        return {
            "rule": "依据来源校验",
            "passed": True,
            "message": "任务依据均来自合同条款",
            "detail": "",
        }

    def _check_no_mock_data(self, tasks: list) -> dict:
        """校验6: 不得使用 Mock 样例数据"""
        mock_found = []
        for task in tasks:
            task_str = str(task)
            for keyword in self.MOCK_KEYWORDS:
                if keyword in task_str:
                    mock_found.append(keyword)
                    break

        if mock_found:
            return {
                "rule": "Mock数据检查",
                "passed": False,
                "message": f"任务数据中检测到样例关键词: {', '.join(set(mock_found))}",
                "detail": "真实合同模式下不得使用 Mock 样例数据",
            }

        return {
            "rule": "Mock数据检查",
            "passed": True,
            "message": "未检测到 Mock 样例数据",
            "detail": "",
        }

    def _check_module_coverage(self, tasks: list) -> dict:
        """校验7: 任务模块必须覆盖合同核心服务模块"""
        task_modules = set()
        for task in tasks:
            module = task.get("service_module", "") or task.get("服务模块", "")
            if module:
                task_modules.add(module)

        missing = [m for m in self.REQUIRED_MODULES if m not in task_modules]

        if missing:
            return {
                "rule": "模块覆盖检查",
                "passed": False,
                "message": f"以下合同核心模块未出现在任务中: {', '.join(missing)}",
                "detail": f"已有模块: {', '.join(task_modules)}",
            }

        return {
            "rule": "模块覆盖检查",
            "passed": True,
            "message": f"所有核心模块均已覆盖: {', '.join(self.REQUIRED_MODULES)}",
            "detail": "",
        }

    def _check_execution_clauses(self, tasks: list, pending_list: dict, risk_list: dict) -> dict:
        """校验8: 验收、响应、季度报告、现场服务条款必须进入任务或风险提示"""
        task_text = str(tasks)
        pending_text = str(pending_list) if pending_list else ""
        risk_text = str(risk_list) if risk_list else ""
        all_text = task_text + pending_text + risk_text

        required_clauses = {
            "验收确认": ["验收", "交付确认单", "确认单"],
            "响应时效": ["48小时", "四十八小时", "响应"],
            "季度报告": ["季度报告", "进度与效果报告", "服务进度"],
            "现场服务": ["现场服务", "驻场", "驻场服务"],
        }

        missing = []
        for clause, keywords in required_clauses.items():
            if not any(kw in all_text for kw in keywords):
                missing.append(clause)

        if missing:
            return {
                "rule": "执行条款检查",
                "passed": False,
                "message": f"以下执行条款未进入任务或风险提示: {', '.join(missing)}",
                "detail": "验收、响应、季度报告、现场服务条款必须任务化",
            }

        return {
            "rule": "执行条款检查",
            "passed": True,
            "message": "验收、响应、季度报告、现场服务条款均已任务化",
            "detail": "",
        }

    def _check_mode_label(self, run_mode: str) -> dict:
        """校验9: 报告必须显示运行模式"""
        if run_mode in ["rule", "llm_enhanced", "real"]:
            return {
                "rule": "运行模式标识",
                "passed": True,
                "message": f"运行模式: {run_mode}",
                "detail": "真实解析模式已标注",
            }
        elif run_mode == "mock":
            return {
                "rule": "运行模式标识",
                "passed": True,
                "message": "运行模式: Mock演示模式",
                "detail": "Mock模式已标注，不可作为正式报告",
            }
        return {
            "rule": "运行模式标识",
            "passed": False,
            "message": f"运行模式未明确: {run_mode}",
            "detail": "必须标注真实解析或Mock演示模式",
        }


# 全局实例
report_validator = ReportValidator()
