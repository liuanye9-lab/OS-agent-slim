"""personal_eval.result_scorer — 按 rubric 维度评分器。

V11 新增：ResultScorer 按 Rubric 定义的维度对 skill 文本进行评分。
确定性评分（第一版），基于关键词匹配和规则检测。
"""

from __future__ import annotations

import logging
import re

from stable_agent.personal_eval.schemas import PersonalEvalCase, Rubric

logger = logging.getLogger(__name__)


class ResultScorer:
    """按 rubric 维度的确定性评分器。

    对 skill 文本按 Rubric 定义的各维度进行评分，
    返回每个维度的 0.0-1.0 分数。
    """

    def score_skill(
        self,
        skill_text: str,
        case: PersonalEvalCase,
        rubric: Rubric,
    ) -> dict[str, float]:
        """对 skill 文本按 rubric 维度评分。

        Args:
            skill_text: skill 规则文本。
            case: 评估用例。
            rubric: 评分维度定义。

        Returns:
            维度名称 → 0.0-1.0 分数的映射。
        """
        if not skill_text or not skill_text.strip():
            return {dim: 0.0 for dim in rubric.dimensions}

        scores: dict[str, float] = {}
        text_lower = skill_text.lower()

        for dim in rubric.dimensions:
            if dim == "goal_alignment":
                scores[dim] = self._score_goal_alignment(skill_text, text_lower, case)
            elif dim == "minimal_change":
                scores[dim] = self._score_minimal_change(skill_text, text_lower)
            elif dim == "test_passed":
                scores[dim] = self._score_test_passed(skill_text, text_lower)
            elif dim == "style_consistency":
                scores[dim] = self._score_style_consistency(skill_text, text_lower)
            elif dim == "token_efficiency":
                scores[dim] = self._score_token_efficiency(skill_text)
            elif dim == "user_preference_match":
                scores[dim] = self._score_user_preference_match(skill_text, text_lower, case)
            else:
                # 未知维度使用通用评分
                scores[dim] = self._score_generic(skill_text, text_lower)

        return scores

    # ------------------------------------------------------------------
    # 各维度评分方法
    # ------------------------------------------------------------------

    @staticmethod
    def _score_goal_alignment(
        skill_text: str, text_lower: str, case: PersonalEvalCase,
    ) -> float:
        """目标对齐度：skill 是否覆盖 must_keep 关键词。"""
        if not case.must_keep:
            return 0.7  # 无约束时给中性分

        hits = sum(1 for kw in case.must_keep if kw.lower() in text_lower)
        return min(1.0, hits / len(case.must_keep))

    @staticmethod
    def _score_minimal_change(skill_text: str, text_lower: str) -> float:
        """最小变更度：skill 是否简洁、聚焦。"""
        score = 0.7  # 基线

        # 过短 → 缺少必要信息
        if len(skill_text.strip()) < 20:
            score = 0.3
        # 过长 → 冗余
        elif len(skill_text.strip()) > 800:
            score = 0.5

        # 包含明确边界词汇加分
        boundary_words = ["必须", "禁止", "总是", "不要", "仅限", "只在"]
        if any(w in text_lower for w in boundary_words):
            score = min(1.0, score + 0.15)

        return round(score, 4)

    @staticmethod
    def _score_test_passed(skill_text: str, text_lower: str) -> float:
        """测试通过度：skill 是否包含验证/测试相关要求。"""
        test_words = [
            "测试", "验证", "test", "verify", "assert", "check",
            "确保", "确认", "检验", "validate",
        ]
        hits = sum(1 for w in test_words if w in text_lower)
        return min(1.0, 0.3 + hits * 0.15)

    @staticmethod
    def _score_style_consistency(skill_text: str, text_lower: str) -> float:
        """风格一致性：skill 是否有结构化格式。"""
        score = 0.5

        # 检查是否有结构化格式
        has_list = bool(re.search(r"^[\d\-\*]\s", skill_text, re.MULTILINE))
        has_sections = bool(re.search(r"^#{1,3}\s", skill_text, re.MULTILINE))
        has_code_block = "```" in skill_text

        if has_list:
            score += 0.15
        if has_sections:
            score += 0.15
        if has_code_block:
            score += 0.1

        return min(1.0, round(score, 4))

    @staticmethod
    def _score_token_efficiency(skill_text: str) -> float:
        """Token 效率：skill 长度是否合理。"""
        length = len(skill_text.strip())
        if 50 <= length <= 300:
            return 0.9
        elif 30 <= length < 50 or 300 < length <= 500:
            return 0.7
        elif length > 500:
            return 0.5
        else:
            return 0.4

    @staticmethod
    def _score_user_preference_match(
        skill_text: str, text_lower: str, case: PersonalEvalCase,
    ) -> float:
        """用户偏好匹配度：skill 是否避免 must_avoid。"""
        if not case.must_avoid:
            return 0.7

        # 检查是否包含 must_avoid 中的模式
        hits = sum(1 for kw in case.must_avoid if kw.lower() in text_lower)
        if hits == 0:
            return 0.9  # 完全避免
        else:
            return max(0.0, 0.9 - hits * 0.3)

    @staticmethod
    def _score_generic(skill_text: str, text_lower: str) -> float:
        """通用评分：对未知维度的默认评分。"""
        # 基于文本长度和关键词存在性
        score = 0.5
        if len(skill_text.strip()) > 30:
            score += 0.1
        action_words = ["必须", "检查", "执行", "验证", "确保"]
        if any(w in text_lower for w in action_words):
            score += 0.15
        return min(1.0, round(score, 4))
