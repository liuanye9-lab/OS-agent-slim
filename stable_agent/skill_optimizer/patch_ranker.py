"""Patch 排序引擎。

按多维度对 SkillPatch 中的编辑列表排序并截断。
综合考量支持数、失败严重度、泛化性、风险和简洁性。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from stable_agent.skill_optimizer.models import (
    SkillEdit,
    SkillPatch,
)

logger = logging.getLogger(__name__)

# 泛化性关键词（中文）
_GENERALIZATION_KEYWORDS: list[str] = [
    "共性", "模式", "多次", "通用", "一般", "泛化", "规律",
    "通常", "大多数", "常见", "普遍", "统一",
]


class PatchRanker:
    """按多维度排序截断 SkillPatch 中的编辑列表。

    排序维度（权重）：
    1. support_count（0.30）— 多次验证有效
    2. 失败严重度（0.25）— 修复高频失败优先
    3. 泛化性（0.20）— 非单 case 硬编码
    4. 风险（0.15）— 低风险优先
    5. 简洁性（0.10）— 不让 skill 臃肿

    风险得分：low=1.0, medium=0.7, high=0.3
    泛化性分数：基于 reasoning 中是否包含"共性/模式/多次"等词 → 1.0，否则 0.5
    简洁性：content 长度 < 200 → 1.0，200-500 → 0.7，> 500 → 0.4
    """

    # 各维度权重
    WEIGHT_SUPPORT = 0.30
    WEIGHT_SEVERITY = 0.25
    WEIGHT_GENERALIZATION = 0.20
    WEIGHT_RISK = 0.15
    WEIGHT_CONCISENESS = 0.10

    def rank(self, patch: SkillPatch, edit_budget: int = 4) -> SkillPatch:
        """按综合得分排序，截取 top edit_budget 条编辑。

        返回新的 SkillPatch（edits 已排序截断，reasoning 记录排序说明）。

        Args:
            patch: 输入的 SkillPatch。
            edit_budget: 保留的最大编辑数。

        Returns:
            排序并截断后的新 SkillPatch。
        """
        if not patch.edits:
            return SkillPatch(
                id=str(uuid.uuid4()),
                edits=[],
                reasoning="排序结果为空：无编辑。",
            )

        # 计算每条编辑的得分
        scored: list[tuple[SkillEdit, float]] = []
        for edit in patch.edits:
            score = self._score_edit(edit)
            scored.append((edit, score))

        # 按得分降序排序
        scored.sort(key=lambda x: x[1], reverse=True)

        # 截取 top edit_budget
        top_edits = [edit for edit, _ in scored[:edit_budget]]

        # 构建排序说明
        ranking_details = []
        for i, (edit, score) in enumerate(scored[:edit_budget]):
            ranking_details.append(
                f"  #{i+1} {edit.id}: score={score:.3f} "
                f"(op={edit.op}, support={edit.support_count}, "
                f"risk={edit.risk_level})"
            )

        reasoning = (
            f"排序完成：{len(scored)} 条编辑 → 保留 top {len(top_edits)}。\n"
            + "\n".join(ranking_details)
            + (
                f"\n已截断 {len(scored) - edit_budget} 条低分编辑。"
                if len(scored) > edit_budget
                else ""
            )
        )

        return SkillPatch(
            id=patch.id,
            edits=top_edits,
            reasoning=reasoning,
            source_rollout_ids=list(patch.source_rollout_ids),
            estimated_impact=patch.estimated_impact,
            estimated_risk=patch.estimated_risk,
        )

    def _score_edit(self, edit: SkillEdit) -> float:
        """计算单条编辑的综合得分（0~1 范围）。

        Args:
            edit: 要评分的 SkillEdit。

        Returns:
            综合得分（0.0 ~ 1.0）。
        """
        support = self._support_score(edit)
        severity = self._severity_score(edit)
        generalization = self._generalization_score(edit)
        risk = self._risk_score(edit)
        conciseness = self._conciseness_score(edit)

        total = (
            support * self.WEIGHT_SUPPORT
            + severity * self.WEIGHT_SEVERITY
            + generalization * self.WEIGHT_GENERALIZATION
            + risk * self.WEIGHT_RISK
            + conciseness * self.WEIGHT_CONCISENESS
        )

        return round(total, 4)

    # ------------------------------------------------------------------
    # 各维度评分
    # ------------------------------------------------------------------

    @staticmethod
    def _support_score(edit: SkillEdit) -> float:
        """支持数评分：归一化到 0~1。

        support_count 越高越好，封顶在 10 次。

        Args:
            edit: SkillEdit 实例。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        return min(edit.support_count / 10.0, 1.0)

    @staticmethod
    def _severity_score(edit: SkillEdit) -> float:
        """失败严重度评分。

        failure 来源的编辑严重度最高（1.0），
        success 次之（0.7），其他最低（0.5）。

        Args:
            edit: SkillEdit 实例。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        if edit.source_type == "failure":
            return 1.0
        elif edit.source_type == "success":
            return 0.7
        else:
            return 0.5

    def _generalization_score(self, edit: SkillEdit) -> float:
        """泛化性评分：reasoning 中出现泛化关键词 → 高分。

        检查 edit.reason 中是否包含泛化关键词。

        Args:
            edit: SkillEdit 实例。

        Returns:
            1.0（泛化）或 0.5（非泛化）。
        """
        reason_lower = edit.reason.lower()
        for keyword in _GENERALIZATION_KEYWORDS:
            if keyword in reason_lower:
                return 1.0
        return 0.5

    @staticmethod
    def _conciseness_score(edit: SkillEdit) -> float:
        """简洁性评分：content 长度越短越高。

        - content 长度 < 200 → 1.0
        - 200-500 → 0.7
        - > 500 → 0.4
        - content 为 None → 1.0（delete 操作无新增内容）

        Args:
            edit: SkillEdit 实例。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        if edit.content is None:
            return 1.0

        length = len(edit.content)
        if length < 200:
            return 1.0
        elif length <= 500:
            return 0.7
        else:
            return 0.4

    def _risk_score(self, edit: SkillEdit) -> float:
        """风险评分：风险越低分数越高。

        - low → 1.0
        - medium → 0.7
        - high → 0.3

        Args:
            edit: SkillEdit 实例。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        risk_map = {
            "low": 1.0,
            "medium": 0.7,
            "high": 0.3,
        }
        return risk_map.get(edit.risk_level, 0.5)
