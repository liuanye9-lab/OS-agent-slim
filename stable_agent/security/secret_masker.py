"""Secret Masker — 日志和输出中的密钥自动脱敏。

所有日志、测试输出、异常信息中不得出现真实 API key。
本模块提供 mask_secret / mask_text 函数，供全局使用。

用法::

    from stable_agent.security.secret_masker import mask_secret, mask_text

    safe = mask_secret("sk-219efad867674c3a8575a82aa7b2e175")
    # → "sk-2***175"

    safe_text = mask_text("Authorization: Bearer sk-219efad867674c3a8575a82aa7b2e175")
    # → "Authorization: Bearer sk-2***175"
"""

from __future__ import annotations

import re

# 常见 key 前缀模式
_KEY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # sk-... (OpenAI / Aliyun DashScope 等)
    (re.compile(r"(sk-[A-Za-z0-9]{2})[A-Za-z0-9]{6,}([A-Za-z0-9]{3,})"), r"\1***\2"),
    # Bearer token
    (re.compile(r"(Bearer\s+)([A-Za-z0-9\-_.]{2})[A-Za-z0-9\-_.]{6,}([A-Za-z0-9\-_.]{3,})"), r"\1\2***\3"),
    # anthropic-... key
    (re.compile(r"(ant-sk-[A-Za-z0-9]{2})[A-Za-z0-9]{6,}([A-Za-z0-9]{3,})"), r"\1***\2"),
    # 飞书 app_secret (纯字母数字 32 位)
    (re.compile(r"(FEISHU_APP_SECRET[=:]\s*)([A-Za-z0-9]{2})[A-Za-z0-9]{10,}([A-Za-z0-9]{3})"), r"\1\2***\3"),
    # 通用: 长数字字母串（>20 字符，可能是 key）
    (re.compile(r"([A-Za-z0-9]{4})[A-Za-z0-9]{12,}([A-Za-z0-9]{4})"), r"\1***\2"),
]


def mask_secret(value: str) -> str:
    """对单个密钥值进行脱敏。

    Args:
        value: 待脱敏的密钥字符串。

    Returns:
        脱敏后的字符串。短于 8 字符返回 '***'，否则保留前 4+后 4 位。
    """
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def mask_text(text: str) -> str:
    """对文本中的所有疑似密钥进行脱敏。

    按模式匹配替换，适用于日志输出、异常信息、测试报告等。

    Args:
        text: 原始文本。

    Returns:
        脱敏后的文本。
    """
    if not text:
        return text
    result = text
    for pattern, replacement in _KEY_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def is_secret_leaked(text: str) -> bool:
    """检查文本中是否存在疑似密钥泄露。

    Args:
        text: 待检查文本。

    Returns:
        True 表示可能存在泄露。
    """
    # 检查 sk- 开头的长串
    if re.search(r"sk-[A-Za-z0-9]{20,}", text):
        return True
    # 检查 Bearer 后跟长串
    if re.search(r"Bearer\s+[A-Za-z0-9\-_.]{20,}", text):
        return True
    return False
