"""LearningEvidence — SkillOpt 学习证据。

展示 patch 前后的 diff 对比和验证结果，
用于 Dashboard 中的技能学习面板。

用法::

    evidence = LearningEvidence()
    details = evidence.build_from_validation(validation_result)
    if not details["triggered"]:
        no_learn = evidence.no_learning_reason()
"""

from __future__ import annotations

from typing import Any


class LearningEvidence:
    """SkillOpt 学习证据。

    封装 patch 验证结果，提供中英双语的学习证据展示。
    支持两种场景：
    1. 学习已触发 → build_from_validation() 展示 diff 和验证结果
    2. 学习未触发 → no_learning_reason() 解释原因
    """

    def __init__(self) -> None:
        """初始化 LearningEvidence。"""
        pass

    def build_from_validation(self, result: dict[str, Any]) -> dict[str, Any]:
        """从验证结果构建学习证据。

        Args:
            result: 验证结果字典，应包含以下字段（可选）：
                - patches: patch 列表
                - baseline_score: 基线评分
                - candidate_score: 候选评分
                - passed: 是否通过验证
                - diff_summary: diff 摘要
                - triggered: 是否触发学习
                - reason_zh: 中文原因
                - reason_en: 英文原因

        Returns:
            {
                triggered: bool,
                reason_zh: str,
                patches: list[dict],
                baseline_score: float,
                candidate_score: float,
                passed: bool,
                diff_summary: str,
            }
        """
        patches = result.get("patches", [])
        baseline_score = float(result.get("baseline_score", 0.0))
        candidate_score = float(result.get("candidate_score", 0.0))
        passed = bool(result.get("passed", False))

        # 构建 diff 摘要
        diff_summary = result.get("diff_summary", "")
        if not diff_summary and patches:
            diff_summary = self._summarize_patches(patches)

        # 构建原因
        triggered = True
        if passed:
            reason_zh = result.get(
                "reason_zh",
                f"验证通过：候选评分 {candidate_score:.2f} ≥ 基线 {baseline_score:.2f}，"
                f"共 {len(patches)} 个 patch 通过验证。",
            )
            reason_en = result.get(
                "reason_en",
                f"Validation passed: candidate score {candidate_score:.2f} ≥ "
                f"baseline {baseline_score:.2f}, {len(patches)} patch(es) validated.",
            )
        else:
            reason_zh = result.get(
                "reason_zh",
                f"验证未通过：候选评分 {candidate_score:.2f} < 基线 {baseline_score:.2f}。",
            )
            reason_en = result.get(
                "reason_en",
                f"Validation failed: candidate score {candidate_score:.2f} < "
                f"baseline {baseline_score:.2f}.",
            )

        return {
            "triggered": triggered,
            "reason_zh": reason_zh,
            "reason_en": reason_en,
            "patches": patches,
            "baseline_score": baseline_score,
            "candidate_score": candidate_score,
            "passed": passed,
            "diff_summary": diff_summary,
        }

    def no_learning_reason(self) -> dict[str, Any]:
        """返回未触发学习的原因解释。

        Returns:
            {
                triggered: False,
                reason_zh: str,
                reason_en: str,
            }
        """
        return {
            "triggered": False,
            "reason_zh": (
                "本轮未触发技能学习。可能原因："
                "1) 任务执行质量达标无需优化；"
                "2) 学习触发条件未满足（如样本数不足）；"
                "3) 优化引擎处于冷却期。"
            ),
            "reason_en": (
                "No skill learning triggered this run. Possible reasons: "
                "1) Task quality meets the threshold; "
                "2) Learning trigger conditions not met (e.g., insufficient samples); "
                "3) Optimization engine is in cooldown."
            ),
        }

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_patches(patches: list[dict[str, Any]]) -> str:
        """生成 patch 列表的摘要文本。

        Args:
            patches: patch 字典列表。

        Returns:
            摘要字符串。
        """
        if not patches:
            return "No patches."

        summaries: list[str] = []
        for i, patch in enumerate(patches[:5]):  # 最多展示 5 个
            name = patch.get("name", patch.get("id", f"Patch #{i + 1}"))
            desc = patch.get("description", patch.get("summary", ""))
            if desc:
                summaries.append(f"{name}: {desc}")
            else:
                summaries.append(name)

        if len(patches) > 5:
            summaries.append(f"... and {len(patches) - 5} more")

        return "; ".join(summaries)
