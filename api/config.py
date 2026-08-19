"""
年度财税顾问项目拆分工作台 - 全局配置管理
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    """全局配置类"""

    # ========== 路径配置 ==========
    # 项目根目录（project-split-workbench/）
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    # api 目录
    API_DIR: Path = Path(__file__).resolve().parent
    # 提示词目录
    PROMPTS_DIR: Path = API_DIR / "services" / "mock_data"
    # 提示词模板目录
    PROMPT_TEMPLATES_DIR: Path = API_DIR / "prompts"
    # 数据运行目录
    RUNS_DIR: Path = BASE_DIR / "runs"
    # 上传文件目录
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    # 导出文件目录
    EXPORT_DIR: Path = BASE_DIR / "exports"

    # ========== 应用配置 ==========
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() == "true"

    # ========== CORS 配置 ==========
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
        ).split(",")
        if origin.strip()
    ]

    # ========== 运行模式 ==========
    # mock: 使用预设JSON数据; real: 调用真实LLM; rule: 规则解析优先(无需API Key)
    RUN_MODE: str = os.getenv("RUN_MODE", "rule")

    # ========== 解析模式 ==========
    # auto: 规则解析优先,有API Key时LLM增强; rule: 仅规则解析; llm: 仅LLM
    PARSER_MODE: str = os.getenv("PARSER_MODE", "auto")

    # ========== LLM 配置 ==========
    # 支持 OpenAI-compatible 接口: DeepSeek / 通义千问 / 其他
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    # DeepSeek 默认: https://api.deepseek.com/v1
    # 通义千问默认: https://dashscope.aliyuncs.com/compatible-mode/v1
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    # DeepSeek 默认: deepseek-chat | 通义千问默认: qwen-plus
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))

    # ========== LLM 预设配置 ==========
    LLM_PRESETS = {
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        },
    }

    # ========== 字段标准 ==========
    FIELD_OPTIONS = {
        "服务模块": [
            "税务合规", "财务规范", "风险排查", "制度建设",
            "纳税申报辅导", "经营分析", "客户资料", "客户确认",
            "会议沟通", "交付验收", "顶层结构设计", "资产架构",
            "关联交易", "股权架构", "资金架构", "人员架构",
            "其他待确认",
        ],
        "任务类型": [
            "服务执行", "客户资料", "客户确认", "会议沟通", "交付验收",
        ],
        "当前状态": [
            "未开始", "进行中", "待客户", "待我方",
            "待确认", "已完成", "逾期", "暂停",
        ],
        "延期责任归属": [
            "无延期", "客户原因", "我方原因",
            "第三方原因", "共同原因", "待判断",
        ],
        "人工复核状态": [
            "待复核", "已确认", "需修改", "剔除",
        ],
    }

    # ========== 18字段列表（中文 -> 英文key映射） ==========
    FIELD_MAPPING = {
        "客户名称": "customer_name",
        "项目名称": "project_name",
        "任务名称": "task_name",
        "服务模块": "service_module",
        "任务类型": "task_type",
        "计划开始时间": "plan_start_date",
        "计划完成时间": "plan_end_date",
        "我方负责人": "our_owner",
        "客户责任人": "client_contact",
        "客户需提供的资料或配合事项": "client_requirements",
        "当前状态": "current_status",
        "延期责任归属": "delay_responsibility",
        "节点目标/达到效果": "milestone_goal",
        "下一步动作及承诺完成时间": "next_action",
        "交付成果或完成凭证": "deliverables",
        "AI定制交付成果说明": "ai_deliverable_desc",
        "AI提取依据": "ai_extraction_basis",
        "人工复核状态": "review_status",
    }

    # 英文key -> 中文名称（反向映射）
    FIELD_MAPPING_REVERSE = {v: k for k, v in FIELD_MAPPING.items()}

    # 18字段中文名列表（按顺序）
    FIELD_NAMES_CN = list(FIELD_MAPPING.keys())

    # 18字段英文名列表（按顺序）
    FIELD_NAMES_EN = list(FIELD_MAPPING.values())

    def __init__(self):
        """初始化时创建必要目录"""
        self.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def is_mock_mode(self) -> bool:
        """是否为 mock 模式（仅 mock 模式才使用预设样例数据）"""
        return self.RUN_MODE.lower() == "mock"

    @property
    def is_rule_mode(self) -> bool:
        """是否为规则解析模式"""
        return self.RUN_MODE.lower() == "rule" or (
            self.RUN_MODE.lower() == "auto" and not self.llm_available
        )

    @property
    def parser_mode(self) -> str:
        """当前解析模式: rule / llm / auto / mock"""
        if self.is_mock_mode:
            return "mock"
        mode = self.PARSER_MODE.lower()
        if mode == "auto":
            return "rule" if not self.llm_available else "llm_enhanced"
        return mode

    @property
    def run_mode_label(self) -> str:
        """运行模式中文标签"""
        if self.is_mock_mode:
            return "Mock演示模式"
        if self.llm_available:
            return "真实解析模式(LLM增强)"
        return "真实解析模式(规则解析)"

    @property
    def llm_available(self) -> bool:
        """LLM 是否可用（有 API Key）

        优先检查环境变量，其次检查动态配置文件 .ai_config.json
        """
        if self.LLM_API_KEY:
            return True
        # 检查动态配置文件（运行时通过 AI 配置面板写入）
        config_file = self.BASE_DIR / ".ai_config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return bool(cfg.get("api_key", ""))
            except (json.JSONDecodeError, IOError):
                pass
        return False

    def get_run_dir(self, run_id: str) -> Path:
        """获取指定 run 的数据目录（run_id 来自 URL，必须校验防路径穿越）"""
        from services.path_safety import validate_id, safe_join

        validate_id(run_id, "run_id")
        run_dir = safe_join(self.RUNS_DIR, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def get_mock_data_path(self, filename: str) -> Path:
        """获取 mock 数据文件路径"""
        return self.PROMPTS_DIR / filename

    def get_prompt_path(self, name: str) -> Path:
        """获取提示词文件路径"""
        return self.PROMPT_TEMPLATES_DIR / f"{name}.txt"


# 全局配置实例
settings = Settings()
