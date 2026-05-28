"""UserFriendlyFormatter — 用户友好格式化器，将内部结构转为自然语言。"""
from __future__ import annotations

from typing import Any

from stable_agent.explanation.bilingual_text import BilingualText


class UserFriendlyFormatter:
    """将 DecisionTrace / RunInsight 转为面向用户的自然语言。

    提供多种格式化方法，将内部的 trace、insight、evidence 等
    结构化数据转为易于阅读的单行/多行自然语言文本。

    Attributes:
        DEFAULT_LOCALE: 默认输出语言。
    """

    DEFAULT_LOCALE: str = "zh"

    def format_trace(
        self,
        trace: dict[str, Any],
        locale: str = "zh",
    ) -> str:
        """将 DecisionTrace 格式化为自然语言字符串。

        Args:
            trace: DecisionTrace 数据的字典表示，需包含 stage、what_happened_*、why_*、next_step_* 字段。
            locale: 输出语言，"zh" 或 "en"。

        Returns:
            单行格式化的自然语言描述字符串。
        """
        if locale == "zh":
            return (
                f"【{trace.get('stage', '')}】{trace.get('what_happened_zh', '')}。"
                f"原因：{trace.get('why_zh', '')}。"
                f"下一步：{trace.get('next_step_zh', '')}"
            )
        return (
            f"[{trace.get('stage', '')}] {trace.get('what_happened_en', '')}. "
            f"Why: {trace.get('why_en', '')}. "
            f"Next: {trace.get('next_step_en', '')}"
        )

    def format_insight(
        self,
        insight: dict[str, Any],
        locale: str = "zh",
    ) -> str:
        """将 RunInsight 格式化为摘要字符串。

        Args:
            insight: RunInsight 数据的字典表示，需包含 task_summary_*、quality_score、token_roi、learning_triggered。
            locale: 输出语言。

        Returns:
            多行格式化的摘要字符串。
        """
        if locale == "zh":
            learning_label: str = "是" if insight.get("learning_triggered") else "否"
            return (
                f"任务总结：{insight.get('task_summary_zh', '')}\n"
                f"质量评分：{insight.get('quality_score', 0):.2f} | "
                f"Token ROI：{insight.get('token_roi', 0):.2f} | "
                f"触发学习：{learning_label}"
            )
        learning_label = "Yes" if insight.get("learning_triggered") else "No"
        return (
            f"Summary: {insight.get('task_summary_en', '')}\n"
            f"Quality: {insight.get('quality_score', 0):.2f} | "
            f"Token ROI: {insight.get('token_roi', 0):.2f} | "
            f"Learning: {learning_label}"
        )

    def format_evidence(
        self,
        evidence: dict[str, Any],
        locale: str = "zh",
    ) -> str:
        """将单条证据格式化为自然语言字符串。

        Args:
            evidence: 证据字典，需包含 title 和 summary_zh / summary_en。
            locale: 输出语言。

        Returns:
            格式化的证据描述字符串。
        """
        if locale == "zh":
            return f"{evidence.get('title', '')}：{evidence.get('summary_zh', '')}"
        return f"{evidence.get('title', '')}: {evidence.get('summary_en', '')}"
