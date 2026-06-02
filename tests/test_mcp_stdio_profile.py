"""tests/test_mcp_stdio_profile.py — MCP stdio profile 测试。

验证 mcp_stdio.py 的 profile 过滤功能。
"""

from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("STABLE_AGENT_TOOL_PROFILE", raising=False)


class TestMcpStdioProfile:
    """MCP stdio profile 测试。"""

    def test_get_tools_minimal(self, monkeypatch):
        """minimal profile 返回核心工具。"""
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "minimal")
        from stable_agent.mcp_stdio import _get_tools_for_profile
        tools = _get_tools_for_profile()
        assert len(tools) <= 12
        names = {t["name"] for t in tools}
        assert "stableagent.task.os_agent" in names

    def test_get_tools_full(self, monkeypatch):
        """full profile 返回所有工具。"""
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "full")
        from stable_agent.mcp_stdio import _get_tools_for_profile
        tools = _get_tools_for_profile()
        assert len(tools) == 8  # 当前 CORE_TOOLS 有 8 个

    def test_os_agent_in_all_profiles(self, monkeypatch):
        """os_agent 在所有 profile 中。"""
        from stable_agent.mcp_stdio import _get_tools_for_profile
        for profile in ["minimal", "default", "full"]:
            monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", profile)
            tools = _get_tools_for_profile()
            names = {t["name"] for t in tools}
            assert "stableagent.task.os_agent" in names, f"os_agent missing in {profile}"
