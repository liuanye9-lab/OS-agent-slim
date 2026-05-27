"""Patch 合并引擎。

合并失败 patch + 成功 patch + rejected buffer 过滤 → 一个合并 patch。
策略：去重、冲突解决、优先修复失败、过滤已拒绝。
"""

from __future__ import annotations

import difflib
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional

from stable_agent.skill_optimizer.models import (
    SkillEdit,
    SkillPatch,
)

logger = logging.getLogger(__name__)


class PatchMerger:
    """合并失败 patch + 成功 patch + rejected buffer → 一个合并 patch。

    策略：
    1. 去重：相同 op + 相同 target 的 edit 只保留一个（保留 support_count 最高的）
    2. 冲突解决：同一 target 有 replace + 另一个操作 → 保留 replace（更精准）
    3. 优先修复失败：failure 来源的 edit 排在 success 前面
    4. 过滤已拒绝：与 rejected_buffer 相似度 > 0.8 的 edit 丢弃

    Attributes:
        rejected_buffer: RejectedEditBuffer 实例引用（可选）。
    """

    def __init__(self, rejected_buffer=None) -> None:
        """初始化 PatchMerger。

        Args:
            rejected_buffer: RejectedEditBuffer 实例引用，用于过滤已拒绝编辑。
        """
        self.rejected_buffer = rejected_buffer

    def merge(
        self,
        failure_patch: SkillPatch | None,
        success_patch: SkillPatch | None,
        rejected_buffer: list[SkillEdit] | None = None,
    ) -> SkillPatch:
        """合并两个 patch，过滤已拒绝编辑。

        Args:
            failure_patch: 失败分析生成的 patch（可为 None）。
            success_patch: 成功分析生成的 patch（可为 None）。
            rejected_buffer: 额外的已拒绝编辑列表（优先于实例属性）。

        Returns:
            合并后的 SkillPatch。
        """
        # 收集所有编辑
        all_edits: list[SkillEdit] = []

        # 先收集 failure 编辑（排在前面）
        if failure_patch is not None:
            all_edits.extend(failure_patch.edits)

        # 再收集 success 编辑
        if success_patch is not None:
            all_edits.extend(success_patch.edits)

        if not all_edits:
            return SkillPatch(
                id=str(uuid.uuid4()),
                edits=[],
                reasoning="合并结果为空：无编辑输入。",
                source_rollout_ids=[],
            )

        # 步骤 1: 去重
        deduped = self._deduplicate(all_edits)

        # 步骤 2: 冲突解决
        resolved = self._resolve_conflicts(deduped)

        # 步骤 3: 过滤已拒绝编辑
        filtered = self._filter_rejected(resolved, rejected_buffer)

        # 步骤 4: 排序：failure 来源在前
        failure_edits = [e for e in filtered if e.source_type == "failure"]
        other_edits = [e for e in filtered if e.source_type != "failure"]
        sorted_edits = failure_edits + other_edits

        # 组装合并 reasoning
        source_ids: list[str] = []
        if failure_patch is not None:
            source_ids.extend(failure_patch.source_rollout_ids)
        if success_patch is not None:
            source_ids.extend(success_patch.source_rollout_ids)

        reasoning_parts = [
            f"合并了 {len(failure_edits)} 条 failure 编辑和 "
            f"{len(other_edits)} 条其他编辑。",
            f"去重后保留 {len(deduped)} 条。",
            f"冲突解决后保留 {len(resolved)} 条。",
            f"过滤已拒绝后保留 {len(filtered)} 条。",
        ]

        return SkillPatch(
            id=str(uuid.uuid4()),
            edits=sorted_edits,
            reasoning=" ".join(reasoning_parts),
            source_rollout_ids=source_ids,
            estimated_impact=0.0,
            estimated_risk=0.0,
        )

    def _deduplicate(self, edits: list[SkillEdit]) -> list[SkillEdit]:
        """去重：相同 op+target 保留 support_count 最高的。

        - SkillEdit 的 (op, target) 元组为去重 key
        - append 编辑 target 为 None，用 content 前 50 字符做 key
        - 保留 support_count 最高的，如果相同保留更晚创建的

        Args:
            edits: 待去重的编辑列表。

        Returns:
            去重后的编辑列表。
        """
        groups: dict[tuple, list[SkillEdit]] = defaultdict(list)

        for edit in edits:
            key = self._dedup_key(edit)
            groups[key].append(edit)

        result: list[SkillEdit] = []
        for group in groups.values():
            if len(group) == 1:
                result.append(group[0])
            else:
                # 按 support_count 降序，相同则按 created_at 降序
                best = max(
                    group,
                    key=lambda e: (e.support_count, e.created_at.timestamp()),
                )
                result.append(best)

        return result

    def _resolve_conflicts(self, edits: list[SkillEdit]) -> list[SkillEdit]:
        """冲突解决：同一 target 只保留最精准的操作。

        规则：同一 target 有 replace + 另一个操作 → 保留 replace（更精准）。
        如果同一 target 有多个 replace，保留 support_count 最高的。

        Args:
            edits: 待冲突解决的编辑列表。

        Returns:
            冲突解决后的编辑列表。
        """
        # 按 target 分组（append 操作 target=None，不参与冲突解决）
        target_groups: dict[str, list[SkillEdit]] = defaultdict(list)
        no_target: list[SkillEdit] = []

        for edit in edits:
            if edit.target is None:
                no_target.append(edit)
            else:
                target_groups[edit.target].append(edit)

        result: list[SkillEdit] = list(no_target)

        for target, group in target_groups.items():
            if len(group) == 1:
                result.append(group[0])
            else:
                # 有 replace 操作 → 保留 replace
                replaces = [e for e in group if e.op == "replace"]
                if replaces:
                    # 多个 replace：保留 support_count 最高的
                    best = max(
                        replaces,
                        key=lambda e: (e.support_count, e.created_at.timestamp()),
                    )
                    result.append(best)
                else:
                    # 没有 replace：保留 support_count 最高的
                    best = max(
                        group,
                        key=lambda e: (e.support_count, e.created_at.timestamp()),
                    )
                    result.append(best)

        return result

    def _compute_support_count(
        self, edit: SkillEdit, all_edits: list[SkillEdit]
    ) -> int:
        """计算相似编辑的支持数。

        op+target 完全一致的其他编辑数 + 1（自身）。

        Args:
            edit: 目标编辑。
            all_edits: 所有编辑列表。

        Returns:
            支持数。
        """
        count = 1  # 自身
        target_key = self._dedup_key(edit)
        for other in all_edits:
            if other is edit:
                continue
            if self._dedup_key(other) == target_key:
                count += 1
        return count

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_key(edit: SkillEdit) -> tuple:
        """生成编辑的去重 key。

        Args:
            edit: SkillEdit 实例。

        Returns:
            (op, target_fingerprint) 元组。
        """
        if edit.target is not None:
            return (edit.op, edit.target)
        # append 操作：使用 content 前 50 字符作为标识
        content_key = (edit.content or "")[:50]
        return (edit.op, f"__append__{content_key}")

    def _filter_rejected(
        self,
        edits: list[SkillEdit],
        extra_rejected: list[SkillEdit] | None = None,
    ) -> list[SkillEdit]:
        """过滤与已拒绝编辑相似的编辑。

        使用 difflib.SequenceMatcher 计算相似度，相似度 > 0.8 的丢弃。

        Args:
            edits: 待过滤的编辑列表。
            extra_rejected: 额外的已拒绝编辑列表。

        Returns:
            过滤后的编辑列表。
        """
        if self.rejected_buffer is None and not extra_rejected:
            return list(edits)

        result: list[SkillEdit] = []
        for edit in edits:
            is_rejected = False

            # 检查实例 buffer
            if self.rejected_buffer is not None:
                if self.rejected_buffer.is_similar_to_rejected(edit):
                    logger.info("编辑 %s 与已拒绝编辑相似，已过滤", edit.id)
                    is_rejected = True
                    continue

            # 检查额外传入的 rejected 列表
            if extra_rejected:
                for rej in extra_rejected:
                    if self._is_similar(edit, rej):
                        logger.info(
                            "编辑 %s 与已拒绝编辑 %s 相似，已过滤",
                            edit.id,
                            rej.id,
                        )
                        is_rejected = True
                        break

            if not is_rejected:
                result.append(edit)

        return result

    @staticmethod
    def _is_similar(a: SkillEdit, b: SkillEdit, threshold: float = 0.8) -> bool:
        """检查两个编辑是否相似。

        Args:
            a: 第一个编辑。
            b: 第二个编辑。
            threshold: 相似度阈值，默认 0.8。

        Returns:
            True 如果相似。
        """
        # 相同 op + 相同 target → 相似
        if a.op == b.op and a.target == b.target:
            return True
        # 均为 append：比较 content 相似度
        if a.op == "append" and b.op == "append":
            content_a = (a.content or "")[:60]
            content_b = (b.content or "")[:60]
            ratio = difflib.SequenceMatcher(None, content_a, content_b).ratio()
            return ratio > threshold
        return False
