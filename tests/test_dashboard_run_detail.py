"""测试 Dashboard Run Detail (Phase 11+12)。

验证 Dashboard run detail 可访问。
"""

import pytest


class TestDashboardRunDetail:
    """Dashboard Run Detail 测试。"""

    def test_run_lifecycle_stages_cover_full_flow(self):
        """验证 RunLifecycle 覆盖完整闭环。"""
        from stable_agent.runtime.run_lifecycle import RunStage, get_stage_meta

        # Task → Plan → Action → Observation → Trace → Eval →
        # BadCase → Regression → Skill Patch → Validation Gate →
        # Human Review → Export best_skill.md
        closed_loop_stages = [
            RunStage.CREATED,
            RunStage.RECEIVED,
            RunStage.INTENT_PARSING,
            RunStage.CONTEXT_BUDGETING,
            RunStage.MEMORY_RETRIEVING,
            RunStage.CONTEXT_BUILDING,
            RunStage.PLANNING,
            RunStage.ACTING,
            RunStage.OBSERVING,
            RunStage.EVALUATING,
            RunStage.FAILURE_ATTRIBUTION,
            RunStage.REGRESSION_GENERATION,
            RunStage.SKILL_PATCH_PROPOSAL,
            RunStage.VALIDATION,
            RunStage.HUMAN_REVIEW,
            RunStage.EXPORTING,
            RunStage.COMPLETED,
        ]
        for stage in closed_loop_stages:
            meta = get_stage_meta(stage)
            assert meta.stage == stage
            assert meta.status_text_zh  # 中文字段非空

    def test_decision_trace_fields_for_dashboard(self):
        """验证 DecisionTrace 字段 Dashboard 可用。"""
        from stable_agent.observation.decision_trace_builder import DecisionTraceBuilder

        builder = DecisionTraceBuilder()
        result = builder.build_for_dashboard(
            run_id="run-dash-001",
            stage="evaluating",
            event_type="eval.completed",
            payload={
                "tool_name": "eval.evaluate",
                "quality_score": 0.85,
                "hallucination_detected": False,
            },
        )
        # Dashboard 展示需要的字段
        assert result["run_id"] == "run-dash-001"
        assert result["stage"] == "evaluating"
        assert result["progress_pct"] == 85

    def test_all_stage_labels_zh(self):
        """所有阶段都有中文字段。"""
        from stable_agent.runtime.run_lifecycle import RunStage, get_stage_meta
        for stage in RunStage:
            meta = get_stage_meta(stage)
            assert meta.status_text_zh, f"{stage.value} 缺少 status_text_zh"
            assert meta.default_why_zh, f"{stage.value} 缺少 default_why_zh"
