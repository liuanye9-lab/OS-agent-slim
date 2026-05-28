"""LearningExplainer — 学习解释器，将 SkillOpt 优化结果翻译为人话。"""
from __future__ import annotations

from typing import Any

from stable_agent.explanation.bilingual_text import BilingualText


class LearningExplainer:
    """解释 SkillOpt 优化回合的结果。

    将 SkillOpt 的内部优化数据（epoch 结果、patch 应用、验证结果）
    翻译为用户可理解的中英双语自然语言解释。

    Attributes:
        DEFAULT_NO_LEARNING_REASON_ZH: 未触发学习的默认中文原因。
        DEFAULT_NO_LEARNING_REASON_EN: 未触发学习的默认英文原因。
    """

    DEFAULT_NO_LEARNING_REASON_ZH: str = "缺少足够反馈信号"
    DEFAULT_NO_LEARNING_REASON_EN: str = "Insufficient feedback signal"

    def explain_epoch(
        self,
        epoch_result: dict[str, Any] | None,
    ) -> BilingualText:
        """解释 SkillOpt 优化回合的整体结果。

        Args:
            epoch_result: 优化回合结果字典，若为 None 则视为未触发学习。

        Returns:
            描述该回合学习情况的双语文本。
        """
        if epoch_result is None:
            return BilingualText(
                zh="本次未触发学习",
                en="No learning triggered this run",
            )

        triggered: bool = epoch_result.get("triggered", False)
        if not triggered:
            reason_zh: str = epoch_result.get("reason_zh", self.DEFAULT_NO_LEARNING_REASON_ZH)
            reason_en: str = epoch_result.get("reason_en", self.DEFAULT_NO_LEARNING_REASON_EN)
            return BilingualText(
                zh=f"本次未触发学习。原因：{reason_zh}",
                en=f"No learning triggered. Reason: {reason_en}",
            )

        patches: int = epoch_result.get("patches_applied", 0)
        score: float = epoch_result.get("score_gain", 0.0)
        return BilingualText(
            zh=f"触发了 {patches} 个 skill patch，评分提升 {score:.2f}",
            en=f"Applied {patches} skill patches, score improved by {score:.2f}",
        )

    def explain_patch(
        self,
        patch: dict[str, Any],
        validation: dict[str, Any] | None,
    ) -> BilingualText:
        """解释单个 skill patch 的结果。

        Args:
            patch: patch 数据字典，需包含 summary_zh / summary_en。
            validation: 验证结果字典；passed=True 表示通过，否则表示被拒绝。

        Returns:
            描述 patch 应用结果的双语文本。
        """
        if validation and validation.get("passed", False):
            return BilingualText(
                zh=f"规则已更新：{patch.get('summary_zh', '')}",
                en=f"Rule updated: {patch.get('summary_en', '')}",
            )
        return BilingualText(
            zh=f"规则被拒绝：{patch.get('summary_zh', '')}",
            en=f"Rule rejected: {patch.get('summary_en', '')}",
        )

    def format_diff(self, before: str, after: str) -> dict[str, str]:
        """将优化前后的字符串打包为 diff 字典。

        Args:
            before: 优化前的规则文本。
            after: 优化后的规则文本。

        Returns:
            包含 "before" 和 "after" 键的字典。
        """
        return {"before": before, "after": after}
