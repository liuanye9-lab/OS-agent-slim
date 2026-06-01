"""测试 AGENTS.md 和 CLAUDE.md 中的 MCP/CLI 优先级规则。

验证 V11.4 连接层硬化要求：
1. AGENTS.md 包含 .venv/bin/python
2. CLAUDE.md 包含 .venv/bin/python
3. 两者不再推荐 python3
4. 两者包含 HTTP MCP
5. 两者包含 stdio MCP
6. 两者包含 CLI fallback
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    """项目根目录。"""
    return Path(__file__).parent.parent


@pytest.fixture
def agents_md(project_root):
    """读取 AGENTS.md 内容。"""
    return (project_root / "AGENTS.md").read_text()


@pytest.fixture
def claude_md(project_root):
    """读取 CLAUDE.md 内容。"""
    return (project_root / "CLAUDE.md").read_text()


def test_agents_md_contains_venv_python(agents_md):
    """测试 AGENTS.md 包含 .venv/bin/python。"""
    assert ".venv/bin/python" in agents_md


def test_claude_md_contains_venv_python(claude_md):
    """测试 CLAUDE.md 包含 .venv/bin/python。"""
    assert ".venv/bin/python" in claude_md


def test_agents_md_not_recommending_python3(agents_md):
    """测试 AGENTS.md 不再推荐 python3。"""
    # 检查是否明确禁止使用 python3
    assert "不要使用" in agents_md and "python3" in agents_md


def test_claude_md_not_recommending_python3(claude_md):
    """测试 CLAUDE.md 不再推荐 python3。"""
    # 检查是否明确禁止使用 python3
    assert "不要使用" in claude_md and "python3" in claude_md


def test_agents_md_contains_http_mcp(agents_md):
    """测试 AGENTS.md 包含 HTTP MCP。"""
    assert "HTTP MCP" in agents_md
    assert "stableagent.task.os_agent" in agents_md


def test_claude_md_contains_http_mcp(claude_md):
    """测试 CLAUDE.md 包含 HTTP MCP。"""
    assert "HTTP MCP" in claude_md
    assert "stableagent.task.os_agent" in claude_md


def test_agents_md_contains_stdio_mcp(agents_md):
    """测试 AGENTS.md 包含 stdio MCP。"""
    assert "stdio MCP" in agents_md
    assert "stableagent-stdio" in agents_md


def test_claude_md_contains_stdio_mcp(claude_md):
    """测试 CLAUDE.md 包含 stdio MCP。"""
    assert "stdio MCP" in claude_md
    assert "stableagent-stdio" in claude_md


def test_agents_md_contains_cli_fallback(agents_md):
    """测试 AGENTS.md 包含 CLI fallback。"""
    assert "CLI fallback" in agents_md
    assert "task run" in agents_md


def test_claude_md_contains_cli_fallback(claude_md):
    """测试 CLAUDE.md 包含 CLI fallback。"""
    assert "CLI fallback" in claude_md
    assert "task run" in claude_md
