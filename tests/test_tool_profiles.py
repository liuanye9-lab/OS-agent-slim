"""tests/test_tool_profiles.py — Tool Profile 瘦身测试。

验证三级 profile (minimal/default/full) 的工具暴露策略。
"""

from __future__ import annotations

import os
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """每个测试前清理环境变量。"""
    monkeypatch.delenv("STABLE_AGENT_TOOL_PROFILE", raising=False)


# ---------------------------------------------------------------------------
# get_tool_profile
# ---------------------------------------------------------------------------

class TestGetToolProfile:
    """get_tool_profile 环境变量解析。"""

    def test_default_is_minimal(self):
        from stable_agent.gateway.tool_profiles import get_tool_profile, ToolProfile
        assert get_tool_profile() == ToolProfile.MINIMAL

    def test_explicit_minimal(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import get_tool_profile, ToolProfile
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "minimal")
        assert get_tool_profile() == ToolProfile.MINIMAL

    def test_explicit_default(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import get_tool_profile, ToolProfile
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "default")
        assert get_tool_profile() == ToolProfile.DEFAULT

    def test_explicit_full(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import get_tool_profile, ToolProfile
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "full")
        assert get_tool_profile() == ToolProfile.FULL

    def test_unknown_falls_back_to_minimal(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import get_tool_profile, ToolProfile
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "bogus")
        assert get_tool_profile() == ToolProfile.MINIMAL

    def test_case_insensitive(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import get_tool_profile, ToolProfile
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "MINIMAL")
        assert get_tool_profile() == ToolProfile.MINIMAL


# ---------------------------------------------------------------------------
# should_expose_tool
# ---------------------------------------------------------------------------

class TestShouldExposeTool:
    """should_expose_tool 过滤逻辑。"""

    def test_minimal_includes_os_agent(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import should_expose_tool
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "minimal")
        assert should_expose_tool("stableagent.task.os_agent") is True

    def test_minimal_excludes_saas_tools(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import should_expose_tool
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "minimal")
        assert should_expose_tool("stableagent.workspace.create") is False
        assert should_expose_tool("stableagent.apikey.create") is False
        assert should_expose_tool("stableagent.usage.get") is False

    def test_default_includes_eval_tools(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import should_expose_tool
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "default")
        assert should_expose_tool("stableagent.eval.case.create") is True
        assert should_expose_tool("stableagent.eval.evaluate") is True

    def test_default_excludes_saas_tools(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import should_expose_tool
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "default")
        assert should_expose_tool("stableagent.workspace.create") is False
        assert should_expose_tool("stableagent.apikey.create") is False

    def test_full_includes_everything(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import should_expose_tool
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "full")
        assert should_expose_tool("stableagent.task.os_agent") is True
        assert should_expose_tool("stableagent.workspace.create") is True
        assert should_expose_tool("stableagent.apikey.create") is True


# ---------------------------------------------------------------------------
# MINIMAL_TOOLS 约束
# ---------------------------------------------------------------------------

class TestMinimalToolsConstraints:
    """minimal profile 工具集约束。"""

    def test_minimal_tool_count_le_12(self):
        from stable_agent.gateway.tool_profiles import MINIMAL_TOOLS
        assert len(MINIMAL_TOOLS) <= 12

    def test_minimal_must_include_os_agent(self):
        from stable_agent.gateway.tool_profiles import MINIMAL_TOOLS
        assert "stableagent.task.os_agent" in MINIMAL_TOOLS

    def test_minimal_must_include_trace(self):
        from stable_agent.gateway.tool_profiles import MINIMAL_TOOLS
        assert "stableagent.trace.get_run" in MINIMAL_TOOLS

    def test_minimal_must_include_feedback_tools(self):
        from stable_agent.gateway.tool_profiles import MINIMAL_TOOLS
        assert "stableagent.feedback.correct_and_remember" in MINIMAL_TOOLS
        assert "stableagent.feedback.remember" in MINIMAL_TOOLS
        assert "stableagent.feedback.dont_do_this_again" in MINIMAL_TOOLS

    def test_minimal_must_include_capsule(self):
        from stable_agent.gateway.tool_profiles import MINIMAL_TOOLS
        assert "stableagent.capsule.status" in MINIMAL_TOOLS


# ---------------------------------------------------------------------------
# filter_tools
# ---------------------------------------------------------------------------

class TestFilterTools:
    """filter_tools 列表过滤。"""

    def test_full_returns_all(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import filter_tools
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "full")
        tools = [{"name": f"stableagent.tool_{i}"} for i in range(55)]
        assert len(filter_tools(tools)) == 55

    def test_minimal_filters_correctly(self, monkeypatch):
        from stable_agent.gateway.tool_profiles import filter_tools, MINIMAL_TOOLS
        monkeypatch.setenv("STABLE_AGENT_TOOL_PROFILE", "minimal")
        tools = [{"name": f"stableagent.tool_{i}"} for i in range(55)]
        # 所有 minimal 工具都不在测试数据中，所以应该返回 0
        # 但如果加入 os_agent，应该返回 1
        tools.append({"name": "stableagent.task.os_agent"})
        result = filter_tools(tools)
        assert len(result) == 1
        assert result[0]["name"] == "stableagent.task.os_agent"


# ---------------------------------------------------------------------------
# get_profile_tool_count
# ---------------------------------------------------------------------------

class TestProfileToolCount:
    """get_profile_tool_count 诊断。"""

    def test_counts(self):
        from stable_agent.gateway.tool_profiles import get_profile_tool_count
        counts = get_profile_tool_count()
        assert counts["minimal"] <= 12
        assert counts["default"] > counts["minimal"]
