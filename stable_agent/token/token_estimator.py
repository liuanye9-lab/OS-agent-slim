"""Token Budget Ledger — Token 估算器。

提供 token 数量估算功能。优先使用 tiktoken 进行精准计数，
不可用时回退到启发式估算：
- 中文：约 1.5 字符/token
- 英文/数字：约 4 字符/token
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _load_tiktoken_encoder():
    """尝试加载 tiktoken cl100k_base 编码器。

    Returns:
        tiktoken.Encoding 实例，失败返回 None。
    """
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        logger.debug("tiktoken 加载失败，回退到启发式估算: %s", e)
        return None


class TokenEstimator:
    """Token 估算器。

    优先使用 tiktoken 进行精准计数，不可用时回退到启发式估算。

    Attributes:
        encoder: tiktoken 编码器实例，None 表示回退模式。
    """

    def __init__(self) -> None:
        """初始化 TokenEstimator，尝试加载 tiktoken 编码器。"""
        self.encoder = _load_tiktoken_encoder()

    def estimate(self, text: str) -> int:
        """估算文本的 token 数。

        - 有 tiktoken → 精准计数
        - fallback → 中文按 1.5 字/token，英文/数字按 4 字符/token

        Args:
            text: 输入文本。

        Returns:
            预估 token 数。
        """
        if not text:
            return 0

        if self.encoder is not None:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.debug("tiktoken 编码失败，回退到启发式估算: %s", e)

        # Fallback 启发式估算
        chinese_chars = 0
        other_chars = 0
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f':
                chinese_chars += 1
            else:
                other_chars += 1

        return max(1, int(chinese_chars / 1.5 + other_chars / 4))

    @property
    def is_fallback(self) -> bool:
        """是否使用 fallback 估算模式。

        Returns:
            True 表示使用启发式估算，False 表示使用 tiktoken。
        """
        return self.encoder is None
