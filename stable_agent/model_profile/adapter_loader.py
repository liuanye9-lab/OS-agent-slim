"""stable_agent.model_profile.adapter_loader — 适配器配置加载器。

聚合 prompt_adapter_rules + context_budget_hint + tool_calling_hint，
返回可直接注入到 system prompt 的 adapter 配置。
"""

from __future__ import annotations

from typing import Any

from stable_agent.model_profile.model_profile import ModelProfileManager
from stable_agent.model_profile.schemas import ModelProfile


class AdapterLoader:
    """适配器配置加载器。

    从 ModelProfileManager 加载模型画像，提取 adapter 相关字段，
    返回一个可直接注入 system prompt 的配置字典。

    Args:
        profile_manager: ModelProfileManager 实例。
    """

    def __init__(self, profile_manager: ModelProfileManager | None = None) -> None:
        self._pm: ModelProfileManager = profile_manager or ModelProfileManager()

    def load_adapter(self, model_id: str) -> dict[str, Any]:
        """加载指定模型的 adapter 配置。

        返回的字典包含三个顶层键：
        - prompt_adapter_rules: prompt 适配规则列表
        - context_budget_hint: 上下文预算提示字典
        - tool_calling_hint: 工具调用提示字典

        Args:
            model_id: 模型标识，如 "claude" / "gpt" / "qwen" / "generic"。

        Returns:
            adapter 配置字典，JSON 可序列化。
        """
        profile: ModelProfile = self._pm.load_model_profile(model_id)

        return {
            "model_id": profile.model_id,
            "display_name": profile.display_name,
            "prompt_adapter_rules": list(profile.prompt_adapter_rules),
            "context_budget_hint": profile.context_budget_hint.to_dict(),
            "tool_calling_hint": profile.tool_calling_hint.to_dict(),
        }
