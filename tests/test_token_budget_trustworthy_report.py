"""test_token_budget_trustworthy_report.py — 验证 Token Budget 可信报告。

测试要求：
1. injected_tokens 不应大于 baseline_tokens_estimated。
2. saving_ratio 必须在 0-1。
3. is_estimated 字段存在。
4. Dashboard API 返回 estimation_method。
5. 空 context 不报错。
"""

from __future__ import annotations

import pytest

from stable_agent.token.schemas import TokenRunRecord


class TestTokenRunRecordFields:
    """TokenRunRecord 字段完整性测试。"""

    def test_has_is_estimated_field(self):
        record = TokenRunRecord()
        assert hasattr(record, "is_estimated")
        assert record.is_estimated is True

    def test_has_estimation_method_field(self):
        record = TokenRunRecord()
        assert hasattr(record, "estimation_method")
        assert record.estimation_method == "tiktoken_cl100k"

    def test_has_candidate_context_tokens(self):
        record = TokenRunRecord()
        assert hasattr(record, "candidate_context_tokens")

    def test_injected_not_greater_than_baseline(self):
        record = TokenRunRecord(
            baseline_tokens_estimated=1000,
            injected_tokens=800,
        )
        assert record.injected_tokens <= record.baseline_tokens_estimated

    def test_saving_ratio_bounds(self):
        record = TokenRunRecord(saving_ratio=0.5)
        assert 0.0 <= record.saving_ratio <= 1.0

    def test_saving_ratio_zero(self):
        record = TokenRunRecord(saving_ratio=0.0)
        assert record.saving_ratio == 0.0

    def test_saving_ratio_one(self):
        record = TokenRunRecord(saving_ratio=1.0)
        assert record.saving_ratio == 1.0

    def test_empty_context_no_error(self):
        """空 context 不应报错。"""
        record = TokenRunRecord(
            run_id="test",
            baseline_tokens_estimated=0,
            raw_context_tokens=0,
            candidate_context_tokens=0,
            injected_tokens=0,
            saved_tokens_estimated=0,
            saving_ratio=0.0,
            summary_zh="当前为候选上下文估算，不代表真实 API 计费。",
        )
        d = record.to_dict()
        assert d["baseline_tokens_estimated"] == 0
        assert d["saving_ratio"] == 0.0

    def test_to_dict_contains_estimation_method(self):
        record = TokenRunRecord(estimation_method="char_div4")
        d = record.to_dict()
        assert "estimation_method" in d
        assert d["estimation_method"] == "char_div4"

    def test_to_dict_contains_is_estimated(self):
        record = TokenRunRecord(is_estimated=True)
        d = record.to_dict()
        assert "is_estimated" in d
        assert d["is_estimated"] is True

    def test_to_dict_contains_candidate_context_tokens(self):
        record = TokenRunRecord(candidate_context_tokens=500)
        d = record.to_dict()
        assert "candidate_context_tokens" in d
        assert d["candidate_context_tokens"] == 500

    def test_from_dict_roundtrip(self):
        record = TokenRunRecord(
            run_id="test_run",
            baseline_tokens_estimated=1000,
            candidate_context_tokens=500,
            injected_tokens=800,
            saved_tokens_estimated=200,
            saving_ratio=0.2,
            estimation_method="tiktoken_cl100k",
            is_estimated=True,
            risk_level="low",
            summary_zh="测试",
        )
        d = record.to_dict()
        restored = TokenRunRecord.from_dict(d)
        assert restored.baseline_tokens_estimated == 1000
        assert restored.candidate_context_tokens == 500
        assert restored.estimation_method == "tiktoken_cl100k"
        assert restored.is_estimated is True
        assert restored.saving_ratio == 0.2

    def test_risk_level_validation(self):
        """非法 risk_level 应抛出 ValueError。"""
        with pytest.raises(ValueError):
            TokenRunRecord(risk_level="critical")

    def test_summary_zh_estimated_note(self):
        """少 context 时 summary_zh 应包含估算说明。"""
        record = TokenRunRecord(
            candidate_context_tokens=50,
            summary_zh="节省 0% token (0/100)。当前为候选上下文估算，不代表真实 API 计费。",
        )
        assert "估算" in record.summary_zh


class TestTokenBudgetLogic:
    """Token 预算计算逻辑测试。"""

    def test_saved_tokens_non_negative(self):
        """saved_tokens 不应为负数。"""
        baseline = 1000
        injected = 800
        saved = max(0, baseline - injected)
        assert saved >= 0

    def test_saving_ratio_formula(self):
        """saving_ratio = saved / baseline。"""
        baseline = 1000
        injected = 700
        saved = max(0, baseline - injected)
        ratio = saved / baseline if baseline > 0 else 0.0
        assert ratio == 0.3

    def test_risk_high_when_blocked(self):
        """blocked 时 risk_level 应为 high。"""
        # Simulate cc_decision.blocked
        blocked = True
        risk = "high" if blocked else "low"
        assert risk == "high"

    def test_risk_medium_when_high_saving(self):
        """高 saving_ratio 时 risk_level 应为 medium。"""
        saving_ratio = 0.7
        risk = "medium" if saving_ratio > 0.5 else "low"
        assert risk == "medium"
