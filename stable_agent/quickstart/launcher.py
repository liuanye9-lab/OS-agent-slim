"""launcher — 一键启动连接检查。"""
from __future__ import annotations
from stable_agent.quickstart.setup_detector import SetupDetector
from stable_agent.quickstart.config_generator import ConfigGenerator
from typing import Any


class Launcher:
    """一键启动器，整合检测 + 配置生成。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self._detector = SetupDetector(host, port)
        self._config = ConfigGenerator(host, port)

    def full_status(self) -> dict[str, Any]:
        """返回完整的接入状态（供 /connect 页面使用）。"""
        health = self._detector.health_check()
        return {
            "status": health,
            "claude": self._config.claude_config(),
            "codex": self._config.codex_config(),
            "generic": self._config.generic_config(),
        }
