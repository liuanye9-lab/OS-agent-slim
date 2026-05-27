"""意图对齐评估器。

评估模型输出是否对齐用户意图。
计算 7 维加权评分：intent_alignment、actionability、style_match、
project_consistency、anti_generic、token_efficiency、regression。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from stable_agent.intent.intent_taxonomy import IntentTaxonomy

logger = logging.getLogger(__name__)


# 通用表达关键词（用于反通用评分）
_GENERIC_PATTERNS: list[str] = [
    "在一般情况下",
    "建议您可以",
    "可以尝试",
    "可以考虑",
    "通常来说",
    "一般来讲",
    "大多数情况",
    "一般而言",
    "您可以根据",
    "常见做法是",
    "通常的做法",
]


class IntentAlignmentEvaluator:
    """评估模型输出是否对齐用户意图。

    指标（0~1）及其权重：
    - intent_alignment_score: 0.25 — 输出是否回应了用户意图
    - actionability_score: 0.20 — 输出是否包含可执行内容
    - style_match_score: 0.15 — 风格是否匹配用户偏好
    - project_consistency_score: 0.15 — 是否与项目上下文一致
    - anti_generic_score: 0.10 — 是否避免了泛泛回答
    - token_efficiency_score: 0.10 — Token 使用是否高效
    - regression_score: 0.05 — 是否引入了回退

    Attributes:
        weights: 各维度权重字典。
    """

    WEIGHTS: dict[str, float] = {
        "intent_alignment": 0.25,
        "actionability": 0.20,
        "style_match": 0.15,
        "project_consistency": 0.15,
        "anti_generic": 0.10,
        "token_efficiency": 0.10,
        "regression": 0.05,
    }

    def evaluate(
        self,
        task_input: str,
        model_output: str,
        user_intent_profile: Any = None,
        expected_intent: str = "",
    ) -> dict[str, Any]:
        """执行完整评估。

        Args:
            task_input: 用户输入文本。
            model_output: 模型输出文本。
            user_intent_profile: UserIntentProfile 实例（可选）。
            expected_intent: 期望的意图分类（可选）。

        Returns:
            评估结果字典，包含：
            - dimension_scores: 各维度评分
            - overall: 加权综合得分
            - feedback: 评估反馈文本
        """
        if not task_input and not model_output:
            return {
                "dimension_scores": {k: 0.0 for k in self.WEIGHTS},
                "overall": 0.0,
                "feedback": "输入和输出均为空。",
            }

        # 计算各维度
        intent_alignment = self._intent_alignment(task_input, model_output, expected_intent)
        actionability = self._actionability(model_output)
        anti_generic = self._anti_generic(model_output)
        style_match = self._style_match(model_output, user_intent_profile)
        project_consistency = self._project_consistency(model_output)
        token_efficiency = self._token_efficiency(task_input, model_output)
        regression = self._regression_check(model_output)

        dimension_scores = {
            "intent_alignment": intent_alignment,
            "actionability": actionability,
            "style_match": style_match,
            "project_consistency": project_consistency,
            "anti_generic": anti_generic,
            "token_efficiency": token_efficiency,
            "regression": regression,
        }

        # 加权综合
        overall = sum(
            dimension_scores[dim] * weight
            for dim, weight in self.WEIGHTS.items()
        )

        # 生成反馈
        feedback_parts: list[str] = []
        if intent_alignment < 0.5:
            feedback_parts.append("输出与用户意图对齐度较低。")
        if actionability < 0.5:
            feedback_parts.append("输出缺少可执行内容。")
        if anti_generic < 0.5:
            feedback_parts.append("输出包含较多泛泛表达。")
        if not feedback_parts:
            feedback_parts.append("输出整体质量良好。")

        return {
            "dimension_scores": dimension_scores,
            "overall": round(overall, 4),
            "feedback": " ".join(feedback_parts),
        }

    # ------------------------------------------------------------------
    # 维度评估
    # ------------------------------------------------------------------

    def _intent_alignment(
        self, task_input: str, model_output: str, expected_intent: str
    ) -> float:
        """意图对齐评分。

        基于：
        - 关键词重叠度
        - 意图分类是否匹配

        Args:
            task_input: 用户输入。
            model_output: 模型输出。
            expected_intent: 期望意图分类。

        Returns:
            0~1 评分。
        """
        if not task_input or not model_output:
            return 0.5

        # 关键词重叠
        input_words = set(re.findall(r"\w+", task_input.lower()))
        output_words = set(re.findall(r"\w+", model_output.lower()))

        if not input_words:
            return 0.5

        overlap_ratio = len(input_words & output_words) / len(input_words)

        # 基础分 = 重叠度
        score = min(overlap_ratio * 1.5, 1.0)

        # 如果提供了期望意图且输出不为泛泛，加分
        if expected_intent and not IntentTaxonomy.is_generic_answer(model_output):
            score = min(score + 0.1, 1.0)

        return score

    def _actionability(self, model_output: str) -> float:
        """可执行性评分。

        含代码块/命令/步骤列表 → 高分。

        Args:
            model_output: 模型输出。

        Returns:
            0~1 评分。
        """
        if not model_output:
            return 0.0

        score = 0.0

        # 代码块权重最大
        code_blocks = len(re.findall(r"```", model_output)) // 2
        score += min(code_blocks * 0.2, 0.5)

        # 命令/指令
        if re.search(r"\$ |npm |pip |git |docker |curl ", model_output):
            score += 0.15

        # 步骤列表
        step_patterns = re.findall(r"^\d+\.\s|\n\d+\.\s|步骤|Step", model_output)
        if len(step_patterns) >= 2:
            score += 0.2
        elif len(step_patterns) >= 1:
            score += 0.1

        # 可操作的动词
        action_verbs = ["运行", "执行", "输入", "创建", "安装", "配置", "run", "create", "install"]
        verb_count = sum(
            1 for v in action_verbs if v.lower() in model_output.lower()
        )
        score += min(verb_count * 0.05, 0.15)

        return min(score, 1.0)

    def _anti_generic(self, model_output: str) -> float:
        """反通用性评分。

        无"在一般情况下/建议/可以尝试"等通用表达 → 高分。

        Args:
            model_output: 模型输出。

        Returns:
            0~1 评分。
        """
        if not model_output:
            return 0.0

        generic_count = sum(
            1 for pattern in _GENERIC_PATTERNS if pattern in model_output
        )

        if generic_count == 0:
            return 1.0
        if generic_count <= 2:
            return 0.7
        if generic_count <= 4:
            return 0.4
        return 0.1

    def _style_match(
        self, model_output: str, profile: Any
    ) -> float:
        """风格匹配评分。

        结构化程度、深度与 profile 对比。

        Args:
            model_output: 模型输出。
            profile: UserIntentProfile 实例（可选）。

        Returns:
            0~1 评分。
        """
        if not model_output:
            return 0.5

        # 无 profile 时返回中性分
        if profile is None:
            return 0.5

        score = 0.5

        # 深度匹配
        preferred_depth = getattr(profile, "preferred_depth", 0.5)
        actual_length = len(model_output)

        # 深度映射：<200=concise(0.2), 200-500=moderate(0.5), >1000=detailed(0.8)
        if actual_length < 200:
            actual_depth = 0.2
        elif actual_length < 500:
            actual_depth = 0.5
        elif actual_length < 1000:
            actual_depth = 0.65
        else:
            actual_depth = 0.8

        depth_diff = abs(preferred_depth - actual_depth)
        score += (1.0 - depth_diff) * 0.25

        # 结构匹配
        preferred_structure = getattr(profile, "preferred_structure", 0.5)
        has_headings = bool(re.search(r"^#{1,3}\s", model_output, re.MULTILINE))
        has_lists = bool(re.search(r"^\s*[-*+]\s|\d+\.\s", model_output, re.MULTILINE))

        actual_structure = 0.8 if has_headings and has_lists else (0.5 if has_headings or has_lists else 0.2)
        struct_diff = abs(preferred_structure - actual_structure)
        score += (1.0 - struct_diff) * 0.25

        return min(score, 1.0)

    @staticmethod
    def _project_consistency(model_output: str) -> float:
        """项目一致性评分（占位：默认为中性）。

        完整实现应考虑项目上下文，此处基于输出结构判断。

        Args:
            model_output: 模型输出。

        Returns:
            0~1 评分。
        """
        if not model_output:
            return 0.5

        # 检查是否有严重矛盾标记
        contradictions = [
            "但是请注意，以上说法是错误的",
            "前面的分析有误",
        ]
        for contra in contradictions:
            if contra in model_output:
                return 0.2

        # 默认中性
        return 0.6

    @staticmethod
    def _token_efficiency(task_input: str, model_output: str) -> float:
        """Token 效率评分。

        输出/输入字符比在合理范围内 → 高分。

        Args:
            task_input: 用户输入。
            model_output: 模型输出。

        Returns:
            0~1 评分。
        """
        if not task_input or not model_output:
            return 0.5

        input_len = len(task_input)
        output_len = len(model_output)

        if input_len == 0:
            return 0.5

        ratio = output_len / input_len

        # 理想比例 1.0~5.0
        if 1.0 <= ratio <= 5.0:
            return 1.0
        if 0.5 <= ratio < 1.0 or 5.0 < ratio <= 10.0:
            return 0.7
        if ratio < 0.5:
            return 0.4
        # ratio > 10.0 — 可能过于冗长
        return 0.3

    @staticmethod
    def _regression_check(model_output: str) -> float:
        """回退检测评分。

        检测输出中是否有回退/降级信号。

        Args:
            model_output: 模型输出。

        Returns:
            0~1 评分（1=无回退）。
        """
        if not model_output:
            return 1.0

        regression_signals = [
            "我无法",
            "我不知道",
            "抱歉",
            "作为AI",
            "请重新表述",
            "我不确定",
        ]

        signal_count = sum(
            1 for s in regression_signals if s in model_output
        )

        if signal_count == 0:
            return 1.0
        if signal_count <= 2:
            return 0.7
        return 0.3
