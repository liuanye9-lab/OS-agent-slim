"""Tests for DecisionNarrator — V5.5."""
import pytest
from stable_agent.explanation.decision_narrator import DecisionNarrator


class TestDecisionNarrator:
    @pytest.fixture
    def narrator(self):
        return DecisionNarrator()

    def test_narrate_mcp_call_received(self, narrator):
        dt = narrator.narrate_event("mcp.call.received", {}, "run-1")
        assert dt.run_id == "run-1"
        assert dt.stage == "task_intake"
        assert len(dt.title_zh) > 0
        assert len(dt.title_en) > 0
        assert "hidden" not in dt.title_zh.lower()

    def test_narrate_memory_retrieved(self, narrator):
        payload = {"selected_count": 5, "discarded_count": 12, "total_count": 17}
        dt = narrator.narrate_event("memory.retrieved", payload, "run-2")
        assert dt.stage == "memory_retrieval"
        assert len(dt.what_happened_zh) > 0
        assert len(dt.why_zh) > 0
        assert len(dt.next_step_zh) > 0

    def test_narrate_task_completed(self, narrator):
        payload = {"overall_score": 0.85}
        dt = narrator.narrate_event("task.completed", payload, "run-3")
        assert dt.stage == "completed"
        assert dt.confidence >= 0

    def test_narrate_task_failed(self, narrator):
        dt = narrator.narrate_event("task.failed", {"error": "timeout"}, "run-4")
        assert dt.stage == "failed"
        assert dt.risk_level in ("high", "medium")

    def test_narrate_unknown_event_fallback(self, narrator):
        dt = narrator.narrate_event("unknown.event", {}, "run-5")
        assert dt.stage == "execution"  # fallback
        assert len(dt.title_zh) > 0

    def test_narrate_stage_method(self, narrator):
        result = narrator.narrate_stage("memory_retrieval", {"selected_count": 3})
        assert "title_zh" in result
        assert "title_en" in result
        assert len(result["what_zh"]) > 0

    def test_explain_evidence(self, narrator):
        payload = {
            "selected": [{"type": "memory", "content": "用户偏好", "confidence": 0.9}]
        }
        evidence = narrator.explain_evidence(payload)
        assert isinstance(evidence, list)

    def test_explain_discarded(self, narrator):
        payload = {
            "discarded": [{"type": "memory", "content": "无关信息"}]
        }
        discarded = narrator.explain_discarded(payload)
        assert isinstance(discarded, list)

    def test_skillopt_events(self, narrator):
        for event in ["skillopt.rollout.collected", "skillopt.patch.proposed",
                       "skillopt.validation.completed", "skillopt.exported"]:
            dt = narrator.narrate_event(event, {}, "run")
            assert dt.stage in ("skill_learning", "skill_validation", "skill_export")

    def test_bilingual_output(self, narrator):
        dt = narrator.narrate_event("memory.retrieved", {"selected_count": 3})
        assert len(dt.what_happened_zh) > 0
        assert len(dt.what_happened_en) > 0

    def test_narrator_explain_why_returns_string(self, narrator):
        """DecisionNarrator 能为已知事件类型生成 explain_why。"""
        result = narrator.explain_why("context.budgeted", {}, "zh")
        assert isinstance(result, str) and len(result) > 0

    def test_narrator_explain_why_english(self, narrator):
        """explain_why 支持英文。"""
        result = narrator.explain_why("memory.retrieved", {}, "en")
        assert isinstance(result, str) and len(result) > 0

    def test_narrator_summarize_discarded_returns_list(self, narrator):
        """summarize_discarded 返回 dict 列表。"""
        payload = {"discarded": [{"type": "memory", "title": "过期记忆", "reason_zh": "已过期", "reason_en": "Expired"}]}
        result = narrator.summarize_discarded(payload, "zh")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["selected"] == False

    def test_decision_trace_no_chain_of_thought(self):
        """DecisionTrace 不包含 chain_of_thought 字段。"""
        from stable_agent.observation.decision_trace import DecisionTrace
        trace = DecisionTrace(
            run_id="r1", span_id="s1", stage="thinking",
            title_zh="", title_en="",
            what_happened_zh="", what_happened_en="",
            why_zh="", why_en="",
            evidence=[], discarded_evidence=[],
            decision_zh="", decision_en="",
            next_step_zh="", next_step_en="",
            risk_level="low", confidence=0.8,
            token_used=100, token_budget=1000,
            avatar_state="thinking",
            raw_payload={},
        )
        assert not hasattr(trace, 'chain_of_thought')
