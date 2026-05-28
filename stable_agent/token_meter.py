"""StableAgent OS Token 计量与成本估算模块。

提供 Token 估算、上下文包大小计算和 API 调用成本估算功能。
优先使用 tiktoken 进行精准计数，不可用时回退到启发式估算。

约定：
- 所有方法返回整数 token 数
- 成本以美元为单位
- 模型价格以每 1K token 计价
"""

from __future__ import annotations

import logging
from typing import Optional

from stable_agent.models import ContextItem

logger = logging.getLogger(__name__)

# 模型价格字典：每 1K token 的 (input_price, output_price)，单位美元
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3.5-sonnet": (0.003, 0.015),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-haiku": (0.00025, 0.00125),
}


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


class TokenMeter:
    """Token 估算器。

    优先使用 tiktoken 进行精准计数，不可用时回退到启发式估算：
    - 中文：约 1.5 字符/token
    - 英文：约 4 字符/token

    Attributes:
        encoder: tiktoken 编码器实例，None 表示回退模式。
    """

    def __init__(self) -> None:
        """初始化 TokenMeter，尝试加载 tiktoken 编码器。"""
        self.encoder = _load_tiktoken_encoder()

    def estimate_tokens(self, text: str) -> int:
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
                pass

        # Fallback 启发式估算
        chinese_chars = 0
        other_chars = 0
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f':
                chinese_chars += 1
            else:
                other_chars += 1

        return int(chinese_chars / 1.5 + other_chars / 4)

    def estimate_context_items(self, items: list[ContextItem]) -> int:
        """估算上下文包的总 token 数。

        Args:
            items: ContextItem 列表。

        Returns:
            总 token 预估数。
        """
        total = 0
        for item in items:
            total += self.estimate_tokens(item.content)
            total += self.estimate_tokens(item.reason)
        return total

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_name: str = "gpt-4o",
    ) -> float:
        """估算 API 调用成本（美元）。

        对于未知模型，返回 0.0 而不崩溃。

        Args:
            input_tokens: 输入 token 数。
            output_tokens: 输出 token 数。
            model_name: 模型名称，默认 gpt-4o。

        Returns:
            预估成本（美元）。
        """
        if model_name not in MODEL_PRICES:
            return 0.0

        input_price_per_k, output_price_per_k = MODEL_PRICES[model_name]
        cost = (
            (input_tokens / 1000.0) * input_price_per_k
            + (output_tokens / 1000.0) * output_price_per_k
        )
        return cost

    def build_budget_report(
        self,
        before_items: list[ContextItem],
        after_items: list[ContextItem],
    ) -> dict:
        """生成压缩前后对比报告。

        Args:
            before_items: 压缩前的 ContextItem 列表。
            after_items: 压缩后的 ContextItem 列表。

        Returns:
            包含 before_tokens, after_tokens, compression_ratio, removed_ids 的字典。
        """
        before_tokens = self.estimate_context_items(before_items)
        after_tokens = self.estimate_context_items(after_items)

        before_ids = {item.id for item in before_items}
        after_ids = {item.id for item in after_items}
        removed_ids = sorted(before_ids - after_ids)

        compression_ratio = 0.0
        if before_tokens > 0:
            compression_ratio = round(1.0 - (after_tokens / before_tokens), 4)

        return {
            "before_tokens": before_tokens,
            "after_tokens": after_tokens,
            "compression_ratio": compression_ratio,
            "removed_ids": removed_ids,
        }

    @property
    def is_fallback(self) -> bool:
        """是否使用 fallback 估算模式。

        Returns:
            True 表示使用启发式估算，False 表示使用 tiktoken。
        """
        return self.encoder is None
