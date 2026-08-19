"""
任务颗粒度检查服务
检查任务拆分粒度是否合理，识别需要进一步拆分或补充的任务
"""
import json
from services.ai_services.base import AIServiceBase
from services.llm_client import llm_client


class GranularityCheckService(AIServiceBase):
    """任务颗粒度检查服务"""

    service_name = "granularity_check"
    mock_filename = "granularity_result.json"
    prompt_name = "granularity_check"

    async def execute_rule(self, task_list: str = "", **kwargs) -> dict:
        """规则解析模式：基础颗粒度检查"""
        try:
            tasks = json.loads(task_list) if isinstance(task_list, str) else task_list
        except (json.JSONDecodeError, TypeError):
            tasks = []

        if not tasks:
            tasks = []
        elif isinstance(tasks, dict):
            tasks = tasks.get("tasks", [])

        need_split = []
        missing_fields = []
        client_data_issues = []
        deliverable_issues = []

        for t in tasks:
            name = t.get("task_name", "")
            task_id = t.get("task_id", "")
            task_type = t.get("task_type", "")
            deliverables = t.get("deliverables", "")
            client_req = t.get("client_requirements", "")
            milestone = t.get("milestone_goal", "")
            next_action = t.get("next_action", "")

            # 1. 检查任务名称过长（需要拆分）
            if len(name) > 30:
                need_split.append({
                    "task_id": task_id,
                    "原任务名称": name,
                    "问题": "任务名称过长，可能包含多个独立工作项",
                    "建议拆分为哪些任务": f"建议将【{name}】按服务模块或交付节点拆分为2-3个独立任务",
                })

            # 2. 检查关键字段缺失
            missing = []
            if not t.get("plan_start_date") or t.get("plan_start_date") == "待确认":
                missing.append("计划开始日期")
            if not t.get("plan_end_date") or t.get("plan_end_date") == "待确认":
                missing.append("计划结束日期")
            if not t.get("our_owner") or t.get("our_owner") == "项目经理":
                missing.append("我方责任人")
            if not t.get("client_contact") or t.get("client_contact") == "客户项目负责人":
                missing.append("客户对接人")

            if missing:
                missing_fields.append({
                    "task_id": task_id,
                    "task_name": name,
                    "missing": missing,
                    "suggestion": f"请在启动会或澄清环节确认{('、'.join(missing))}",
                })

            # 3. 检查客户资料类任务
            if task_type == "客户资料" or "客户资料" in name:
                if not client_req or client_req == "待确认":
                    client_data_issues.append({
                        "task_id": task_id,
                        "task_name": name,
                        "issue": "客户资料任务缺少具体资料清单",
                        "suggestion": "建议在启动会上与客户确认具体资料清单和提交时间",
                    })

            # 4. 检查交付成果
            if task_type == "交付验收" or "交付" in name:
                if not deliverables:
                    deliverable_issues.append({
                        "task_id": task_id,
                        "task_name": name,
                        "issue": "交付验收任务缺少明确交付物",
                        "suggestion": "建议补充具体的交付物名称和验收标准",
                    })

            # 5. 检查里程碑目标缺失
            if not milestone:
                missing_fields.append({
                    "task_id": task_id,
                    "task_name": name,
                    "missing": ["里程碑目标"],
                    "suggestion": "建议补充该任务的里程碑目标和验收标准",
                })

        # 生成摘要
        total_issues = len(need_split) + len(missing_fields) + len(client_data_issues) + len(deliverable_issues)
        if total_issues == 0:
            summary = f"已完成{len(tasks)}个任务的颗粒度检查，未发现明显问题。"
        else:
            summary = f"已完成{len(tasks)}个任务的颗粒度检查，发现{total_issues}个待改进项："
            if need_split:
                summary += f" {len(need_split)}个任务建议拆分；"
            if missing_fields:
                summary += f" {len(missing_fields)}个任务存在字段缺失；"
            if client_data_issues:
                summary += f" {len(client_data_issues)}个客户资料任务需补充；"
            if deliverable_issues:
                summary += f" {len(deliverable_issues)}个交付任务需完善交付物。"

        data = {
            "summary": summary,
            "need_split": need_split,
            "missing_fields": missing_fields,
            "client_data_issues": client_data_issues,
            "deliverable_issues": deliverable_issues,
            "total_issues": total_issues,
            "checked_tasks": len(tasks),
        }

        return {
            "success": True,
            "mode": "rule",
            "mode_label": "真实解析模式(规则解析)",
            "data_source": "任务主表",
            "service": self.service_name,
            "data": data,
        }

    async def execute_real(self, task_list: str = "", **kwargs) -> dict:
        """真实模式：调用 LLM 检查任务颗粒度"""
        prompt = self.render_prompt({"任务主表": task_list})
        if not prompt:
            return await self.execute_rule(task_list=task_list, **kwargs)
        result = await llm_client.chat_json(prompt)
        if result.get("error") or result.get("mock"):
            return await self.execute_rule(task_list=task_list, **kwargs)

        # 归一化 LLM 返回结果到标准字段，避免前端出现原始 JSON
        normalized = self._normalize_llm_result(result)
        return {
            "success": True,
            "mode": "real",
            "mode_label": "真实解析模式(LLM)",
            "data_source": f"任务主表(LLM: {llm_client.model})",
            "service": self.service_name,
            "data": normalized,
        }

    def _normalize_llm_result(self, result: dict) -> dict:
        """将 LLM 返回结果归一化为标准字段。

        兼容 LLM 可能返回的非标准字段：
        - passed/issue_count → 转换为中文 summary，绝不展示原始 JSON
        - summary 为 dict 或 JSON 字符串 → 视为无效，重新生成
        - 缺失字段 → 默认空数组
        """
        def ensure_array(val):
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                # 兼容 dict 包裹的数组
                for k in ("items", "list", "data"):
                    inner = val.get(k)
                    if isinstance(inner, list):
                        return inner
            return []

        def is_valid_summary(val) -> bool:
            # 仅接受非空、非 JSON 字符串
            if not isinstance(val, str):
                return False
            stripped = val.strip()
            if not stripped:
                return False
            if stripped.startswith("{") or stripped.startswith("["):
                return False
            return True

        need_split = ensure_array(result.get("need_split"))
        missing_fields = ensure_array(result.get("missing_fields"))
        client_data_issues = ensure_array(
            result.get("client_data_issues") or result.get("client_data_not_separated")
        )
        deliverable_issues = ensure_array(
            result.get("deliverable_issues") or result.get("unclear_deliverables")
        )

        # 1. 优先使用 LLM 返回的合法 summary
        summary = result.get("summary") if is_valid_summary(result.get("summary")) else ""

        # 2. summary 无效时，根据 passed/issue_count 生成中文摘要
        if not summary:
            passed = result.get("passed")
            issue_count = result.get("issue_count")
            total = (
                len(need_split) + len(missing_fields)
                + len(client_data_issues) + len(deliverable_issues)
            )
            if passed is True or issue_count == 0:
                summary = "颗粒度检查通过，未发现明显问题。"
            elif passed is False or (isinstance(issue_count, int) and issue_count > 0):
                cnt = issue_count if isinstance(issue_count, int) else total
                summary = f"颗粒度检查未通过，发现 {cnt} 个待改进项。"
            elif total > 0:
                summary = f"颗粒度检查完成，发现 {total} 个待改进项。"
            else:
                summary = "颗粒度检查完成。"

        return {
            "summary": summary,
            "need_split": need_split,
            "missing_fields": missing_fields,
            "client_data_issues": client_data_issues,
            "deliverable_issues": deliverable_issues,
            "total_issues": (
                len(need_split) + len(missing_fields)
                + len(client_data_issues) + len(deliverable_issues)
            ),
        }
