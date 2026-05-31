"""stable_agent.model_profile.model_router — 模型路由推荐器。

基于任务类型和模型画像的 strengths/risks 做推荐，
并为指定模型+任务组合构建 adapter prompt。
"""

from __future__ import annotations

from stable_agent.model_profile.model_profile import ModelProfileManager
from stable_agent.model_profile.schemas import ModelProfile


class ModelRouter:
    """模型路由器。

    根据任务类型和可用模型列表，推荐最佳模型，
    并为指定模型+任务组合构建 adapter prompt。

    Args:
        profile_manager: ModelProfileManager 实例，用于获取模型画像。
    """

    def __init__(self, profile_manager: ModelProfileManager | None = None) -> None:
        self._pm: ModelProfileManager = profile_manager or ModelProfileManager()

    def suggest_model_for_task(
        self,
        task_type: str,
        available_models: list[str],
    ) -> str:
        """推荐最适合指定任务类型的模型。

        评分逻辑：
        1. 如果 task_type 在 profile.best_for 中 → +3 分
        2. 如果 task_type 在 profile.avoid_for 中 → -5 分
        3. 每个 strength → +1 分
        4. 每个 risk → -1 分

        Args:
            task_type: 任务类型字符串，如 "code_generation" / "bug_fix"。
            available_models: 可用模型 ID 列表。

        Returns:
            推荐的模型 ID 字符串。若无可用模型返回 "generic"。
        """
        if not available_models:
            return "generic"

        best_model = available_models[0]
        best_score = float("-inf")

        for model_id in available_models:
            profile = self._pm.load_model_profile(model_id)
            score = self._score_profile(profile, task_type)
            if score > best_score:
                best_score = score
                best_model = model_id

        return best_model

    def build_model_adapter_prompt(self, model_id: str, task_type: str) -> str:
        """构建模型适配 prompt 片段。

        将模型画像中的 prompt_adapter_rules、已知 risks 组装为
        可注入 system prompt 的指令文本。

        Args:
            model_id: 模型标识。
            task_type: 任务类型。

        Returns:
            适配 prompt 文本。
        """
        profile = self._pm.load_model_profile(model_id)

        parts: list[str] = []

        # 基础信息
        parts.append(f"[Model Adapter: {profile.display_name}]")

        # 适配规则
        if profile.prompt_adapter_rules:
            parts.append("适配规则：")
            for i, rule in enumerate(profile.prompt_adapter_rules, 1):
                parts.append(f"  {i}. {rule}")

        # 已知风险提示
        if profile.risks:
            parts.append("已知风险（请规避）：")
            for risk in profile.risks:
                parts.append(f"  - {risk}")

        # 任务特定提示
        if task_type in profile.best_for:
            parts.append(f"该模型擅长 {task_type} 类任务，请充分发挥优势。")
        elif task_type in profile.avoid_for:
            parts.append(f"该模型在 {task_type} 类任务上表现较弱，请格外注意质量检查。")

        # 上下文预算提示
        budget = profile.context_budget_hint
        parts.append(
            f"上下文预算：最大注入 {budget.max_injected_tokens} tokens"
            + ("，优先使用短上下文。" if budget.prefer_short_context else "。")
        )

        # 工具调用提示
        tool_hint = profile.tool_calling_hint
        if tool_hint.requires_strict_json:
            parts.append("工具调用需严格遵循 JSON schema。")
        if tool_hint.avoid_parallel_tool_calls:
            parts.append("请避免并行调用工具，一次只调用一个。")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _score_profile(profile: ModelProfile, task_type: str) -> float:
        """计算模型画像对指定任务类型的匹配分数。"""
        score = 0.0
        if task_type in profile.best_for:
            score += 3.0
        if task_type in profile.avoid_for:
            score -= 5.0
        score += len(profile.strengths)
        score -= len(profile.risks)
        return score
