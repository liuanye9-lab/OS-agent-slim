"""tests.test_slim_mcp_tools — Slim MCP 工具测试。"""

import os
import pytest
from stable_agent.gateway.tool_schemas import TOOLS


class TestSlimMCPTools:
    """Slim MCP 工具测试。"""

    def test_os_agent_tool_exists(self):
        """stableagent.task.os_agent 工具存在。"""
        assert "stableagent.task.os_agent" in TOOLS

    def test_feedback_tools_exist(self):
        """反馈工具存在。"""
        assert "stableagent.feedback.remember" in TOOLS
        assert "stableagent.feedback.dont_do_this_again" in TOOLS
        assert "stableagent.feedback.correct_and_remember" in TOOLS

    def test_cloud_tools_exist(self):
        """Cloud 工具存在。"""
        assert "stableagent.cloud.worker.list" in TOOLS
        assert "stableagent.cloud.worker.status" in TOOLS
        assert "stableagent.cloud.task.create" in TOOLS
        assert "stableagent.cloud.task.list" in TOOLS
        assert "stableagent.cloud.task.get" in TOOLS
        assert "stableagent.cloud.task.cancel" in TOOLS

    def test_capsule_tools_exist(self):
        """Capsule 工具存在。"""
        assert "stableagent.capsule.status" in TOOLS
        assert "stableagent.memory.health" in TOOLS
        assert "stableagent.token.summary" in TOOLS

    def test_all_tools_have_input_schema(self):
        """所有工具都有 inputSchema。"""
        for name, tool in TOOLS.items():
            schema = tool.get("inputSchema") or tool.get("input_schema")
            assert schema is not None, f"{name} missing inputSchema"
            assert "type" in schema, f"{name} schema missing 'type'"

    def test_cloud_tool_schemas_valid(self):
        """Cloud 工具 Schema 结构正确。"""
        cloud_tools = [
            "stableagent.cloud.worker.list",
            "stableagent.cloud.worker.status",
            "stableagent.cloud.task.create",
            "stableagent.cloud.task.list",
            "stableagent.cloud.task.get",
            "stableagent.cloud.task.cancel",
        ]
        for name in cloud_tools:
            tool = TOOLS[name]
            schema = tool.get("inputSchema")
            assert schema is not None, f"{name} missing inputSchema"
            assert schema.get("type") == "object", f"{name} schema type should be object"
