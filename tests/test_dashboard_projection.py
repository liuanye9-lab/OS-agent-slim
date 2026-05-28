"""Tests for DashboardProjection — V5.5."""
import pytest
from stable_agent.observation.dashboard_projection import DashboardProjection
from stable_agent.observation.decision_trace import DecisionTrace, DecisionEvidence, RunInsight


class TestDashboardProjection:
    @pytest.fixture
    def proj(self):
        return DashboardProjection()

    def test_project_trace_zh(self, proj):
        t = DecisionTrace(
            run_id="r1", stage="memory_retrieval",
            title_zh="检索记忆", title_en="Memory Retrieval",
            what_happened_zh="找到5条", what_happened_en="Found 5",
            why_zh="提升质量", why_en="Improve quality",
            next_step_zh="构建上下文", next_step_en="Build context",
            risk_level="low",
        )
        result = proj.project_trace(t, "zh")
        assert result["stage_title"] == "检索记忆"
        assert result["what"] == "找到5条"
        assert result["why"] == "提升质量"
        assert result["risk"]["level"] == "low"

    def test_project_trace_en(self, proj):
        t = DecisionTrace(
            run_id="r1", stage="memory_retrieval",
            title_zh="检索记忆", title_en="Memory Retrieval",
            what_happened_zh="找到5条", what_happened_en="Found 5",
            why_zh="提升质量", why_en="Improve quality",
        )
        result = proj.project_trace(t, "en")
        assert result["stage_title"] == "Memory Retrieval"
        assert result["what"] == "Found 5"

    def test_project_timeline(self, proj):
        traces = [
            DecisionTrace(run_id="r1", stage="task_intake", title_zh="接收"),
            DecisionTrace(run_id="r1", stage="completed", title_zh="完成"),
        ]
        timeline = proj.project_timeline(traces)
        assert len(timeline) == 2

    def test_project_insight(self, proj):
        insight = RunInsight(
            run_id="r1", quality_score=0.85,
            learning_triggered=True, skill_updated=True,
            improvement_summary_zh="输出更准确",
            improvement_summary_en="More accurate output",
        )
        result = proj.project_insight(insight, "zh")
        assert result["quality_score"] == 0.85
        assert result["learning_triggered"] is True

    def test_project_learning_triggered(self, proj):
        evidence = {
            "triggered": True, "passed": True,
            "baseline_score": 0.72, "candidate_score": 0.85, "score_delta": 0.13,
        }
        result = proj.project_learning(evidence, "zh")
        assert result["triggered"] is True

    def test_project_learning_not_triggered(self, proj):
        evidence = {"triggered": False, "reason_zh": "数据不足", "reason_en": "Insufficient data"}
        result = proj.project_learning(evidence, "zh")
        assert result["triggered"] is False
