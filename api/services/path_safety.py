"""
路径安全工具

所有由外部输入（URL 路径参数、上传文件名等）拼接的文件路径，
必须先经过本模块校验，防止路径穿越攻击（如 run_id 传入 "../"）。
"""
import re
from pathlib import Path

# 标识符类输入（run_id / artifact_id 等）：字母/数字/下划线/连字符，禁止点号与分隔符
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")

# 单段文件名：字母/数字/下划线/连字符开头，可含点号（扩展名），禁止分隔符
_NAME_RE = re.compile(r"^[A-Za-z0-9_\-][A-Za-z0-9_\-.]{0,255}$")


def validate_id(value: str, field: str = "id") -> str:
    """校验 run_id / artifact_id 等标识符，拒绝路径穿越片段"""
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"非法的 {field}: {value!r}")
    return value


def safe_filename(value: str, field: str = "filename") -> str:
    """校验单段文件名（不含目录部分），拒绝穿越与隐藏文件"""
    if (
        not isinstance(value, str)
        or value in {".", ".."}
        or not _NAME_RE.match(value)
    ):
        raise ValueError(f"非法的 {field}: {value!r}")
    return value


def safe_join(base: Path, *parts: str) -> Path:
    """拼接路径并确保结果仍位于 base 之下（校验后的双保险）"""
    base = base.resolve()
    result = base
    for p in parts:
        result = result / p
    result = result.resolve()
    if result != base and base not in result.parents:
        raise ValueError(f"路径越界: {result}")
    return result
