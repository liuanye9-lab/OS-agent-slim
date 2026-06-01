"""测试 CLI dashboard 命令。

验证 V11.4 CLI dashboard 命令：
1. dashboard open 命令存在
2. 能生成正确 URL
3. --print-only 时只打印 URL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    """项目根目录。"""
    return Path(__file__).parent.parent


def test_dashboard_command_exists(project_root):
    """测试 dashboard 命令存在。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "dashboard", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "open" in result.stdout


def test_dashboard_open_generates_url(project_root):
    """测试 dashboard open 生成正确 URL。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "dashboard", "open",
         "--run-id", "test_run_123", "--print-only"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "test_run_123" in result.stdout
    assert "/observe/" in result.stdout


def test_dashboard_open_print_only(project_root):
    """测试 --print-only 只打印 URL，不打开浏览器。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "dashboard", "open",
         "--run-id", "test_run_456", "--print-only"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # --print-only 时只输出 URL，不包含其他文案
    output = result.stdout.strip()
    assert output.startswith("http://")
    assert "test_run_456" in output
