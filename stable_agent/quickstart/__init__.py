"""quickstart — StableAgent OS 一键接入模块。

提供 Claude Code / Codex / Cursor 的配置生成和健康检查。
"""
from __future__ import annotations

from stable_agent.quickstart.setup_detector import SetupDetector
from stable_agent.quickstart.config_generator import ConfigGenerator
from stable_agent.quickstart.launcher import Launcher

__all__ = ["SetupDetector", "ConfigGenerator", "Launcher"]
