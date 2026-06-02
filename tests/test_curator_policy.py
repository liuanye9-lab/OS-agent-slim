"""tests/test_curator_policy.py — Curator 策略测试。

验证 CuratorService 的 learning-worthy 判断和 candidate 生成。
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import RunTrace, SkillCandidate
from stable_agent.core.curator import CuratorService


@pytest.fixture
def curator():
    return CuratorService()


def _make_trace(**kwargs) -> RunTrace:
    """创建测试用 RunTrace。"""
    defaults = {
        "run_id": "run_test",
        "ok": True,
        "status": "completed",
        "eval_passed": True,
        "eval_score": 0.8,
        "events": [],
        "output_text": "test output",
        "artifacts": {},
        "si_report": None,
    }
    defaults.update(kwargs)
    return RunTrace(**defaults)


class TestLearningWorthy:
    """learning-worthy 判断测试。"""

    def test_low_eval_score_is_learning_worthy(self, curator):
        """eval_score < 0.75 值得学习。"""
        trace = _make_trace(eval_score=0.5)
        result = curator.analyze_trace(trace)
        assert result["is_learning_worthy"] is True

    def test_high_eval_score_not_learning_worthy(self, curator):
        """eval_score >= 0.75 不值得学习。"""
        trace = _make_trace(eval_score=0.9)
        result = curator.analyze_trace(trace)
        assert result["is_learning_worthy"] is False

    def test_force_eval_failed_is_learning_worthy(self, curator):
        """force_eval_failed=true 值得学习。"""
        trace = _make_trace(artifacts={"force_eval_failed": True})
        result = curator.analyze_trace(trace)
        assert result["is_learning_worthy"] is True

    def test_missing_events_is_learning_worthy(self, curator):
        """missing_required_events 值得学习。"""
        trace = _make_trace(artifacts={"missing_required_events": ["task.received"]})
        result = curator.analyze_trace(trace)
        assert result["is_learning_worthy"] is True

    def test_dashboard_replay_failure_is_learning_worthy(self, curator):
        """dashboard_replay_ok=false 值得学习。"""
        trace = _make_trace(artifacts={"dashboard_replay_ok": False})
        result = curator.analyze_trace(trace)
        assert result["is_learning_worthy"] is True


class TestCandidateGeneration:
    """candidate 生成测试。"""

    def test_learning_worthy_generates_candidate(self, curator):
        """learning-worthy trace 生成 candidate。"""
        trace = _make_trace(eval_score=0.5)
        candidates = curator.propose_candidates(trace)
        assert len(candidates) == 1
        assert isinstance(candidates[0], SkillCandidate)

    def test_not_learning_worthy_no_candidate(self, curator):
        """非 learning-worthy trace 不生成 candidate。"""
        trace = _make_trace(eval_score=0.9)
        candidates = curator.propose_candidates(trace)
        assert len(candidates) == 0

    def test_candidate_has_required_fields(self, curator):
        """candidate 包含必需字段。"""
        trace = _make_trace(eval_score=0.5)
        candidates = curator.propose_candidates(trace)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.candidate_id
        assert c.source_run_id
        assert c.proposed_rule
        assert c.when_to_use
        assert c.validation_plan
        assert c.risk_level in ("low", "medium", "high")


class TestRewardProxy:
    """reward proxy 计算测试。"""

    def test_reward_proxy_range(self, curator):
        """reward proxy 在 [0, 1] 范围内。"""
        trace = _make_trace(eval_score=0.5)
        result = curator.analyze_trace(trace)
        assert 0.0 <= result["reward_proxy"] <= 1.0

    def test_high_eval_high_reward(self, curator):
        """高 eval_score 对应较高 reward。"""
        trace_high = _make_trace(eval_score=0.9)
        trace_low = _make_trace(eval_score=0.3)
        reward_high = curator.analyze_trace(trace_high)["reward_proxy"]
        reward_low = curator.analyze_trace(trace_low)["reward_proxy"]
        assert reward_high > reward_low


class TestFeedbackIngestion:
    """反馈摄入测试。"""

    def test_dont_do_this_generates_candidate(self, curator):
        """dont_do_this 反馈生成 candidate。"""
        candidates = curator.ingest_feedback("run_001", "不要这样做", "dont_do_this")
        assert len(candidates) == 1
        assert candidates[0].do_not_use_when == "不要这样做"

    def test_remember_no_candidate(self, curator):
        """remember 反馈不生成 candidate。"""
        candidates = curator.ingest_feedback("run_001", "记住这个", "remember")
        assert len(candidates) == 0
