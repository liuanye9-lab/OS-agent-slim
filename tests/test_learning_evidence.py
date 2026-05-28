"""Tests for LearningEvidence + RunInsightGenerator — V5.5."""
import pytest
from stable_agent.observation.learning_evidence import LearningEvidence
from stable_agent.observation.run_insight import RunInsightGenerator
from stable_agent.observation.decision_trace import DecisionTrace


class TestLearningEvidence:
    @pytest.fixture
    def le(self):
        return LearningEvidence()

    def test_no_learning_reason(self, le):
        result = le.no_learning_reason()
        assert result["triggered"] is False
        assert len(result["reason_zh"]) > 0
        assert len(result["reason_en"]) > 0

    def test_build_from_validation_passed(self, le):
        result = le.build_from_validation({
            "passed": True,
            "baseline_score": 0.72,
            "candidate_score": 0.85,
            "score_delta": 0.13,
        })
        assert result["triggered"] is True
        assert result["passed"] is True
        assert result["baseline_score"] == 0.72
        assert result["candidate_score"] == 0.85

    def test_build_from_validation_failed(self, le):
        result = le.build_from_validation({
            "passed": False,
            "baseline_score": 0.80,
            "candidate_score": 0.78,
            "score_delta": -0.02,
        })
        assert result["passed"] is False
        assert result["baseline_score"] == 0.80


class TestRunInsightGenerator:
    @pytest.fixture
    def gen(self):
        return RunInsightGenerator()

    def test_generate_with_traces(self, gen):
        traces = [
            DecisionTrace(run_id="r1", stage="task_intake", quality_score=0.8),
            DecisionTrace(run_id="r1", stage="memory_retrieval", quality_score=0.9,
                          confidence=0.7, token_used=2000, token_budget=8000),
            DecisionTrace(run_id="r1", stage="completed", quality_score=0.85),
        ]
        insight = gen.generate(traces, "r1")
        assert insight.run_id == "r1"
        assert len(insight.task_summary_zh) > 0
        assert insight.quality_score > 0
        assert insight.token_roi >= 0

    def test_generate_empty_traces(self, gen):
        insight = gen.generate([], "r-empty")
        assert insight.run_id == "r-empty"
        assert insight.quality_score == 0.0

    def test_failed_task(self, gen):
        traces = [
            DecisionTrace(run_id="r-fail", stage="failed", risk_level="high")
        ]
        insight = gen.generate(traces, "r-fail")
        assert insight.failure_reason_zh is not None
        assert insight.next_time_rule_zh is not None
