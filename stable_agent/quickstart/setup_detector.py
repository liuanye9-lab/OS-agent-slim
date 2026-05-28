"""setup_detector — 检测服务运行状态和配置。"""
from __future__ import annotations
import socket
from typing import Any


class SetupDetector:
    """检测 StableAgent OS 服务运行状态。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self._host = host
        self._port = port

    def is_server_running(self) -> bool:
        """检测服务是否在运行。"""
        try:
            sock = socket.create_connection((self._host, self._port), timeout=2)
            sock.close()
            return True
        except OSError:
            return False

    def get_endpoint(self) -> str:
        """返回 MCP 端点 URL。"""
        return f"http://{self._host}:{self._port}/mcp/v5/mcp"

    def get_dashboard_url(self) -> str:
        """返回 Dashboard URL。"""
        return f"http://{self._host}:{self._port}/dashboard/v2"

    def get_connect_url(self) -> str:
        """返回连接页面 URL。"""
        return f"http://{self._host}:{self._port}/connect"

    def health_check(self) -> dict[str, Any]:
        """执行健康检查，返回状态字典。"""
        running = self.is_server_running()
        result: dict[str, Any] = {
            "ok": running,
            "server": "running" if running else "stopped",
            "mcp_endpoint": self.get_endpoint(),
            "dashboard": f"http://{self._host}:{self._port}",
            "dashboard_v2": self.get_dashboard_url(),
            "connect_page": self.get_connect_url(),
            "recommended_command": "/os-agent",
        }
        if not running:
            result["start_command"] = f"uvicorn web.server:app --host {self._host} --port {self._port}"
        return result
