"""测试 ResponseAdapter 状态字段透传 (Phase 12)。

验证 ResponseAdapter 返回 dashboard_url/progress_pct/status_text_zh/why_zh。
"""

import pytest
from stable_agent.gateway.response_adapter import ResponseAdapter
from stable_agent.models import StableAgentToolResult


class TestResponseAdapterFields:
    """ResponseAdapter 字段透传测试。"""

    def test_to_mcp_content_includes_dashboard_url(self):
        """验证 dashboard_url 透传。"""
        adapter = ResponseAdapter()
        result = StableAgentToolResult(
            ok=True,
            run_id="run-001",
            tool_name="test.tool",
            plain_text="成功",
            dashboard_url="/runs/run-001",
        )
        mcp = adapter.to_mcp_content(result)
        sc = mcp["structuredContent"]
        assert sc["dashboard_url"] == "/runs/run-001"

    def test_to_mcp_content_includes_status_text_zh(self):
        """验证 status_text_zh 透传。"""
        adapter = ResponseAdapter()
        result = StableAgentToolResult(
            ok=True,
            run_id="run-001",
            tool_name="test.tool",
            plain_text="Success",
            plain_text_zh="成功执行",
        )
        mcp = adapter.to_mcp_content(result)
        sc = mcp["structuredContent"]
        assert sc["status_text_zh"] == "成功执行"

    def test_to_mcp_content_includes_decision_fields(self):
        """验证决策字段透传。"""
        adapter = ResponseAdapter()
        result = StableAgentToolResult(
            ok=True,
            run_id="run-001",
            tool_name="test.tool",
            plain_text="OK",
            data={
                "decision_summary_zh": "决定使用方案A",
                "why_zh": "方案A更安全",
            },
        )
        mcp = adapter.to_mcp_content(result)
        sc = mcp["structuredContent"]
        assert sc["decision_summary_zh"] == "决定使用方案A"
        assert sc["why_zh"] == "方案A更安全"

    def test_to_mcp_content_includes_progress(self):
        """验证 progress_pct 字段。"""
        adapter = ResponseAdapter()
        result = StableAgentToolResult(
            ok=True,
            run_id="run-001",
            tool_name="test.tool",
            plain_text="OK",
            data={"progress_pct": 70},
        )
        mcp = adapter.to_mcp_content(result)
        sc = mcp["structuredContent"]
        assert sc["progress_pct"] == 70

    def test_to_mcp_content_hides_chain_of_thought(self):
        """验证不暴露 chain_of_thought 字段。"""
        adapter = ResponseAdapter()
        result = StableAgentToolResult(
            ok=True,
            run_id="run-001",
            tool_name="test.tool",
            plain_text="OK",
            data={"chain_of_thought": "secret"},
        )
        mcp = adapter.to_mcp_content(result)
        sc = mcp["structuredContent"]
        # chain_of_thought 不在 structuredContent 的顶级字段中
        assert "chain_of_thought" not in sc
