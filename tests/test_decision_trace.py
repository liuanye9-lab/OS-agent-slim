"""Tests for DecisionTrace data model — V5.5."""
import pytest
from datetime import datetime
from stable_agent.observation.decision_trace import (
    DecisionTrace, DecisionEvidence, RunInsight, DecisionStage, EventImportance
)


class TestDecisionEvidence:
    def test_defaults(self):
        e = DecisionEvidence()
        assert e.evidence_type == ""
        assert e.selected is True
        assert e.confidence == 0.0

    def test_full_init(self):
        e = DecisionEvidence(
            evidence_type="memory", title="用户偏好",
            summary_zh="用户喜欢简洁输出", summary_en="User prefers concise output",
            source="mem-001", confidence=0.95, selected=True,
            reason_zh="高度相关", reason_en="Highly relevant"
        )
        assert e.evidence_type == "memory"
        assert e.source == "mem-001"
        assert e.confidence == 0.95


class TestDecisionTrace:
    def test_defaults(self):
        t = DecisionTrace()
        assert t.stage == "execution"
        assert t.importance == "normal"
        assert t.risk_level == "none"
        assert isinstance(t.timestamp, datetime)

    def test_full_init(self):
        t = DecisionTrace(
            run_id="run-1", span_id="span-1", stage="memory_retrieval",
            title_zh="检索记忆", title_en="Memory Retrieval",
            what_happened_zh="找到5条记忆", what_happened_en="Found 5 memories",
            why_zh="提升输出质量", why_en="Improve quality",
            risk_level="low", confidence=0.9, importance="normal",
            token_used=2000, token_budget=8000,
            avatar_state="reading_notes"
        )
        assert t.run_id == "run-1"
        assert t.stage == "memory_retrieval"
        assert t.risk_level == "low"
        assert t.avatar_state == "reading_notes"

    def test_evidence_list(self):
        e = DecisionEvidence(title="测试依据", summary_zh="测试摘要")
        t = DecisionTrace(evidence=[e], discarded_evidence=[DecisionEvidence(selected=False)])
        assert len(t.evidence) == 1
        assert len(t.discarded_evidence) == 1
        assert t.discarded_evidence[0].selected is False

    def test_no_hidden_cot(self):
        """DecisionTrace 不应包含隐藏 chain-of-thought 字段"""
        t = DecisionTrace()
        attrs = [a for a in dir(t) if not a.startswith('_')]
        # 不应有 'cot' / 'thought' / 'reasoning' 等隐藏字段
        hidden = [a for a in attrs if 'cot' in a or 'thought' in a.lower()]
        assert len(hidden) == 0


class TestRunInsight:
    def test_defaults(self):
        r = RunInsight()
        assert r.learning_triggered is False
        assert r.skill_updated is False
        assert r.quality_score == 0.0

    def test_failure_insight(self):
        r = RunInsight(
            run_id="run-fail", quality_score=0.35,
            failure_reason_zh="模型输出太短", failure_reason_en="Output too short",
            next_time_rule_zh="增加输出长度要求", next_time_rule_en="Enforce output length"
        )
        assert r.failure_reason_zh == "模型输出太短"
        assert r.next_time_rule_zh == "增加输出长度要求"


class TestDecisionStage:
    def test_stages_exist(self):
        stages = DecisionStage.__args__
        assert "task_intake" in stages
        assert "memory_retrieval" in stages
        assert "evaluation" in stages
        assert "skill_learning" in stages
        assert "completed" in stages
        assert "failed" in stages


class TestEventImportance:
    def test_importance_levels(self):
        levels = EventImportance.__args__
        assert "debug" in levels
        assert "normal" in levels
        assert "important" in levels
        assert "critical" in levels
