"""personal_eval.ab_regression_runner — A/B 回归测试执行器。

V11 新增：ABRegressionRunner 比较 old_skill 和 new_skill 在评估用例上的表现。
确定性评分（第一版），只有 new_score > old_score + min_delta 才 passed。
"""

from __future__ import annotations

import logging

from stable_agent.personal_eval.schemas import (
    ABRegressionResult,
    PersonalEvalCase,
    Rubric,
)
from stable_agent.personal_eval.result_scorer import ResultScorer

logger = logging.getLogger(__name__)


class ABRegressionRunner:
    """A/B 回归测试执行器。

    比较 old_skill 和 new_skill 在 PersonalEvalCase 上的表现，
    基于 Rubric 维度评分，只有 new_score > old_score + min_delta 才通过。

    Attributes:
        min_delta: 最低提升阈值。
        scorer: 维度评分器。
    """

    def __init__(self, min_delta: float = 0.01) -> None:
        """初始化 A/B 回归测试执行器。

        Args:
            min_delta: 最低提升阈值，默认 0.01。
        """
        self.min_delta: float = min_delta
        self.scorer: ResultScorer = ResultScorer()

    def run_ab(
        self,
        case: PersonalEvalCase,
        old_skill: str,
        new_skill: str,
        rubric: Rubric,
    ) -> ABRegressionResult:
        """执行 A/B 回归测试。

        对 old_skill 和 new_skill 分别按 rubric 维度评分，
        计算加权总分，判断 new_skill 是否显著优于 old_skill。

        Args:
            case: 评估用例。
            old_skill: 旧 skill 规则文本。
            new_skill: 新 skill 规则文本。
            rubric: 评分维度定义。

        Returns:
            ABRegressionResult 实例。
        """
        # 分维度评分
        old_scores = self.scorer.score_skill(old_skill, case, rubric)
        new_scores = self.scorer.score_skill(new_skill, case, rubric)

        # 计算加权总分
        old_total = self._weighted_total(old_scores, rubric)
        new_total = self._weighted_total(new_scores, rubric)

        delta = new_total - old_total
        passed = delta > self.min_delta

        # 生成中文说明
        reason_zh = self._generate_reason(
            case, old_total, new_total, delta, passed, old_scores, new_scores,
        )

        # 构建 dimension_scores
        dimension_scores: dict[str, dict[str, float]] = {}
        for dim in rubric.dimensions:
            dimension_scores[dim] = {
                "old": old_scores.get(dim, 0.0),
                "new": new_scores.get(dim, 0.0),
                "delta": new_scores.get(dim, 0.0) - old_scores.get(dim, 0.0),
            }

        result = ABRegressionResult(
            case_id=case.case_id,
            old_skill_score=round(old_total, 4),
            new_skill_score=round(new_total, 4),
            delta=round(delta, 4),
            passed=passed,
            reason_zh=reason_zh,
            dimension_scores=dimension_scores,
        )

        logger.info(
            "AB regression %s: old=%.3f, new=%.3f, delta=%.3f, passed=%s",
            case.case_id, old_total, new_total, delta, passed,
        )

        return result

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_total(scores: dict[str, float], rubric: Rubric) -> float:
        """计算加权总分。"""
        total = 0.0
        for dim, weight in rubric.dimensions.items():
            total += scores.get(dim, 0.0) * weight
        return total

    @staticmethod
    def _generate_reason(
        case: PersonalEvalCase,
        old_total: float,
        new_total: float,
        delta: float,
        passed: bool,
        old_scores: dict[str, float],
        new_scores: dict[str, float],
    ) -> str:
        """生成中文说明。"""
        if passed:
            # 找出提升最大的维度
            improvements = {
                dim: new_scores.get(dim, 0.0) - old_scores.get(dim, 0.0)
                for dim in old_scores
            }
            best_dim = max(improvements, key=lambda k: improvements[k])
            return (
                f"新 skill 显著优于旧 skill (delta={delta:.3f})。"
                f"最大提升维度: {best_dim} (+{improvements[best_dim]:.3f})"
            )
        else:
            if delta <= 0:
                return f"新 skill 未提升评分 (delta={delta:.3f})，验证失败。"
            else:
                return (
                    f"新 skill 提升不足 (delta={delta:.3f} <= min_delta=0.01)，"
                    f"验证失败。"
                )
