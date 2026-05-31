"""test_cli_health — V11.4 CLI health 命令测试。"""
from __future__ import annotations
import json, subprocess, sys
from unittest.mock import patch
import pytest
CLI_MODULE = "stable_agent.cli"

class TestHealthParser:
    def test_health_command_exists(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "health", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "json" in result.stdout

    def test_health_json_flag(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "health", "--json", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0

class TestHealthExecution:
    def test_server_not_running_returns_error(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "health", "--json", "--port", "19999"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."}, timeout=10)
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["ok"] is False
        assert data["server"] is False

    @patch(f"{CLI_MODULE}._http_get")
    def test_json_output_structure(self, mock_get):
        def side_effect(url, timeout=5.0):
            if "/api/health" in url: return {"ok": True, "service": "StableAgent OS"}
            elif "/mcp/health" in url: return {"ok": True, "service": "StableAgent MCP Gateway", "tool_count": 55}
            elif "/mcp/tools" in url: return {"result": {"tools": [{"name": "stableagent.task.os_agent"}, {"name": "stableagent.memory.retrieve"}]}}
            return {}
        mock_get.side_effect = side_effect
        from stable_agent.cli import cmd_health
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_health(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
        assert data["server"] is True
        assert data["mcp"] is True
        assert data["tool_count"] == 2
        assert data["has_os_agent"] is True
