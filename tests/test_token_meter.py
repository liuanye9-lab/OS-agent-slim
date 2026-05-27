"""StableAgent OS TokenMeter 单元测试。

测试 Token 估算、成本计算、预算报告等功能。
"""

from __future__ import annotations

import pytest

from stable_agent.models import ContextItem
from stable_agent.token_meter import MODEL_PRICES, TokenMeter


# ============================================================================
# Fixtures
# ============================================================================


class TestTokenMeterEstimateTokens:
    """测试 Token 估算。"""

    def test_estimate_tokens_english(self) -> None:
        """测试英文文本 Token 估算。"""
        tm = TokenMeter()
        tokens = tm.estimate_tokens("Hello world, this is a test sentence.")
        assert tokens > 0
        # 英文 fallback: ~40 chars / 4 = ~10 tokens
        assert 5 <= tokens <= 20

    def test_estimate_tokens_chinese(self) -> None:
        """测试中文文本 Token 估算。"""
        tm = TokenMeter()
        tokens = tm.estimate_tokens("今天天气非常好，适合出门散步和运动。")
        assert tokens > 0
        # 中文 fallback: ~18 chars / 1.5 = ~12 tokens
        assert 5 <= tokens <= 25

    def test_estimate_tokens_mixed(self) -> None:
        """测试中英文混合文本 Token 估算。"""
        tm = TokenMeter()
        tokens = tm.estimate_tokens(
            "修复 login page 的样式崩溃问题，需要调整 CSS 布局。"
        )
        assert tokens > 0

    def test_estimate_tokens_empty(self) -> None:
        """测试空文本返回 0。"""
        tm = TokenMeter()
        assert tm.estimate_tokens("") == 0

    def test_estimate_tokens_numeric(self) -> None:
        """测试纯数字文本。"""
        tm = TokenMeter()
        tokens = tm.estimate_tokens("12345 67890 12345 67890")
        assert tokens > 0


class TestTokenMeterContextItems:
    """测试上下文条目 Token 估算。"""

    def test_estimate_context_items(self) -> None:
        """测试上下文包总 Token 估算。"""
        tm = TokenMeter()
        items = [
            ContextItem(id="i1", content="Hello world", reason="High relevance"),
            ContextItem(id="i2", content="今天天气好", reason="中等相关"),
        ]
        total = tm.estimate_context_items(items)
        assert total > 0

    def test_estimate_context_items_empty(self) -> None:
        """测试空列表返回 0。"""
        tm = TokenMeter()
        assert tm.estimate_context_items([]) == 0


class TestTokenMeterCost:
    """测试成本估算。"""

    def test_estimate_cost_gpt4o(self) -> None:
        """测试 GPT-4o 成本估算。"""
        tm = TokenMeter()
        cost = tm.estimate_cost(input_tokens=1000, output_tokens=500, model_name="gpt-4o")
        # input: 1000/1000 * 0.0025 = 0.0025
        # output: 500/1000 * 0.01 = 0.005
        # total: 0.0075
        expected = (1000 / 1000.0) * 0.0025 + (500 / 1000.0) * 0.01
        assert cost == pytest.approx(expected)

    def test_estimate_cost_claude(self) -> None:
        """测试 Claude 3.5 Sonnet 成本估算。"""
        tm = TokenMeter()
        cost = tm.estimate_cost(input_tokens=2000, output_tokens=1000, model_name="claude-3.5-sonnet")
        expected = (2000 / 1000.0) * 0.003 + (1000 / 1000.0) * 0.015
        assert cost == pytest.approx(expected)

    def test_estimate_cost_zero_tokens(self) -> None:
        """测试零 Token 成本为 0。"""
        tm = TokenMeter()
        assert tm.estimate_cost(0, 0) == 0.0

    def test_unknown_model_cost(self) -> None:
        """测试未知模型返回 0.0 而不崩溃。"""
        tm = TokenMeter()
        cost = tm.estimate_cost(1000, 500, model_name="unknown-model-v99")
        assert cost == 0.0


class TestTokenMeterBudgetReport:
    """测试预算报告生成。"""

    def test_build_budget_report(self) -> None:
        """测试压缩对比报告。"""
        tm = TokenMeter()
        before = [
            ContextItem(id="a", content="Long content " * 20, reason="important"),
            ContextItem(id="b", content="Another item " * 10, reason="relevant"),
            ContextItem(id="c", content="Remove me " * 5, reason="low"),
        ]
        after = [
            ContextItem(id="a", content="Long content " * 20, reason="important"),
            ContextItem(id="b", content="Another item " * 10, reason="relevant"),
        ]

        report = tm.build_budget_report(before, after)
        assert report["before_tokens"] > 0
        assert report["after_tokens"] > 0
        assert report["before_tokens"] > report["after_tokens"]
        assert report["compression_ratio"] > 0
        assert "c" in report["removed_ids"]

    def test_build_budget_report_no_change(self) -> None:
        """测试无变化时的报告。"""
        tm = TokenMeter()
        items = [ContextItem(id="a", content="Same content", reason="same")]
        report = tm.build_budget_report(items, items)
        assert report["compression_ratio"] == 0.0
        assert report["removed_ids"] == []

    def test_build_budget_report_empty_before(self) -> None:
        """测试空 before 列表。"""
        tm = TokenMeter()
        report = tm.build_budget_report([], [])
        assert report["before_tokens"] == 0
        assert report["after_tokens"] == 0
        assert report["compression_ratio"] == 0.0
        assert report["removed_ids"] == []


class TestTokenMeterFallback:
    """测试 fallback 模式检测。"""

    def test_is_fallback(self) -> None:
        """测试 is_fallback 属性。"""
        tm = TokenMeter()
        # 无论 tiktoken 是否可用，is_fallback 应正确反映状态
        assert isinstance(tm.is_fallback, bool)


class TestModelPrices:
    """测试 MODEL_PRICES 字典。"""

    def test_model_prices_has_entries(self) -> None:
        """测试 MODEL_PRICES 包含已知模型。"""
        assert "gpt-4o" in MODEL_PRICES
        assert "gpt-4o-mini" in MODEL_PRICES
        assert "claude-3.5-sonnet" in MODEL_PRICES
        assert len(MODEL_PRICES) >= 4

    def test_model_prices_format(self) -> None:
        """测试 MODEL_PRICES 格式为 (input_price, output_price)。"""
        for model, prices in MODEL_PRICES.items():
            assert isinstance(prices, tuple)
            assert len(prices) == 2
            assert isinstance(prices[0], float)
            assert isinstance(prices[1], float)
            assert prices[0] >= 0
            assert prices[1] >= 0
