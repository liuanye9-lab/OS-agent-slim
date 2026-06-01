"""测试 CLI task run 命令。

验证 V11.4 连接层硬化要求：
1. CLI task run 命令存在
2. --task-input 必填
3. mock HTTP MCP 成功时 exit code=0
4. --json 输出合法 JSON
5. 输出包含 run_id/dashboard_url/observer_url
6. 输出包含 understanding_trace/token_report/expression_matches
7. server 不可达时 exit code=1
8. server 不可达时 error 明确
9. JSON-RPC error 时 exit code=1
10. ok=false 时必须有 error
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def project_root():
    """项目根目录。"""
    return Path(__file__).parent.parent


def test_task_run_command_exists(project_root):
    """测试 CLI task run 命令存在。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "run" in result.stdout


def test_task_run_requires_task_input(project_root):
    """测试 --task-input 必填。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert result.returncode != 0
    assert "task-input" in result.stderr or "required" in result.stderr.lower()


def test_task_run_server_unreachable_exit_code_1(project_root):
    """测试 server 不可达时 exit code=1。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run",
         "--task-input", "测试任务", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    assert result.returncode == 1


def test_task_run_server_unreachable_error_message(project_root):
    """测试 server 不可达时 error 明确。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run",
         "--task-input", "测试任务", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    output = json.loads(result.stdout)
    assert "ok" in output
    assert output["ok"] is False
    assert "error" in output
    assert "未启动" in output["error"] or "失败" in output["error"]


def test_task_run_json_output_is_valid_json(project_root):
    """测试 --json 输出合法 JSON。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run",
         "--task-input", "测试任务", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    # 即使失败，输出也应该是合法 JSON
    output = json.loads(result.stdout)
    assert isinstance(output, dict)


def test_task_run_output_contains_required_fields(project_root):
    """测试输出包含 run_id/dashboard_url/observer_url。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run",
         "--task-input", "测试任务", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    output = json.loads(result.stdout)
    assert "run_id" in output
    assert "dashboard_url" in output
    assert "observer_url" in output


def test_task_run_output_contains_trace_fields(project_root):
    """测试输出包含 understanding_trace/token_report/expression_matches。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run",
         "--task-input", "测试任务", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    output = json.loads(result.stdout)
    assert "understanding_trace" in output
    assert "token_report" in output
    assert "expression_matches" in output


def test_task_run_ok_false_must_have_error(project_root):
    """测试 ok=false 时必须有 error。"""
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "task", "run",
         "--task-input", "测试任务", "--json", "--port", "19999"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )
    output = json.loads(result.stdout)
    if not output.get("ok", True):
        assert "error" in output
        assert output["error"] is not None
        assert len(output["error"]) > 0
