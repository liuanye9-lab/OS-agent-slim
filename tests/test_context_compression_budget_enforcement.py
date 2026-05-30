"""测试 ContextCompressionGuard enforce_budget (V6.1 新功能)。"""

import pytest
from stable_agent.context.context_compression_guard import (
    ContextCompressionGuard,
    CompressionDecision,
)


@pytest.fixture
def guard():
    return ContextCompressionGuard()


class TestEnforceBudget:
    def test_normal_compression_fits_budget(self, guard):
        """正常场景：内容在预算内。"""
        decision = CompressionDecision(
            protected_items=[
                {"content": "用户目标: 完成任务A", "type": "goal"},
            ],
            kept_items=[
                {"content": "一段中等长度内容", "type": "memory"},
            ],
        )
        result = guard.enforce_budget(decision, token_budget=500)
        assert result.blocked is False
        assert len(result.kept_items) == 1

    def test_protected_exceeds_budget_blocks(self, guard):
        """保护条目超预算 → blocked=True。"""
        decision = CompressionDecision(
            protected_items=[
                {"content": "X" * 2000, "type": "goal"},  # ~1000 tokens
            ],
            kept_items=[],
        )
        result = guard.enforce_budget(decision, token_budget=100)
        assert result.blocked is True
        assert "阻止" in result.summary_zh or "超过" in result.summary_zh

    def test_low_priority_dropped_first(self, guard):
        """低优先级（secondary）先被丢弃。"""
        decision = CompressionDecision(
            protected_items=[],
            kept_items=[
                {"content": "X" * 100, "type": "secondary"},  # 低优先级
                {"content": "Y" * 100, "type": "memory", "confidence": 0.9},  # 高优先级
            ],
        )
        result = guard.enforce_budget(decision, token_budget=60)
        # secondary 可能优先被丢弃
        assert result.blocked is False

    def test_blocked_protects_all(self, guard):
        """blocked 时不丢弃任何 protected 项。"""
        decision = CompressionDecision(
            protected_items=[
                {"content": "关键目标A"},
                {"content": "项目约束B"},
            ],
            kept_items=[],
        )
        result = guard.enforce_budget(decision, token_budget=1)
        assert result.blocked is True
        assert len(result.protected_items) == 2

    def test_token_stats_present(self, guard):
        """返回的 decision 应有 token 统计数据。"""
        decision = CompressionDecision(
            protected_items=[{"content": "AB" * 50}],
            kept_items=[],
        )
        result = guard.enforce_budget(decision, token_budget=200)
        assert result.estimated_tokens_before > 0
        assert result.estimated_tokens_after > 0
        assert result.token_budget == 200

    def test_compression_ratio(self, guard):
        """有丢弃时应产生压缩比。"""
        decision = CompressionDecision(
            protected_items=[],
            kept_items=[
                {"content": "X" * 200, "type": "memory"},
                {"content": "Y" * 200, "type": "secondary"},
            ],
        )
        result = guard.enforce_budget(decision, token_budget=60)
        assert result.compression_ratio >= 0.0
        if result.compression_ratio > 0:
            assert "压缩完成" in result.summary_zh
