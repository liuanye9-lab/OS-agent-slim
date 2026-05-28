"""Tests for RunInsight — V5.5."""
import pytest
from stable_agent.observation.run_insight import RunInsightGenerator
from stable_agent.observation.decision_trace import DecisionTrace


class TestRunInsight:
    @pytest.fixture
    def gen(self):
        return RunInsightGenerator()

    def test_generate_basic(self, gen):
        traces = [
            DecisionTrace(run_id="r1", stage="completed", quality_score=0.82)
        ]
        insight = gen.generate(traces, "r1")
        assert insight.run_id == "r1"
        assert 0 <= insight.quality_score <= 1

    def test_generate_with_all_metrics(self, gen):
        traces = [
            DecisionTrace(run_id="r2", stage="task_intake", token_used=500, token_budget=8000),
            DecisionTrace(run_id="r2", stage="memory_retrieval", token_used=2000, quality_score=0.9),
            DecisionTrace(run_id="r2", stage="completed", quality_score=0.88, token_used=5000),
        ]
        insight = gen.generate(traces, "r2")
        assert insight.run_id == "r2"
        assert insight.quality_score > 0
        assert insight.token_roi >= 0
        assert insight.memory_hit_rate >= 0

    def test_generate_learning_triggered(self, gen):
        traces = [
            DecisionTrace(run_id="r3", stage="skill_learning"),
            DecisionTrace(run_id="r3", stage="skill_validation", quality_score=0.9),
            DecisionTrace(run_id="r3", stage="completed", quality_score=0.85),
        ]
        insight = gen.generate(traces, "r3")
        assert insight.learning_triggered is True

    def test_generate_no_learning(self, gen):
        traces = [
            DecisionTrace(run_id="r4", stage="task_intake"),
            DecisionTrace(run_id="r4", stage="completed", quality_score=0.7),
        ]
        insight = gen.generate(traces, "r4")
        assert insight.learning_triggered is False

    def test_generate_empty_traces(self, gen):
        insight = gen.generate([], "r-empty")
        assert insight.run_id == "r-empty"
        assert insight.quality_score == 0.0
        assert insight.learning_triggered is False

    def test_generate_bilingual_output(self, gen):
        traces = [DecisionTrace(run_id="r5", stage="completed", quality_score=0.8)]
        insight = gen.generate(traces, "r5")
        assert len(insight.task_summary_zh) > 0
        assert len(insight.task_summary_en) > 0
