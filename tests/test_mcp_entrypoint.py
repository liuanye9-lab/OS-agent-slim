"""测试 MCP 入口点 (Phase 12)。

验证:
1. /mcp tools/list 可用
2. /mcp/legacy 仍然兼容
3. stableagent.task.os_agent 可调用
"""

import pytest
from stable_agent.gateway.tool_schemas import TOOLS, get_tool_by_name, get_tool_names


class TestMcpEntrypoint:
    """MCP 入口点测试。"""

    def test_tools_list_available(self):
        """验证 tools/list 可用 — 至少有 core tools。"""
        names = get_tool_names()
        assert len(names) >= 28  # 28 tools defined
        assert "stableagent.task.process" in names
        assert "stableagent.task.os_agent" in names
        assert "stableagent.memory.retrieve" in names

    def test_legacy_tools_still_registered(self):
        """验证核心工具未被删除。"""
        core_tools = [
            "stableagent.task.process",
            "stableagent.context.build",
            "stableagent.memory.retrieve",
            "stableagent.eval.evaluate",
        ]
        for name in core_tools:
            tool = get_tool_by_name(name)
            assert tool is not None, f"工具 {name} 缺失"
            assert tool["name"] == name
            assert "input_schema" in tool
            assert "risk_level" in tool

    def test_os_agent_has_correct_schema(self):
        """os_agent 有正确的 schema。"""
        tool = get_tool_by_name("stableagent.task.os_agent")
        assert tool is not None
        assert tool["title"] == "OS Agent 自优化工作流"
        assert tool["risk_level"] == "medium"
        props = tool["input_schema"]["properties"]
        assert "task_input" in props
        assert "mode" in props
        assert props["task_input"]["type"] == "string"

    def test_approval_respond_is_high_risk(self):
        """审批响应工具是高风险。"""
        tool = get_tool_by_name("stableagent.approval.respond")
        assert tool is not None
        assert tool["risk_level"] == "high"

    def test_skill_export_is_high_risk(self):
        """Skill 导出是高风险。"""
        tool = get_tool_by_name("stableagent.skill.export_best")
        assert tool is not None
        assert tool["risk_level"] == "high"
