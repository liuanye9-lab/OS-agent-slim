"""测试 DecisionTraceBuilder (Phase 4)。

验证:
1. DecisionTraceBuilder 不包含 chain_of_thought 字段
2. build_for_dashboard 返回完整 Dashboard 字段
3. RunLifecycle 元信息自动注入
"""

import pytest
from stable_agent.observation.decision_trace_builder import DecisionTraceBuilder


class TestDecisionTraceBuilder:
    """DecisionTraceBuilder 测试。"""

    @pytest.fixture
    def builder(self):
        return DecisionTraceBuilder()

    def test_build_for_dashboard_no_chain_of_thought(self, builder):
        """禁止 chain_of_thought / hidden_reasoning 字段。"""
        result = builder.build_for_dashboard(
            run_id="run-001",
            stage="planning",
            event_type="tool.started",
            payload={"tool_name": "test_tool"},
        )
        assert "chain_of_thought" not in result
        assert "hidden_reasoning" not in result

    def test_build_for_dashboard_includes_key_fields(self, builder):
        """Dashboard 必须包含核心字段。"""
        result = builder.build_for_dashboard(
            run_id="run-001",
            stage="acting",
            event_type="tool.completed",
            payload={"tool_name": "test_tool", "ok": True},
        )
        assert result["run_id"] == "run-001"
        assert "decision_summary_zh" in result
        assert "decision_summary_en" in result
        assert "why_zh" in result
        assert "why_en" in result
        assert "next_step_zh" in result
        assert "next_step_en" in result
        assert "progress_pct" in result
        assert "avatar_state" in result
        assert "stage_label_zh" in result

    def test_build_for_dashboard_uses_runlifecycle(self, builder):
        """验证 RunLifecycle 元信息注入。"""
        result = builder.build_for_dashboard(
            run_id="run-001",
            stage="evaluating",
            event_type="eval.completed",
            payload={},
        )
        # RunLifecycle 元信息应该被注入
        assert result["stage_label_zh"] == "评估结果"
        assert result["progress_pct"] == 85

    def test_payload_overrides_runlifecycle(self, builder):
        """Payload 中的显式字段覆盖 RunLifecycle 默认值。"""
        result = builder.build_for_dashboard(
            run_id="run-001",
            stage="planning",
            event_type="tool.started",
            payload={
                "decision_summary_zh": "自定义决策",
                "progress_pct": 99,
            },
        )
        assert result["decision_summary_zh"] == "自定义决策"
        assert result["progress_pct"] == 99

    def test_unknown_stage_fallback(self, builder):
        """未知阶段 fallback 到 CREATED。"""
        result = builder.build_for_dashboard(
            run_id="run-001",
            stage="nonexistent",
            event_type="test.event",
            payload={},
        )
        assert result["stage_label_zh"] == "已创建"
        assert result["progress_pct"] == 0
