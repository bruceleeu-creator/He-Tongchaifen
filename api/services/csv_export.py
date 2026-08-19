"""
CSV 导出服务
UTF-8 BOM 编码，表头严格18字段
"""
import csv
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings
from services.path_safety import validate_id, safe_filename, safe_join


class CSVExporter:
    """CSV 导出器"""

    def __init__(self):
        self.export_dir = settings.EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_tasks(
        self,
        tasks: list[dict],
        run_id: str = "",
        filename: Optional[str] = None,
    ) -> str:
        """导出任务列表为 CSV 文件

        Args:
            tasks: 任务列表（每条为 dict，key 为英文）
            run_id: 运行 ID
            filename: 自定义文件名

        Returns:
            保存后的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = f"{run_id}_" if run_id else ""
            filename = f"{prefix}task_list_{timestamp}.csv"

        # 防路径穿越：校验 run_id 与文件名，最终路径必须仍在导出目录内
        if run_id:
            validate_id(run_id, "run_id")
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"非法文件名: {filename!r}")
        export_root = self.export_dir.resolve()
        filepath = (export_root / filename).resolve()
        if not filepath.is_relative_to(export_root):
            raise ValueError(f"路径越界的文件名: {filename!r}")

        # 使用 UTF-8 BOM 编码（csv 模块要求 newline=""，先在内存生成再落盘）
        output = io.StringIO(newline="")
        writer = csv.writer(output)

        # 写入表头（中文18字段）
        writer.writerow(settings.FIELD_NAMES_CN)

        # 写入数据行
        for task in tasks:
            row = []
            for en_key in settings.FIELD_NAMES_EN:
                row.append(task.get(en_key, ""))
            writer.writerow(row)

        filepath.write_text(output.getvalue(), encoding="utf-8-sig")

        return str(filepath)

    def export_to_string(self, tasks: list[dict]) -> str:
        """导出任务列表为 CSV 字符串（用于直接返回）"""
        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow(settings.FIELD_NAMES_CN)

        # 写入数据行
        for task in tasks:
            row = []
            for en_key in settings.FIELD_NAMES_EN:
                row.append(task.get(en_key, ""))
            writer.writerow(row)

        return output.getvalue()

    def export_markdown(self, tasks: list[dict], run_id: str = "") -> str:
        """导出任务列表为 Markdown 表格"""
        lines = []

        # 标题
        lines.append(f"# 年度财税顾问项目任务主表\n")
        lines.append(f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"- 任务总数: {len(tasks)}\n")

        # 表头
        header = "| " + " | ".join(settings.FIELD_NAMES_CN) + " |"
        separator = "| " + " | ".join(["---"] * len(settings.FIELD_NAMES_CN)) + " |"
        lines.append(header)
        lines.append(separator)

        # 数据行
        for task in tasks:
            row = []
            for en_key in settings.FIELD_NAMES_EN:
                value = str(task.get(en_key, "")).replace("|", "\\|").replace("\n", " ")
                row.append(value)
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def export_markdown_file(
        self,
        tasks: list[dict],
        run_id: str = "",
        filename: Optional[str] = None,
    ) -> str:
        """导出 Markdown 文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = f"{run_id}_" if run_id else ""
            filename = f"{prefix}task_list_{timestamp}.md"

        # 防路径穿越：校验 run_id 与文件名，最终路径必须仍在导出目录内
        if run_id:
            validate_id(run_id, "run_id")
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"非法文件名: {filename!r}")
        export_root = self.export_dir.resolve()
        filepath = (export_root / filename).resolve()
        if not filepath.is_relative_to(export_root):
            raise ValueError(f"路径越界的文件名: {filename!r}")

        content = self.export_markdown(tasks, run_id)
        filepath.write_text(content, encoding="utf-8")

        return str(filepath)


# 全局实例
csv_exporter = CSVExporter()
