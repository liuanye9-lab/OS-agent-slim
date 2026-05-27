"""意图信号提取器。

从 RolloutTrajectory 中提取用户意图信号。
提取维度：显性意图、隐性意图、输出偏好、拒绝信号、修正信号、任务类型。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from stable_agent.skill_optimizer.models import RolloutTrajectory

logger = logging.getLogger(__name__)


# 隐性意图关键词映射
_IMPLICIT_INTENT_KEYWORDS: dict[str, str] = {
    "提示词": "需要可直接执行的开发提示词",
    "生产": "需要可直接执行的开发提示词",
    "Codex": "需要可直接执行的开发提示词",
    "优化": "需要系统化的改进方案",
    "重构": "需要系统化的改进方案",
    "升级": "需要系统化的改进方案",
    "学习": "需要第一性原理的深度解释",
    "理解": "需要第一性原理的深度解释",
    "解释": "需要第一性原理的深度解释",
    "设计": "需要可落地的设计方案",
    "UI": "需要可落地的设计方案",
    "样式": "需要可落地的设计方案",
}

# 任务分类关键词
_TASK_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "implementation": ["开发", "实现", "写代码", "提示词", "Codex", "生产", "构建", "创建"],
    "diagnosis": ["诊断", "修复", "bug", "报错", "崩溃", "异常", "错误", "调试"],
    "learning": ["解释", "学习", "原理", "理解", "概念", "教程", "入门"],
    "design": ["设计", "UI", "架构", "方案", "规划", "布局", "样式"],
    "evaluation": ["评估", "审查", "测试", "打分", "检查", "审计"],
}

# 泛表达关键词
_GENERIC_PHRASES: list[str] = [
    "在一般情况下",
    "建议",
    "可以尝试",
    "可以考虑",
    "通常来说",
    "一般来讲",
    "大多数情况",
    "一般而言",
    "您可以根据",
]


class IntentSignalExtractor:
    """从轨迹中提取用户意图信号。

    提取维度：
    - 显性意图：用户字面上要求什么
    - 隐性意图：用户真正想达成什么结果
    - 输出偏好：喜欢什么结构/语气/深度
    - 拒绝信号：哪些内容让用户觉得没用
    - 修正信号：用户后续修改了什么
    - 任务类型：学习/项目开发/诊断/代码执行
    """

    def extract(self, trajectory: RolloutTrajectory) -> dict[str, Any]:
        """提取意图信号。

        Args:
            trajectory: RolloutTrajectory 实例。

        Returns:
            意图信号字典，包含：
            - explicit_intent: str
            - implicit_intent: str
            - output_preference: dict
            - rejection_signals: list[str]
            - correction_signals: list[str]
            - task_category: str
        """
        task_input = trajectory.task_input or ""
        task_type = trajectory.task_type or ""
        user_feedback = trajectory.user_feedback or ""
        model_output = trajectory.model_output or ""

        explicit = self._extract_explicit(task_input)
        implicit = self._infer_implicit(task_input, task_type)
        preference = self._infer_preference(user_feedback, model_output)
        rejection_signals: list[str] = []
        correction_signals: list[str] = []

        # 只有 feedback 为 "rejected" 或 "edited" 时才提取这些信号
        if user_feedback == "rejected":
            rejection_signals = self._extract_rejection(
                getattr(trajectory, "model_output", "") or ""
            )
        elif user_feedback == "edited":
            correction_signals = self._extract_correction(
                getattr(trajectory, "model_output", "") or ""
            )

        task_category = self._classify_task_category(task_input)

        return {
            "explicit_intent": explicit,
            "implicit_intent": implicit,
            "output_preference": preference,
            "rejection_signals": rejection_signals,
            "correction_signals": correction_signals,
            "task_category": task_category,
        }

    # ------------------------------------------------------------------
    # 提取方法
    # ------------------------------------------------------------------

    def _extract_explicit(self, task_input: str) -> str:
        """显性意图：直接取 task_input 原文（脱敏后）。

        脱敏：移除过长的路径、API key、密码等内容。

        Args:
            task_input: 任务输入文本。

        Returns:
            脱敏后的任务输入文本。
        """
        if not task_input:
            return ""

        # 简单脱敏：截断超长文本
        sanitized = task_input.strip()
        if len(sanitized) > 2000:
            sanitized = sanitized[:1997] + "..."

        return sanitized

    def _infer_implicit(self, task_input: str, task_type: str) -> str:
        """隐性意图推断：基于关键词推断用户的深层需求。

        映射规则：
        - "提示词/生产/Codex" → 需要可直接执行的开发提示词
        - "优化/重构/升级" → 需要系统化的改进方案
        - "学习/理解/解释" → 需要第一性原理的深度解释
        - "设计/UI/样式" → 需要可落地的设计方案
        - 默认 → 需要高质量的 AI 辅助

        Args:
            task_input: 任务输入文本。
            task_type: 任务类型。

        Returns:
            推断的隐性意图字符串。
        """
        if not task_input:
            return "需要高质量的 AI 辅助"

        # 按优先级匹配关键词（长关键词优先）
        sorted_keywords = sorted(
            _IMPLICIT_INTENT_KEYWORDS.keys(), key=len, reverse=True
        )
        for keyword in sorted_keywords:
            if keyword.lower() in task_input.lower():
                return _IMPLICIT_INTENT_KEYWORDS[keyword]

        # 基于 task_type 的兜底推断
        task_type_lower = task_type.lower() if task_type else ""
        if "code" in task_type_lower or "bug" in task_type_lower:
            return "需要可直接执行的开发提示词"
        if "refactor" in task_type_lower or "arch" in task_type_lower:
            return "需要系统化的改进方案"
        if "design" in task_type_lower or "ui" in task_type_lower:
            return "需要可落地的设计方案"

        return "需要高质量的 AI 辅助"

    def _infer_preference(
        self, user_feedback: str, model_output: str
    ) -> dict[str, Any]:
        """从 feedback 和 output 推断用户偏好。

        结构偏好：output 中有标题/列表/代码块 → 偏好结构化
        深度偏好：output 中 > 500 字符 → 偏好详细
        语气偏好：feedback 中含"太简单/不够/再详细" → 偏好深入

        Args:
            user_feedback: 用户反馈文本。
            model_output: 模型输出文本。

        Returns:
            偏好字典，包含 style, depth, structure 字段。
        """
        preference: dict[str, Any] = {
            "style": "neutral",
            "depth": "moderate",
            "structure": "moderate",
        }

        # 结构偏好判断
        if model_output:
            has_headings = bool(re.search(r"^#{1,3}\s", model_output, re.MULTILINE))
            has_lists = bool(re.search(r"^\s*[-*+]\s|\d+\.\s", model_output, re.MULTILINE))
            has_code = "```" in model_output

            if has_headings and has_lists:
                preference["structure"] = "structured"
            elif has_code:
                preference["structure"] = "code_heavy"
            elif not has_headings and not has_lists:
                preference["structure"] = "free_form"

        # 深度偏好判断
        if model_output:
            output_len = len(model_output)
            if output_len > 1000:
                preference["depth"] = "detailed"
            elif output_len < 200:
                preference["depth"] = "concise"

        # 语气偏好判断（从 feedback 推断）
        if user_feedback:
            fb_lower = user_feedback.lower()
            depth_signals = [
                "太简单", "不够", "再详细", "more detail", "深入",
                "展开", "详细", "elaborate",
            ]
            concise_signals = [
                "太长", "简洁", "概括", "总结", "too long",
                "concise", "summarize",
            ]

            if any(s in fb_lower for s in depth_signals):
                preference["depth"] = "detailed"
                preference["style"] = "in_depth"
            elif any(s in fb_lower for s in concise_signals):
                preference["depth"] = "concise"
                preference["style"] = "concise"

        return preference

    def _extract_rejection(self, user_feedback: str) -> list[str]:
        """从 rejected feedback 中提取关键问题。

        Args:
            user_feedback: 用户反馈文本（用于分析 rejection 信号）。

        Returns:
            拒绝信号关键词列表。
        """
        signals: list[str] = []
        if not user_feedback:
            return signals

        fb_lower = user_feedback.lower()

        rejection_patterns = [
            ("不准确", "输出不准确"),
            ("不对", "输出不正确"),
            ("错误", "包含错误"),
            ("太泛", "回答太泛泛"),
            ("太简单", "回答过于简单"),
            ("没用", "输出无用"),
            ("不行", "输出不可用"),
            ("跑偏", "偏离用户意图"),
            ("无关", "输出与问题无关"),
            ("幻觉", "存在幻觉内容"),
        ]

        for pattern, description in rejection_patterns:
            if pattern in fb_lower:
                signals.append(description)

        return signals

    def _extract_correction(self, user_feedback: str) -> list[str]:
        """从 edited feedback 中提取用户修改方向。

        Args:
            user_feedback: 用户反馈文本（用于分析修正方向）。

        Returns:
            修正信号列表。
        """
        signals: list[str] = []
        if not user_feedback:
            return signals

        fb_lower = user_feedback.lower()

        correction_patterns = [
            ("改成", "需要结构调整"),
            ("加上", "需要补充内容"),
            ("删除", "需要删除冗余"),
            ("替换", "需要替换部分内容"),
            ("补充", "需要补充说明"),
            ("简化", "需要简化表达"),
            ("展开", "需要展开详细说明"),
            ("重新", "需要重写"),
        ]

        for pattern, description in correction_patterns:
            if pattern in fb_lower:
                signals.append(description)

        return signals

    # ------------------------------------------------------------------
    # 任务分类
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_task_category(task_input: str) -> str:
        """基于关键词对任务进行分类。

        Args:
            task_input: 任务输入文本。

        Returns:
            任务类别：implementation/diagnosis/learning/design/evaluation/qa。
        """
        if not task_input:
            return "qa"

        input_lower = task_input.lower()

        for category, keywords in _TASK_CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in input_lower:
                    return category

        return "qa"
