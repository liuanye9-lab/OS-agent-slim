"""stable_agent.model_profile — 模型画像与自适应路由。

提供 ModelProfile 管理、任务-模型推荐路由、以及 prompt adapter 加载能力，
使系统能根据模型特性自动调整上下文注入策略和工具调用方式。
"""

from __future__ import annotations

from stable_agent.model_profile.schemas import ModelProfile
from stable_agent.model_profile.model_profile import ModelProfileManager
from stable_agent.model_profile.model_router import ModelRouter
from stable_agent.model_profile.adapter_loader import AdapterLoader

__all__ = [
    "ModelProfile",
    "ModelProfileManager",
    "ModelRouter",
    "AdapterLoader",
]
