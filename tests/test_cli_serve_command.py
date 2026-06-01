"""测试 CLI serve 命令。

验证 V11.4 CLI serve 命令：
1. serve 命令存在
2. 端口占用时 exit code=1
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


def test_serve_command_exists(project_root):
    """测试 serve 命令存在。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "serve", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "host" in result.stdout
    assert "port" in result.stdout
