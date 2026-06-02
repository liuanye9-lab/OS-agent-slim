"""tests/test_promotion_gate.py — Promotion Gate 测试。

验证 ValidationGate 的 promotion 决策逻辑。
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import SkillCandidate, ValidationResult
from stable_agent.core.validator import ValidationGate


@pytest.fixture
def gate():
    return ValidationGate()


def _make_candidate(**kwargs) -> SkillCandidate:
    """创建测试用 SkillCandidate。"""
    defaults = {
        "candidate_id": "sk_test",
        "source_run_id": "run_test",
        "failure_mode": "low_quality",
        "evidence_events": ["eval.completed"],
        "proposed_rule": "test rule",
        "when_to_use": "when eval score is low",
        "do_not_use_when": "when task is simple",
        "validation_plan": "validate with related tasks",
        "risk_level": "low",
    }
    defaults.update(kwargs)
    return SkillCandidate(**defaults)


def _make_validation(**kwargs) -> ValidationResult:
    """创建测试用 ValidationResult。"""
    defaults = {
        "passed": True,
        "schema_valid": True,
        "regression_count": 0,
        "score_delta": 0.05,
        "event_completeness": 1.0,
        "token_delta": 0.05,
        "validations_count": 2,
    }
    defaults.update(kwargs)
    return ValidationResult(**defaults)


class TestSchemaValidation:
    """Schema 验证测试。"""

    def test_valid_candidate_passes(self, gate):
        """有效 candidate 通过 schema 验证。"""
        candidate = _make_candidate()
        result = gate.validate_schema(candidate)
        assert result.schema_valid is True

    def test_missing_proposed_rule_fails(self, gate):
        """缺少 proposed_rule 失败。"""
        candidate = _make_candidate(proposed_rule="")
        result = gate.validate_schema(candidate)
        assert result.schema_valid is False

    def test_missing_validation_plan_fails(self, gate):
        """缺少 validation_plan 失败。"""
        candidate = _make_candidate(validation_plan="")
        result = gate.validate_schema(candidate)
        assert result.schema_valid is False

    def test_invalid_risk_level_fails(self, gate):
        """无效 risk_level 失败。"""
        candidate = _make_candidate(risk_level="invalid")
        result = gate.validate_schema(candidate)
        assert result.schema_valid is False

    def test_long_proposed_rule_fails(self, gate):
        """过长的 proposed_rule 失败。"""
        candidate = _make_candidate(proposed_rule="x" * 2001)
        result = gate.validate_schema(candidate)
        assert result.schema_valid is False


class TestPromotionDecision:
    """Promotion 决策测试。"""

    def test_can_promote_with_valid_conditions(self, gate):
        """满足所有条件可以 promote。"""
        candidate = _make_candidate()
        validation = _make_validation()
        assert gate.can_promote(candidate, validation) is True

    def test_cannot_promote_with_invalid_schema(self, gate):
        """schema 无效不能 promote。"""
        candidate = _make_candidate()
        validation = _make_validation(schema_valid=False)
        assert gate.can_promote(candidate, validation) is False

    def test_cannot_promote_with_insufficient_validations(self, gate):
        """验证次数不足不能 promote。"""
        candidate = _make_candidate()
        validation = _make_validation(validations_count=1)
        assert gate.can_promote(candidate, validation) is False

    def test_cannot_promote_with_regression(self, gate):
        """有回归不能 promote。"""
        candidate = _make_candidate()
        validation = _make_validation(regression_count=1)
        assert gate.can_promote(candidate, validation) is False

    def test_cannot_promote_with_low_score_delta(self, gate):
        """分数提升不足不能 promote。"""
        candidate = _make_candidate()
        validation = _make_validation(score_delta=0.01)
        assert gate.can_promote(candidate, validation) is False

    def test_cannot_promote_high_risk_auto(self, gate):
        """高风险 skill 不能自动 promote。"""
        candidate = _make_candidate(risk_level="high")
        validation = _make_validation()
        assert gate.can_promote(candidate, validation) is False


class TestCanaryDecision:
    """Canary 决策测试。"""

    def test_can_canary_with_minimal_conditions(self, gate):
        """满足最小条件可以 canary。"""
        candidate = _make_candidate()
        validation = _make_validation(validations_count=1, score_delta=0.02)
        assert gate.can_canary(candidate, validation) is True

    def test_cannot_canary_with_no_validations(self, gate):
        """无验证不能 canary。"""
        candidate = _make_candidate()
        validation = _make_validation(validations_count=0)
        assert gate.can_canary(candidate, validation) is False
