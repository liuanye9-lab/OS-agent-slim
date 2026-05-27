"""回归测试套件。

确保新 skill 不破坏旧能力。对关键任务类型进行逐类评分比较，
检测超过容忍阈值的退化。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RegressionSuite:
    """回归测试套件。

    确保新 skill 不破坏旧能力。关键任务类型：
    implementation, diagnosis, learning, design。
    如果这些类型出现评分下降超过容忍度，标记为回归。

    Attributes:
        critical_types: 关键任务类型列表。
        max_regression_tolerance: 允许的最大评分退化（负数，默认 -0.05 即 5%）。
    """

    def __init__(self) -> None:
        """初始化回归测试套件。

        设置关键任务类型和退化容忍阈值。
        """
        self.critical_types: list[str] = [
            "implementation",
            "diagnosis",
            "learning",
            "design",
        ]
        self.max_regression_tolerance: float = -0.05  # 允许最多 5% 的退化

    # ------------------------------------------------------------------
    # 回归检测
    # ------------------------------------------------------------------

    def check_regression(
        self,
        baseline_scores: dict[str, float],
        candidate_scores: dict[str, float],
    ) -> list[str]:
        """逐类型比较，退化超过容忍阈值的加入回归列表。

        对所有在 baseline_scores 中出现的类型进行逐一比较：
        - 计算 score_delta = candidate_score - baseline_score
        - 如果 score_delta < max_regression_tolerance（即 < -0.05），
          标记为回归。

        Args:
            baseline_scores: 基线 skill 的各类型评分，key 为类型名。
            candidate_scores: 候选 skill 的各类型评分，key 为类型名。

        Returns:
            回归的类型名列表。空列表表示无回归。
        """
        regression_cases: list[str] = []

        for task_type in baseline_scores:
            baseline = baseline_scores[task_type]
            candidate = candidate_scores.get(task_type, 0.0)
            delta = candidate - baseline

            if delta < self.max_regression_tolerance:
                regression_cases.append(task_type)
                logger.warning(
                    "回归检测：类型 '%s' 退化 %.3f（基线=%.3f, 候选=%.3f）",
                    task_type,
                    delta,
                    baseline,
                    candidate,
                )

        return regression_cases

    # ------------------------------------------------------------------
    # 关键回归
    # ------------------------------------------------------------------

    def has_critical_regression(self, regression_cases: list[str]) -> bool:
        """检查回归类型中是否包含关键任务类型。

        关键任务类型包括：implementation, diagnosis, learning, design。
        如果回归列表中包含任何这些类型，返回 True。

        Args:
            regression_cases: check_regression 返回的回归类型列表。

        Returns:
            True 如果包含关键任务类型回归。
        """
        for case in regression_cases:
            if case in self.critical_types:
                return True
        return False
