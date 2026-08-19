"""
JSON 文件存储服务
负责所有 JSON 数据的读写操作，按 runs/{run_id}/ 目录组织
"""
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import settings
from services.path_safety import validate_id, safe_filename, safe_join


class JSONStore:
    """JSON 文件存储管理器"""

    def __init__(self):
        self.base_dir = settings.RUNS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ========== 目录管理 ==========

    def get_run_dir(self, run_id: str) -> Path:
        """获取指定 run 的数据目录（run_id 来自 URL，必须校验防路径穿越）"""
        validate_id(run_id, "run_id")
        run_dir = safe_join(self.base_dir, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def create_run(self, run_name: str = "") -> str:
        """创建新的运行实例，返回 run_id"""
        run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        run_dir = self.get_run_dir(run_id)

        # 初始化 run 元数据
        meta = {
            "run_id": run_id,
            "run_name": run_name or f"运行实例 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().isoformat(),
            "status": "created",
        }
        self._write_json(run_dir / "meta.json", meta)
        return run_id

    def list_runs(self) -> list[dict]:
        """列出所有运行实例"""
        runs = []
        if not self.base_dir.exists():
            return runs

        for run_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if run_dir.is_dir() and run_dir.name.startswith("run_"):
                meta = self._read_json(run_dir / "meta.json")
                if meta:
                    runs.append(meta)
        return runs

    def get_run_meta(self, run_id: str) -> Optional[dict]:
        """获取运行实例元数据"""
        return self._read_json(self.get_run_dir(run_id) / "meta.json")

    def update_run_meta(self, run_id: str, updates: dict):
        """更新运行实例元数据"""
        meta = self.get_run_meta(run_id) or {}
        meta.update(updates)
        meta["updated_at"] = datetime.now().isoformat()
        self._write_json(self.get_run_dir(run_id) / "meta.json", meta)

    # ========== JSON 读写 ==========

    def read(self, run_id: str, filename: str, default: Any = None) -> Any:
        """读取 run 目录下的 JSON 文件"""
        filepath = safe_join(self.get_run_dir(run_id), safe_filename(filename))
        return self._read_json(filepath, default)

    def write(self, run_id: str, filename: str, data: Any):
        """写入 run 目录下的 JSON 文件"""
        filepath = safe_join(self.get_run_dir(run_id), safe_filename(filename))
        self._write_json(filepath, data)

    def exists(self, run_id: str, filename: str) -> bool:
        """检查文件是否存在"""
        return safe_join(self.get_run_dir(run_id), safe_filename(filename)).exists()

    def delete_file(self, run_id: str, filename: str):
        """删除文件"""
        filepath = safe_join(self.get_run_dir(run_id), safe_filename(filename))
        if filepath.exists():
            filepath.unlink()

    def delete_dir(self, run_id: str, dirname: str):
        """删除 run 目录下的子目录（递归删除所有内容）"""
        dirpath = safe_join(self.get_run_dir(run_id), safe_filename(dirname, "dirname"))
        if dirpath.exists() and dirpath.is_dir():
            shutil.rmtree(dirpath)

    # ========== Mock 数据初始化 ==========

    def init_from_mock(self, run_id: str):
        """从 mock 数据初始化 run 目录"""
        run_dir = self.get_run_dir(run_id)
        mock_dir = settings.PROMPTS_DIR

        mock_files = [
            "contract_result.json",
            "plan_result.json",
            "cross_check_result.json",
            "clarification_form.json",
            "task_list.json",
            "granularity_result.json",
            "pending_list.json",
            "risk_list.json",
        ]

        for filename in mock_files:
            mock_path = mock_dir / filename
            if mock_path.exists():
                shutil.copy2(mock_path, run_dir / filename)

    # ========== 内部方法 ==========

    @staticmethod
    def _read_json(filepath: Path, default: Any = None) -> Any:
        """读取 JSON 文件"""
        if not filepath.exists():
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default

    @staticmethod
    def _write_json(filepath: Path, data: Any):
        """写入 JSON 文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# 全局实例
json_store = JSONStore()
