"""Tests for dependency injection patterns — V5.5."""
import pytest


def test_unified_registry_accepts_orchestrator():
    """UnifiedToolRegistry 接受 orchestrator 依赖注入。"""
    from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
    registry = UnifiedToolRegistry(orchestrator=None)
    assert registry.get_handler("stableagent.context.build") is not None


def test_tool_router_accepts_event_stream():
    """ToolRouter 接受 EventStream 依赖注入。"""
    from stable_agent.gateway.tool_router import ToolRouter
    from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
    from stable_agent.observation.event_stream import EventStream
    registry = UnifiedToolRegistry()
    stream = EventStream()
    router = ToolRouter(registry=registry, event_stream=stream)
    assert router._event_stream is not None


def test_event_stream_di_works():
    """EventStream 可独立创建并注入。"""
    from stable_agent.observation.event_stream import EventStream
    stream = EventStream()
    assert hasattr(stream, 'publish')
    assert hasattr(stream, 'publish_sync')


def test_models_import_user_feedback():
    """UserFeedbackSignal 可导入且字段正确。"""
    from stable_agent.models import UserFeedbackSignal
    fb = UserFeedbackSignal(run_id="r1", signal_type="aligned", label_zh="符合", label_en="Aligned")
    assert fb.feedback_id != ""
    assert fb.signal_type == "aligned"
    assert fb.processed == False
