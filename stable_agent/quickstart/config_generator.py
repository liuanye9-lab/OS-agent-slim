"""config_generator — 为不同客户端生成 MCP 配置。"""
from __future__ import annotations
import json
from typing import Any


class ConfigGenerator:
    """生成 Claude Code / Codex / 通用 MCP 接入配置。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self._host = host
        self._port = port
        self._mcp_url = f"http://{host}:{port}/mcp/v5/mcp"

    def claude_config(self) -> dict[str, Any]:
        """为 Claude Code 生成配置。"""
        return {
            "name": "stableagent-os",
            "description": "StableAgent OS — 自优化智能代理操作系统",
            "skill_command": "/os-agent",
            "skill_dir": ".claude/skills/os-agent/",
            "mcp_endpoint": self._mcp_url,
            "dashboard": f"http://{self._host}:{self._port}/dashboard/v2",
            "connect_page": f"http://{self._host}:{self._port}/connect",
            "health_check": f"http://{self._host}:{self._port}/api/connect/health",
            "instructions": [
                "1. 确保服务已启动: uvicorn web.server:app --host 127.0.0.1 --port 8000",
                "2. Claude Code 自动识别 .claude/skills/ 目录",
                "3. 在对话中输入 /os-agent 你的任务描述",
            ],
        }

    def codex_config(self) -> dict[str, Any]:
        """为 Codex 生成配置。"""
        return {
            "name": "stableagent-os",
            "transport": "streamable_http",
            "mcp_endpoint": self._mcp_url,
            "dashboard": f"http://{self._host}:{self._port}/dashboard/v2",
            "connect_page": f"http://{self._host}:{self._port}/connect",
            "config_file": ".codex/os-agent/mcp_config.example.json",
            "quick_prompt": ".codex/os-agent/os-agent.prompt.md",
            "launch_script": ".codex/os-agent/launch.sh",
            "mcp_json": {
                "mcpServers": {
                    "stableagent-os": {
                        "transport": "streamable_http",
                        "url": self._mcp_url,
                    }
                }
            },
        }

    def generic_config(self) -> dict[str, Any]:
        """为通用 MCP 客户端（Cursor 等）生成配置。"""
        return {
            "name": "stableagent-os",
            "description": "StableAgent OS MCP Server",
            "mcp_endpoint": self._mcp_url,
            "dashboard": f"http://{self._host}:{self._port}/dashboard/v2",
            "connect_page": f"http://{self._host}:{self._port}/connect",
            "tools_list_endpoint": self._mcp_url,
            "mcp_json": {
                "mcpServers": {
                    "stableagent-os": {
                        "transport": "streamable_http",
                        "url": self._mcp_url,
                    }
                }
            },
        }

    def to_clipboard_json(self, client_type: str) -> str:
        """生成可复制的 JSON 配置文本。"""
        if client_type == "claude":
            return json.dumps(self.claude_config(), indent=2, ensure_ascii=False)
        elif client_type == "codex":
            return json.dumps(self.codex_config()["mcp_json"], indent=2, ensure_ascii=False)
        else:
            return json.dumps(self.generic_config()["mcp_json"], indent=2, ensure_ascii=False)
