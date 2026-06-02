"""tests/test_delayed_validation.py — Delayed Validation 测试。

验证 DelayedValidationGate 的延迟验证逻辑。
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import SkillCandidate
from stable_agent.core.delayed_validation import DelayedValidationGate, TaskGroup


@pytest.fixture
def gate():
    return DelayedValidationGate()


def _make_candidate(**kwargs) -> SkillCandidate:
    defaults = {
        "candidate_id": "sk_test",
        "source_run_id": "run_test",
        "failure_mode": "low_quality",
        "evidence_events": [],
        "proposed_rule": "test rule",
        "when_to_use": "when eval score is low",
        "do_not_use_when": "when task is simple",
        "validation_plan": "validate with related tasks",
        "risk_level": "low",
    }
    defaults.update(kwargs)
    return SkillCandidate(**defaults)


class TestDelayedValidation:
    """延迟验证测试。"""

    @pytest.mark.asyncio
    async def test_empty_holdout_passes(self, gate):
        """空 holdout tasks 直接通过。"""
        candidate = _make_candidate()
        group = gate.create_task_group("g1", "coding")
        record = await gate.validate_with_related_tasks(candidate, group)
        assert record.passed is True

    @pytest.mark.asyncio
    async def test_with_holdout_tasks(self, gate):
        """有 holdout tasks 时执行验证。"""
        candidate = _make_candidate()
        group = gate.create_task_group(
            "g1", "coding",
            holdout_tasks=[{"task_input": "test task 1"}, {"task_input": "test task 2"}],
        )
        record = await gate.validate_with_related_tasks(candidate, group)
        assert record.validation_id
        assert record.candidate_id == "sk_test"
        assert len(record.baseline_scores) == 2
        assert len(record.candidate_scores) == 2

    @pytest.mark.asyncio
    async def test_score_delta_calculation(self, gate):
        """分数 delta 计算正确。"""
        candidate = _make_candidate()
        group = gate.create_task_group(
            "g1", "coding",
            holdout_tasks=[{"task_input": "test"}],
        )
        record = await gate.validate_with_related_tasks(candidate, group)
        # 模拟分数: baseline=0.7, candidate=0.75, delta=0.05
        assert record.score_delta > 0

    @pytest.mark.asyncio
    async def test_regression_detection(self, gate):
        """回归检测。"""
        candidate = _make_candidate()
        group = gate.create_task_group(
            "g1", "coding",
            holdout_tasks=[{"task_input": "test"}],
        )
        record = await gate.validate_with_related_tasks(candidate, group)
        # 模拟无回归
        assert record.regression_count == 0


class TestTaskGroup:
    """TaskGroup 测试。"""

    def test_create_task_group(self, gate):
        """创建任务组。"""
        group = gate.create_task_group("g1", "coding", skill_tags=["refactor"])
        assert group.group_id == "g1"
        assert group.domain == "coding"
        assert group.skill_tags == ["refactor"]

    def test_empty_holdout(self, gate):
        """空 holdout tasks。"""
        group = gate.create_task_group("g1", "coding")
        assert group.holdout_tasks == []
