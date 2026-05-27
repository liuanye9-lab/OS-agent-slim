"""Tests for Dashboard V4 SkillOpt 端点与事件。

验证 Dashboard 新增的 SkillOpt API 路由和 SkillOpt 事件大白话解释。
不使用 TestClient（避免 httpx 依赖），改用直接函数调用验证。
"""

import pytest
from stable_agent.dashboard import Dashboard
from stable_agent.trace_event_bus import EventBus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def dashboard(event_bus):
    return Dashboard(event_bus)


# ============================================================================
# Dashboard SkillOpt 端点基础
# ============================================================================

class TestDashboardSkillOptEndpoints:
    """验证 skillopt 端点路由已正确注册。"""

    def test_status_endpoint_mounted(self, dashboard):
        route_paths = [r.path for r in dashboard.app.routes]
        assert "/api/skillopt/status" in route_paths

    def test_current_skill_endpoint_mounted(self, dashboard):
        route_paths = [r.path for r in dashboard.app.routes]
        assert "/api/skillopt/current_skill" in route_paths

    def test_recent_epochs_endpoint_mounted(self, dashboard):
        route_paths = [r.path for r in dashboard.app.routes]
        assert "/api/skillopt/recent_epochs" in route_paths

    def test_old_explain_route_still_mounted(self, dashboard):
        route_paths = [r.path for r in dashboard.app.routes]
        assert "/explain/{event_type}" in route_paths


# ============================================================================
# SkillOpt 事件大白话验证
# ============================================================================

class TestSkillOptExplanations:
    """验证 V4 skillopt 事件的大白话解释正确性。"""

    def test_skillopt_explanations_in_plain_language(self):
        from stable_agent.plain_language import PlainLanguageExplainer
        explainer = PlainLanguageExplainer()

        events = [
            "skillopt.epoch_started",
            "skillopt.rollouts_collected",
            "skillopt.failures_analyzed",
            "skillopt.successes_analyzed",
            "skillopt.patch_merged",
            "skillopt.patch_ranked",
            "skillopt.candidate_created",
            "skillopt.validation_passed",
            "skillopt.validation_failed",
            "skillopt.rejected_buffer_updated",
            "skillopt.slow_update_created",
            "skillopt.best_skill_exported",
        ]
        for event in events:
            explanation = explainer.explain(event)
            assert explanation != explainer.DEFAULT_EXPLANATION, \
                f"事件 {event} 缺少大白话解释"
            assert len(explanation) > 5, \
                f"事件 {event} 大白话解释太短"

    def test_skillopt_explain_with_context(self):
        from stable_agent.plain_language import PlainLanguageExplainer
        explainer = PlainLanguageExplainer()

        result = explainer.explain_with_context(
            "skillopt.validation_passed",
            {"baseline_score": 0.72, "candidate_score": 0.85}
        )
        assert "0.72" in result or "0.85" in result or "验证" in result

    def test_each_skillopt_event_unique(self):
        from stable_agent.plain_language import PlainLanguageExplainer
        explainer = PlainLanguageExplainer()

        events = [
            "skillopt.epoch_started",
            "skillopt.failures_analyzed",
            "skillopt.successes_analyzed",
            "skillopt.patch_merged",
            "skillopt.candidate_created",
            "skillopt.validation_passed",
            "skillopt.validation_failed",
        ]
        explanations = [explainer.explain(e) for e in events]
        # 至少应该有多个不同的大白话
        unique = set(explanations)
        assert len(unique) >= len(events) - 1, \
            f"V4 skillopt 事件大白话重复度过高，unique={len(unique)}/{len(events)}"


# ============================================================================
# SpanType 完整性
# ============================================================================

class TestSkillOptSpanTypes:
    """验证所有 V4 skillopt SpanType 值都存在。"""

    def test_skillopt_span_types(self):
        from stable_agent.models import SpanType

        expected = [
            "skillopt.epoch_started",
            "skillopt.rollouts_collected",
            "skillopt.failures_analyzed",
            "skillopt.successes_analyzed",
            "skillopt.patch_merged",
            "skillopt.patch_ranked",
            "skillopt.candidate_created",
            "skillopt.validation_passed",
            "skillopt.validation_failed",
            "skillopt.rejected_buffer_updated",
            "skillopt.slow_update_created",
            "skillopt.best_skill_exported",
        ]
        for val in expected:
            assert SpanType(val) is not None, f"SpanType 缺少: {val}"

    def test_skillopt_events_in_plain_language(self):
        from stable_agent.plain_language import PlainLanguageExplainer
        explainer = PlainLanguageExplainer()

        events = [
            "skillopt.epoch_started",
            "skillopt.validation_passed",
            "skillopt.validation_failed",
            "skillopt.best_skill_exported",
        ]
        for event in events:
            assert explainer.explain(event) != explainer.DEFAULT_EXPLANATION
