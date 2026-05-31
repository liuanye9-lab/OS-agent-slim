"""test_cli_serve_command — V11.4 CLI serve 命令测试。"""
from __future__ import annotations
import subprocess, sys
import pytest

class TestServeParser:
    def test_serve_command_exists(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "serve", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "host" in result.stdout
        assert "port" in result.stdout

    def test_serve_default_host(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "serve", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert "127.0.0.1" in result.stdout

    def test_serve_default_port(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "serve", "--help"],
            capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert "8000" in result.stdout

class TestServePortOccupied:
    def test_port_occupied_returns_error(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        try:
            result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "serve", "--port", str(port)],
                capture_output=True, text=True, cwd="/Users/Zhuanz/OS-Agent/OS-Agent",
                env={**__import__("os").environ, "PYTHONPATH": "."}, timeout=5)
            assert result.returncode != 0
            assert "占用" in result.stdout or "occupied" in result.stdout.lower()
        finally:
            sock.close()
