"""
AI 配置动态存储服务
支持运行时切换 LLM 服务商和 API Key，无需重启后端
配置持久化到 JSON 文件，兼顾安全性与便利性
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# 配置文件路径：项目根目录 / .ai_config.json（常量路径，仍校验必须位于项目根目录内）
CONFIG_FILE = (settings.BASE_DIR / ".ai_config.json").resolve()
if not CONFIG_FILE.is_relative_to(settings.BASE_DIR.resolve()):
    raise RuntimeError(f"AI 配置文件路径越界: {CONFIG_FILE}")


# 默认预设配置
PRESETS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "description": "性价比高，中文合同理解能力强",
    },
    "qwen": {
        "label": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "description": "阿里云通义千问，国内访问稳定",
    },
    "openai": {
        "label": "OpenAI (GPT-4o)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "description": "GPT-4o，理解能力最强但成本较高",
    },
}


class AIConfigStore:
    """AI 配置动态存储"""

    def __init__(self):
        self._cache: Optional[dict] = None
        self._load()

    def _load(self):
        """从文件加载配置"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"AI 配置文件读取失败，使用默认配置: {e}")
                self._cache = None

        if not self._cache:
            # 从环境变量初始化
            self._cache = {
                "preset": "deepseek",
                "api_key": settings.LLM_API_KEY,
                "base_url": settings.LLM_BASE_URL,
                "model": settings.LLM_MODEL,
                "temperature": settings.LLM_TEMPERATURE,
                "timeout": settings.LLM_TIMEOUT,
                "updated_at": "",
                "updated_by": "system",
            }

    def _save(self):
        """保存配置到文件"""
        self._cache["updated_at"] = datetime.now().isoformat()
        try:
            CONFIG_FILE.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except IOError as e:
            logger.error(f"AI 配置文件保存失败: {e}")

    def get_config(self) -> dict:
        """获取当前 AI 配置（API Key 脱敏）"""
        self._load()  # 每次读取最新
        config = dict(self._cache)
        # API Key 脱敏：只显示前4位和后4位
        api_key = config.get("api_key", "")
        if api_key and len(api_key) > 12:
            config["api_key_masked"] = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
        elif api_key:
            config["api_key_masked"] = "*" * len(api_key)
        else:
            config["api_key_masked"] = ""
        config["has_api_key"] = bool(api_key)
        return config

    def get_raw_config(self) -> dict:
        """获取原始配置（含完整 API Key，仅内部使用）"""
        self._load()
        return dict(self._cache)

    def update_config(self, preset: str = "", api_key: str = "", base_url: str = "", model: str = "", temperature: float = None, timeout: int = None) -> dict:
        """更新 AI 配置

        Args:
            preset: 服务商预设 (deepseek / qwen / openai)
            api_key: API Key
            base_url: Base URL
            model: 模型名称
            temperature: 温度参数
            timeout: 超时时间（秒）

        Returns:
            更新后的配置（脱敏）
        """
        self._load()

        # 如果指定了预设，切换预设
        if preset and preset in PRESETS:
            p = PRESETS[preset]
            self._cache["preset"] = preset
            self._cache["base_url"] = p["base_url"]
            self._cache["model"] = p["model"]

        # API Key：空字符串不更新（保留原值），非空字符串才更新
        if api_key and api_key.strip():
            self._cache["api_key"] = api_key.strip()

        # 手动覆盖 base_url / model
        if base_url and base_url.strip():
            self._cache["base_url"] = base_url.strip()
        if model and model.strip():
            self._cache["model"] = model.strip()

        # 可选参数
        if temperature is not None:
            self._cache["temperature"] = float(temperature)
        if timeout is not None:
            self._cache["timeout"] = int(timeout)

        self._cache["updated_by"] = "user"
        self._save()

        logger.info(f"AI 配置已更新: preset={self._cache['preset']}, model={self._cache['model']}, has_key={bool(self._cache.get('api_key'))}")
        return self.get_config()

    def get_presets(self) -> dict:
        """获取所有预设配置"""
        return PRESETS

    @property
    def api_key(self) -> str:
        return self.get_raw_config().get("api_key", "")

    @property
    def base_url(self) -> str:
        return self.get_raw_config().get("base_url", settings.LLM_BASE_URL)

    @property
    def model(self) -> str:
        return self.get_raw_config().get("model", settings.LLM_MODEL)

    @property
    def temperature(self) -> float:
        return float(self.get_raw_config().get("temperature", settings.LLM_TEMPERATURE))

    @property
    def timeout(self) -> int:
        return int(self.get_raw_config().get("timeout", settings.LLM_TIMEOUT))

    @property
    def is_available(self) -> bool:
        """AI 是否可用（有 API Key）"""
        return bool(self.api_key)

    @property
    def model_source(self) -> str:
        """模型来源标识"""
        if not self.is_available:
            return "mock"
        return f"{self.model}@{self.base_url}"


# 全局实例
ai_config_store = AIConfigStore()
