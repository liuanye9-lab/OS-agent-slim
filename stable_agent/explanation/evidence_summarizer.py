"""EvidenceSummarizer — 证据摘要器，对决策证据进行排序和摘要。"""
from __future__ import annotations

from typing import Any

from stable_agent.explanation.bilingual_text import BilingualText


class EvidenceSummarizer:
    """对 DecisionEvidence 列表进行排序和双语摘要。

    在多个决策源同时返回证据时，负责按置信度排序并生成
    简洁的双语摘要文本，避免信息过载。

    Attributes:
        DEFAULT_MAX_ITEMS: 默认摘要条数上限。
    """

    DEFAULT_MAX_ITEMS: int = 5

    def summarize(
        self,
        evidence_list: list[dict[str, Any]],
        max_items: int = 5,
    ) -> BilingualText:
        """对证据列表生成双语摘要。

        Args:
            evidence_list: 证据字典列表，每个字典应包含 summary_zh / summary_en。
            max_items: 最大摘要条数。

        Returns:
            以 "；" 和 "; " 连接的中英双语摘要文本。
            空列表返回 "无可用证据" / "No evidence available"。
        """
        if not evidence_list:
            return BilingualText(zh="无可用证据", en="No evidence available")

        top: list[dict[str, Any]] = evidence_list[:max_items]
        zh_parts: list[str] = [
            e.get("summary_zh", "") for e in top if e.get("summary_zh")
        ]
        en_parts: list[str] = [
            e.get("summary_en", "") for e in top if e.get("summary_en")
        ]
        return BilingualText(
            zh="；".join(zh_parts),
            en="; ".join(en_parts),
        )

    def rank_by_confidence(
        self,
        evidence_list: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """按置信度降序排列证据。

        Args:
            evidence_list: 证据字典列表，每个字典应包含 confidence 字段。

        Returns:
            按 confidence 降序排列的新列表。
        """
        return sorted(
            evidence_list,
            key=lambda e: e.get("confidence", 0.0),
            reverse=True,
        )
