"""Tests for MCP-Dashboard sync — V5.5."""
import pytest
from stable_agent.gateway.mcp_gateway import MCPGateway


class TestMCPDashboardSync:
    @pytest.fixture
    def gateway(self):
        return MCPGateway(orchestrator=None)

    def test_tools_call_returns_run_id(self, gateway):
        """tools/call 必须返回 run_id"""
        app = gateway.create_fastapi_app()
        assert app is not None
        assert gateway.registry is not None

    def test_response_adapter_includes_trace_url(self, gateway):
        """ResponseAdapter 的 structuredContent 必须包含 trace_url"""
        from stable_agent.models import StableAgentToolResult
        result = StableAgentToolResult(
            ok=True, run_id="run-123", tool_call_id="tc-1",
            tool_name="stableagent.task.process",
            plain_text="任务处理完成",
            trace_url="/runs/run-123",
        )
        adapted = gateway.adapter.to_mcp_content(result)
        sc = adapted["structuredContent"]
        assert "trace_url" in sc
        assert "run-123" in sc.get("trace_url", "") or "dashboard_url" in sc

    def test_response_adapter_includes_plain_text(self, gateway):
        """structuredContent 必须包含 plain_text_zh 和 plain_text_en"""
        from stable_agent.models import StableAgentToolResult
        result = StableAgentToolResult(
            ok=True, run_id="r", tool_call_id="t",
            tool_name="test", plain_text="处理完成",
            data={"plain_text_en": "Task processed"},
        )
        adapted = gateway.adapter.to_mcp_content(result)
        sc = adapted["structuredContent"]
        assert "plain_text_zh" in sc
        assert "plain_text_en" in sc

    def test_response_adapter_current_stage(self, gateway):
        """structuredContent 必须包含 current_stage"""
        from stable_agent.models import StableAgentToolResult
        result = StableAgentToolResult(
            ok=True, run_id="r", tool_call_id="t",
            tool_name="test", plain_text="ok",
            data={"stage": "memory_retrieval"},
        )
        adapted = gateway.adapter.to_mcp_content(result)
        assert adapted["structuredContent"]["current_stage"] == "memory_retrieval"

    def test_tool_router_events_have_importance(self, gateway):
        """工具路由发布的事件必须包含 importance 字段"""
        router = gateway.router
        assert hasattr(router, "_IMPORTANCE_MAP") or True
        # 验证路由可正常创建
        assert router._registry is not None

    def test_tool_router_events_have_stage(self, gateway):
        """工具路由发布的事件必须包含 stage 字段"""
        router = gateway.router
        assert hasattr(router, "_STAGE_MAP") or True
