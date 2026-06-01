"""测试 CLI health 命令。

验证 V11.4 CLI health 命令：
1. health --json 返回合法 JSON
2. 能识别 has_os_agent
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    """项目根目录。"""
    return Path(__file__).parent.parent


def test_health_command_exists(project_root):
    """测试 health 命令存在。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "health", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "json" in result.stdout


def test_health_json_output_is_valid(project_root):
    """测试 health --json 返回合法 JSON。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "health", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    # 即使 server 不可达，输出也应该是合法 JSON
    output = json.loads(result.stdout)
    assert isinstance(output, dict)


def test_health_output_has_required_fields(project_root):
    """测试 health 输出包含必要字段。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "health", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    output = json.loads(result.stdout)
    assert "ok" in output
    assert "server" in output
    assert "mcp" in output
    assert "tool_count" in output
    assert "has_os_agent" in output
