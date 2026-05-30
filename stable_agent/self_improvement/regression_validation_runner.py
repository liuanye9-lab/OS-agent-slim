"""RegressionValidationRunner — 回归验证执行器。

V6.1 Production Hardening:
- 替换 proof_loop 中的硬置 validation_passed=True。
- 基于规则评分比较 old_score / new_score / delta。

V6.2 LLM Upgrade:
- 支持可选 LLM eval 路径（llm_client 参数）。
- LLM 评分权重 0.7 + 规则评分 0.3 混合模式。
- LLM 不可用时自动 fallback 到纯规则评分。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, Any

from stable_agent.self_improvement.validation_report import (
    ValidationReport,
    ValidationCaseResult,
)
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchCandidate

logger = logging.getLogger(__name__)


class LLMClientProtocol(Protocol):
    """LLM 客户端最小协议 — 兼容任何实现了 generate(prompt) → str 的客户端。"""
    def generate(self, prompt: str, max_tokens: int = 512) -> str: ...


@dataclass
class RegressionValidationRunner:
    """规则+LLM 混合的回归验证执行器。

    V6.2: 支持 LLM eval 路径。
    - LLM 可用: score = llm_score * 0.7 + rule_score * 0.3
    - LLM 不可用: score = rule_score * 1.0（fallback）
    """

    min_delta: float = 0.01  # 最低提升阈值
    llm_weight: float = 0.7  # LLM 评分权重（混合模式）
    rule_weight: float = 0.3  # 规则评分权重（混合模式）

    def validate_patch(
        self,
        patch: SkillPatchCandidate,
        regression_cases: list[dict],
        old_skill: str = "",
        candidate_skill: str = "",
        llm_client: LLMClientProtocol | None = None,
    ) -> ValidationReport:
        """对 skill patch 执行回归验证。

        V6.2: 新增 llm_client 参数支持 LLM eval。

        Args:
            patch: 待验证的 SkillPatchCandidate。
            regression_cases: 回归用例列表。
            old_skill: 当前 skill 规则文本（可选）。
            candidate_skill: 候选 skill 规则文本（可选）。
            llm_client: LLM 客户端（可选）。提供则启用混合评分模式。

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

        use_llm = llm_client is not None
        if use_llm:
            logger.info("ValidationRunner: LLM eval 模式 (llm_weight=%.1f)", self.llm_weight)

        # 对每个用例执行评分
        case_results: list[ValidationCaseResult] = []
        total_old = 0.0
        total_new = 0.0
        n = len(regression_cases)

        for case in regression_cases:
            case_id = case.get("case_id", f"case_{len(case_results)}")

            # 规则评分
            old_rule_score = self._score_rule(old_skill or patch.old_rule, case)
            new_rule_score = self._score_rule(candidate_skill or patch.new_rule, case)

            if use_llm:
                # LLM 评分
                old_llm_score = self._score_with_llm(
                    llm_client, old_skill or patch.old_rule, case, case_id,
                )
                new_llm_score = self._score_with_llm(
                    llm_client, candidate_skill or patch.new_rule, case, case_id,
                )
                # 混合评分
                old_score = old_llm_score * self.llm_weight + old_rule_score * self.rule_weight
                new_score = new_llm_score * self.llm_weight + new_rule_score * self.rule_weight
                logger.debug(
                    "%s: old(llm=%.2f, rule=%.2f) → %.2f, new(llm=%.2f, rule=%.2f) → %.2f",
                    case_id, old_llm_score, old_rule_score, old_score,
                    new_llm_score, new_rule_score, new_score,
                )
            else:
                old_score = old_rule_score
                new_score = new_rule_score

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

        reason = (
            f"验证 {n} 个回归用例{' (LLM混合模式)' if use_llm else ' (规则模式)'}，"
            f"{sum(1 for c in case_results if c.passed)}/{n} 通过"
        )

        return ValidationReport.from_results(
            run_id=patch.source_run_id or "unknown",
            patch_id=patch.patch_id,
            old_score=avg_old,
            new_score=avg_new,
            case_results=case_results,
            reason_zh=reason,
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

    # ------------------------------------------------------------------
    # V6.2: LLM-based Scoring
    # ------------------------------------------------------------------

    def _score_with_llm(
        self,
        llm_client: LLMClientProtocol,
        rule_text: str,
        case: dict,
        case_id: str,
    ) -> float:
        """使用 LLM 对规则在特定用例上的效果评分。

        向 LLM 提供 rule_text + case，要求返回 0.0-1.0 的评分。
        LLM 失败时 fallback 到 rule-based 评分。

        Args:
            llm_client: LLM 客户端（需实现 generate 方法）。
            rule_text: 规则文本。
            case: 测试用例。
            case_id: 用例 ID。

        Returns:
            0.0-1.0 的规则质量分数。
        """
        if not rule_text or not rule_text.strip():
            return 0.0

        case_input = case.get("input", case.get("description", ""))[:200]
        case_expected = case.get("expected", "")[:100]

        prompt = (
            f"请对以下规则在给定测试用例上的质量进行评分（0.0-1.0）。\n\n"
            f"评分维度：\n"
            f"1. 具体性（是否明确具体，非模糊笼统）\n"
            f"2. 可操作性（是否有明确的行动指引）\n"
            f"3. 约束清晰度（条件/边界是否明确）\n"
            f"4. 安全性（是否考虑风险/审批/验证）\n\n"
            f"规则文本：\n{rule_text[:500]}\n\n"
            f"测试用例：\n{case_input}"
        )
        if case_expected:
            prompt += f"\n\n预期行为：\n{case_expected}"

        prompt += "\n\n请只返回一个 0.0 到 1.0 之间的数字，不要解释。"

        try:
            response = llm_client.generate(prompt, max_tokens=64).strip()
            # 提取数字
            import re
            match = re.search(r'(0?\.?\d+)', response)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))
            logger.warning("LLM 评分解析失败: %s, fallback to rule", response[:50])
        except Exception as e:
            logger.warning("LLM 评分失败: %s, fallback to rule", e)

        # Fallback: 规则评分
        return self._score_rule(rule_text, case)
