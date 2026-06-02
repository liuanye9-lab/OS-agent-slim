"""stable_agent.cloud.config — Slim Cloud Edition 配置。

通过环境变量控制所有行为，支持 slim / full profile 切换。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CloudConfig:
    """Slim Cloud Center 配置。"""

    profile: Literal["slim", "full"] = "slim"
    port: int = 18789
    bind_host: str = "127.0.0.1"
    max_events: int = 1000
    max_task_logs: int = 200
    worker_timeout: int = 60
    cloud_token: str = ""
    enable_effectiveness: bool = False
    enable_heavy_skillopt: bool = False
    enable_saas: bool = False
    enable_canvas_animation: bool = False
    db_path: str = ""
    uvicorn_workers: int = 1

    @classmethod
    def from_env(cls) -> "CloudConfig":
        """从环境变量加载配置。"""
        profile = os.getenv("STABLEAGENT_PROFILE", "slim").lower()
        is_slim = profile == "slim"

        return cls(
            profile=profile,  # type: ignore[arg-type]
            port=int(os.getenv("STABLEAGENT_PORT", "18789")),
            bind_host=os.getenv("STABLEAGENT_BIND_HOST", "127.0.0.1"),
            max_events=int(os.getenv("STABLEAGENT_MAX_EVENTS", "1000")),
            max_task_logs=int(os.getenv("STABLEAGENT_MAX_TASK_LOGS", "200")),
            worker_timeout=int(os.getenv("STABLEAGENT_WORKER_TIMEOUT", "60")),
            cloud_token=os.getenv("STABLEAGENT_CLOUD_TOKEN", ""),
            enable_effectiveness=_env_bool(
                "STABLEAGENT_ENABLE_EFFECTIVENESS", not is_slim
            ),
            enable_heavy_skillopt=_env_bool(
                "STABLEAGENT_ENABLE_HEAVY_SKILLOPT", False
            ),
            enable_saas=_env_bool("STABLEAGENT_ENABLE_SAAS", not is_slim),
            enable_canvas_animation=_env_bool(
                "STABLEAGENT_ENABLE_CANVAS_ANIMATION", not is_slim
            ),
            db_path=os.getenv(
                "STABLEAGENT_CLOUD_DB", _default_db_path(is_slim)
            ),
            uvicorn_workers=1 if is_slim else int(os.getenv("UVICORN_WORKERS", "1")),
        )

    @property
    def is_slim(self) -> bool:
        return self.profile == "slim"


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _default_db_path(is_slim: bool) -> str:
    if is_slim:
        return ".stableagent-capsule/cloud/cloud.sqlite"
    return "data/stable_agent.sqlite3"


# 全局单例
_config: CloudConfig | None = None


def get_cloud_config() -> CloudConfig:
    """获取全局 CloudConfig 单例。"""
    global _config
    if _config is None:
        _config = CloudConfig.from_env()
    return _config


def reset_cloud_config() -> None:
    """重置全局配置（用于测试）。"""
    global _config
    _config = None
