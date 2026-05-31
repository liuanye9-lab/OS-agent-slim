"""test_cli_dashboard — V11.4 CLI dashboard 命令测试。"""
from __future__ import annotations
import subprocess, sys
import pytest

class TestDashboardParser:
    def test_dashboard_command_exists(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "dashboard", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "open" in result.stdout

    def test_dashboard_open_help(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "dashboard", "open", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "run-id" in result.stdout or "run_id" in result.stdout

class TestDashboardPrintOnly:
    def test_print_only_shows_url_with_run_id(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "dashboard", "open",
            "--run-id", "run_test123", "--print-only"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "run_test123" in result.stdout
        assert "/observe/" in result.stdout

    def test_print_only_without_run_id(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "dashboard", "open", "--print-only"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "http://127.0.0.1:8000" in result.stdout
