"""慢速元更新器。

周期性总结长期稳定规律，修改 SLOW_UPDATE 保护区。
只有当多轮优化结果稳定时，才生成仅修改保护区的低风险更新。
"""

from __future__ import annotations

import logging
import statistics
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from stable_agent.skill_optimizer.models import (
    SkillDocument,
    SkillEdit,
    SkillPatch,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SlowMetaUpdater:
    """慢速元更新器。

    周期性总结长期稳定规律，修改 SLOW_UPDATE 保护区。
    只有当连续多个 epoch 的结果稳定（标准差小）且存在长期模式时，
    才生成仅修改保护区的 SkillPatch。

    Attributes:
        min_epochs: 两次慢更新之间的最小 epoch 数。
    """

    def __init__(self, min_epochs_between_updates: int = 3) -> None:
        """初始化慢速元更新器。

        Args:
            min_epochs_between_updates: 触发慢更新需要的最小 epoch 数。
        """
        self.min_epochs: int = min_epochs_between_updates

    # ------------------------------------------------------------------
    # 生成慢更新
    # ------------------------------------------------------------------

    def generate_slow_update(
        self,
        previous_skill: SkillDocument,
        current_skill: SkillDocument,
        longitudinal_results: list[dict],
    ) -> SkillPatch | None:
        """检查是否应该生成慢更新。

        条件：
        - 至少 min_epochs 个 epoch 的数据
        - 最近结果稳定（标准差 < 0.1）
        - 存在未在保护区中的长期模式

        如果满足，生成一个只修改保护区的 SkillPatch。
        返回的 patch 中所有 edit 的 source_type="slow_update"，risk_level="low"。

        Args:
            previous_skill: 上一个 epoch 的 SkillDocument。
            current_skill: 当前 SkillDocument。
            longitudinal_results: 长期结果列表，每项包含
                {epoch, accepted_count, rejected_count, avg_score}。

        Returns:
            SkillPatch 如果应该生成慢更新，否则 None。
        """
        # 条件 1: 数据量检查
        if len(longitudinal_results) < self.min_epochs:
            logger.info(
                "慢更新跳过：数据不足（需 %d epoch，当前 %d）",
                self.min_epochs,
                len(longitudinal_results),
            )
            return None

        # 条件 2: 稳定性检查
        if not self._is_stable(longitudinal_results):
            logger.info(
                "慢更新跳过：最近 epoch 结果不稳定（标准差 >= 0.1）"
            )
            return None

        # 条件 3: 提取长期模式
        patterns = self._extract_long_term_patterns(longitudinal_results)
        if not patterns:
            logger.info("慢更新跳过：未检测到长期稳定模式")
            return None

        # 生成慢更新编辑
        edits: list[SkillEdit] = []
        for i, pattern in enumerate(patterns):
            edit = SkillEdit(
                id=f"slow-update-{uuid.uuid4().hex[:8]}",
                op="append",
                target=None,  # 慢更新通过 append 添加到保护区
                content=self._format_protected_content(pattern),
                reason=(
                    f"慢更新（第 {len(longitudinal_results)} epoch）："
                    f"连续稳定模式 — {pattern}"
                ),
                source_type="slow_update",
                support_count=len(longitudinal_results),
                risk_level="low",
                created_at=datetime.now(),
            )
            edits.append(edit)

        logger.info(
            "生成慢更新：%d 条编辑，基于 %d 个 epoch 的数据",
            len(edits),
            len(longitudinal_results),
        )

        return SkillPatch(
            id=f"slow-patch-{uuid.uuid4().hex[:8]}",
            edits=edits,
            reasoning=(
                f"慢速元更新：基于 {len(longitudinal_results)} 个 epoch 的 "
                f"稳定结果，提取了 {len(patterns)} 条长期规律。"
            ),
            source_rollout_ids=[],
            estimated_impact=0.05,
            estimated_risk=0.01,
            created_at=datetime.now(),
        )

    # ------------------------------------------------------------------
    # 模式提取
    # ------------------------------------------------------------------

    def _extract_long_term_patterns(
        self, results: list[dict]
    ) -> list[str]:
        """从长期结果中提取稳定规律。

        检查连续多个 epoch 都出现的高分模式：
        - 如果最近连续 min_epochs 个 epoch 的 avg_score 都 > 0.7
        - 且 accepted_count 趋势上升或稳定
        则生成相应的规律描述。

        Args:
            results: 长期结果列表。

        Returns:
            规律描述字符串列表。
        """
        patterns: list[str] = []

        if len(results) < self.min_epochs:
            return patterns

        # 检查最近 N 个 epoch
        recent = results[-self.min_epochs:]

        # 模式 1: 持续高分的趋势
        high_scores = all(
            r.get("avg_score", 0.0) > 0.7 for r in recent
        )
        if high_scores:
            avg_of_recent = statistics.mean(
                r.get("avg_score", 0.0) for r in recent
            )
            patterns.append(
                f"最近 {self.min_epochs} 个 epoch 均保持高分 "
                f"(平均 {avg_of_recent:.3f})，表明当前优化方向正确。"
            )

        # 模式 2: 接受率提升
        recent_accept_rates = [
            r.get("accepted_count", 0) / max(
                r.get("accepted_count", 0) + r.get("rejected_count", 0),
                1,
            )
            for r in recent
        ]
        if len(recent_accept_rates) >= 2:
            # 检查接受率是否稳定或上升
            if all(rate >= 0.5 for rate in recent_accept_rates):
                avg_rate = statistics.mean(recent_accept_rates)
                patterns.append(
                    f"接受率稳定在 {avg_rate:.1%} 以上，"
                    f"说明编辑质量可靠。"
                )

            # 趋势上升
            if (
                len(recent_accept_rates) >= 3
                and recent_accept_rates[-1] > recent_accept_rates[0]
            ):
                patterns.append(
                    "接受率呈上升趋势，优化策略持续改进。"
                )

        # 模式 3: 低拒绝率
        total_rejected = sum(
            r.get("rejected_count", 0) for r in recent
        )
        if total_rejected < 3:
            patterns.append(
                "拒绝编辑数量极少，当前策略与验证门判断一致。"
            )

        return patterns

    # ------------------------------------------------------------------
    # 稳定性检查
    # ------------------------------------------------------------------

    def _is_stable(self, results: list[dict]) -> bool:
        """判断最近 epoch 的结果是否稳定。

        计算最近 min_epochs 个 epoch 的 avg_score 标准差，
        如果 < 0.1 则视为稳定。

        Args:
            results: 长期结果列表。

        Returns:
            True 如果稳定。
        """
        if len(results) < self.min_epochs:
            return False

        recent = results[-self.min_epochs:]
        scores = [r.get("avg_score", 0.0) for r in recent]

        if len(scores) < 2:
            return False

        try:
            std_dev = statistics.stdev(scores)
        except statistics.StatisticsError:
            return False

        is_stable = std_dev < 0.1
        logger.debug(
            "稳定性检查：std=%.4f (需 < 0.1), stable=%s",
            std_dev,
            is_stable,
        )
        return is_stable

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _format_protected_content(pattern: str) -> str:
        """将规律格式化为保护区中的内容。

        包装在 SLOW_UPDATE 标记之间，确保只有 slow_update source_type
        的编辑能修改此内容。

        Args:
            pattern: 规律描述文本。

        Returns:
            格式化后的保护区内容。
        """
        from stable_agent.skill_optimizer.prompt_contracts import PromptContracts

        return (
            f"{PromptContracts.PROTECTED_START}\n"
            f"## 长期稳定规律\n"
            f"- {pattern}\n"
            f"{PromptContracts.PROTECTED_END}"
        )
