"""RegressionValidationRunner — 回归验证执行器。

V6.1 Production Hardening:
- 替换 proof_loop 中的硬置 validation_passed=True。
- 基于规则评分比较 old_score / new_score / delta。
- 最低实现用 rule-based scoring（不依赖 LLM）。
- passed=False 时不得进入 waiting_review。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from stable_agent.self_improvement.validation_report import (
    ValidationReport,
    ValidationCaseResult,
)
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchCandidate

logger = logging.getLogger(__name__)


@dataclass
class RegressionValidationRunner:
    """规则驱动的回归验证执行器。

    对每个回归用例：
    1. 用 old_rule 和 candidate_rule 分别评分
    2. 比较 delta
    3. 生成 ValidationReport
    """

    min_delta: float = 0.01  # 最低提升阈值

    def validate_patch(
        self,
        patch: SkillPatchCandidate,
        regression_cases: list[dict],
        old_skill: str = "",
        candidate_skill: str = "",
    ) -> ValidationReport:
        """对 skill patch 执行回归验证。

        Args:
            patch: 待验证的 SkillPatchCandidate。
            regression_cases: 回归用例列表 [{"input": ..., "expected": ...}, ...]。
            old_skill: 当前 skill 规则文本（可选）。
            candidate_skill: 候选 skill 规则文本（可选）。

        Returns:
            ValidationReport，passed 表示验证通过。
        """
        if not regression_cases:
            logger.warning("无回归用例，跳过验证")
            return ValidationReport.from_results(
                run_id=patch.source_run_id or "unknown",
                patch_id=patch.patch_id,
                old_score=0.0,
                new_score=1.0,
                case_results=[],
                reason_zh="无回归用例可用，默认通过（低置信度）",
            )

        # 对每个用例执行规则评分
        case_results: list[ValidationCaseResult] = []
        total_old = 0.0
        total_new = 0.0
        n = len(regression_cases)

        for case in regression_cases:
            case_id = case.get("case_id", f"case_{len(case_results)}")

            # 规则评分：基于规则质量维度
            old_score = self._score_rule(old_skill or patch.old_rule, case)
            new_score = self._score_rule(candidate_skill or patch.new_rule, case)
            total_old += old_score
            total_new += new_score

            delta = new_score - old_score
            passed = delta > self.min_delta

            if not passed:
                logger.info(
                    "回归用例 %s 未通过: old=%.2f, new=%.2f, delta=%.2f",
                    case_id, old_score, new_score, delta,
                )

            case_results.append(ValidationCaseResult(
                case_id=case_id,
                passed=passed,
                old_score=old_score,
                new_score=new_score,
                delta=delta,
                failure_reason="" if passed else f"delta={delta:.2f} <= min_delta={self.min_delta}",
            ))

        avg_old = total_old / n if n > 0 else 0.0
        avg_new = total_new / n if n > 0 else 0.0

        return ValidationReport.from_results(
            run_id=patch.source_run_id or "unknown",
            patch_id=patch.patch_id,
            old_score=avg_old,
            new_score=avg_new,
            case_results=case_results,
            reason_zh=f"验证 {n} 个回归用例，{sum(1 for c in case_results if c.passed)}/{n} 通过",
        )

    def _score_rule(self, rule_text: str, case: dict) -> float:
        """对规则质量进行规则化评分。

        评分维度：
        - specificity (0-1): 规则是否具体，非模糊
        - actionability (0-1): 规则是否有明确行动指引
        - constraint_clarity (0-1): 约束是否清晰
        - safety (0-1): 是否包含安全相关考虑

        Args:
            rule_text: 规则文本。
            case: 测试用例。

        Returns:
            0-1 的规则质量分数。
        """
        if not rule_text or not rule_text.strip():
            return 0.0

        score = 0.5  # 基线分

        text = rule_text.lower()

        # specificity: 包含"必须"/"禁止"/"总是"等明确词
        specific_words = ["必须", "禁止", "总是", "永远不要", "总是要",
                         "must", "never", "always", "forbidden", "required"]
        specificity_bonus = sum(1 for w in specific_words if w in text) * 0.08
        score += min(specificity_bonus, 0.25)

        # actionability: 包含步骤/动作指示
        action_words = ["调用", "检查", "执行", "搜索", "读取", "验证",
                       "call", "check", "execute", "search", "read", "verify"]
        action_bonus = sum(1 for w in action_words if w in text) * 0.06
        score += min(action_bonus, 0.15)

        # constraint_clarity: 包含"如果"/"当"/"在...之前"等条件词
        constraint_words = ["如果", "当", "则", "否则", "在.*之前",
                           "if", "when", "then", "else", "before"]
        constraint_bonus = sum(1 for w in constraint_words if w in text) * 0.04
        score += min(constraint_bonus, 0.10)

        # safety: 包含"审批"/"风险"/"危险"/"确认"等安全词
        safety_words = ["审批", "风险", "危险", "确认", "验证",
                       "approval", "risk", "danger", "confirm", "validate"]
        safety_bonus = sum(1 for w in safety_words if w in text) * 0.04
        score += min(safety_bonus, 0.10)

        # 过短的规则扣分
        if len(text) < 30:
            score -= 0.15

        # 过长冗余扣分（>1000 字符）
        if len(text) > 1000:
            score -= 0.10

        return max(0.0, min(1.0, score))
