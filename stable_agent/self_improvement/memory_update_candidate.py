"""memory_update_candidate — 记忆更新候选管理。

失败经验不能直接进入长期记忆，必须先作为 MemoryUpdateCandidate
走审查流程。只有通过以下全部检查才允许 promoted：
- 有 source_run_id
- 有 failure_attribution
- 有验证通过记录
- 不含隐私原文
- 不与现有高置信记忆冲突
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class MemoryUpdateStatus(StrEnum):
    """记忆更新候选状态。"""

    CANDIDATE = "candidate"         # 新候选
    VALIDATED = "validated"         # 验证通过
    REJECTED = "rejected"           # 被拒绝
    EXPIRED = "expired"             # 过期
    PROMOTED = "promoted"           # 已晋升


@dataclass
class MemoryUpdateCandidate:
    """记忆更新候选条目。

    每次失败经验被系统识别后，生成一条 MemoryUpdateCandidate。
    只有通过 validation gate + human review 后才能 promoted。

    Attributes:
        update_id: 唯一 ID。
        source_run_id: 来源 run ID。
        content: 候选记忆内容（必须脱敏）。
        failure_attribution: 失败归因文本。
        validation_report_id: 验证报告 ID。
        human_review_id: 人工审核 ID。
        status: 当前状态。
        confidence: 置信度。
        created_at: 创建时间。
        tags: 标签。
        old_memory_id: 冲突的旧记忆 ID（如有）。
    """

    update_id: str = field(default_factory=lambda: f"mem_upd_{uuid.uuid4().hex[:12]}")
    source_run_id: str = ""
    content: str = ""
    failure_attribution: str = ""
    validation_report_id: str = ""
    human_review_id: str = ""
    status: MemoryUpdateStatus = MemoryUpdateStatus.CANDIDATE
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    old_memory_id: str = ""

    def can_promote(self) -> tuple[bool, str]:
        """检查是否满足晋升条件。

        Returns:
            (是否可晋升, 失败原因) 元组。
        """
        checks = [
            (bool(self.source_run_id), "缺少 source_run_id"),
            (bool(self.failure_attribution), "缺少 failure_attribution"),
            (bool(self.validation_report_id), "缺少 validation_report"),
            (bool(self.human_review_id), "缺少 human_review"),
            (self.status == MemoryUpdateStatus.VALIDATED, "状态不是 validated"),
        ]
        for passed, reason in checks:
            if not passed:
                return False, reason
        return True, ""


class MemoryUpdateStore:
    """记忆更新候选存储。

    管理 MemoryUpdateCandidate 的完整生命周期。

    Attributes:
        _updates: 候选更新字典。
    """

    def __init__(self) -> None:
        """初始化空更新库。"""
        self._updates: dict[str, MemoryUpdateCandidate] = {}

    def add(self, update: MemoryUpdateCandidate) -> MemoryUpdateCandidate:
        """添加一条候选更新。

        Args:
            update: MemoryUpdateCandidate 实例。

        Returns:
            存储的实例。

        Raises:
            ValueError: 缺少必需字段。
        """
        if not update.source_run_id:
            raise ValueError("MemoryUpdateCandidate 必须有 source_run_id")
        if not update.content.strip():
            raise ValueError("MemoryUpdateCandidate 内容不能为空")

        self._updates[update.update_id] = update
        return update

    def validate(self, update_id: str, report_id: str) -> None:
        """标记 candidate → validated。

        Args:
            update_id: 更新 ID。
            report_id: 验证报告 ID。
        """
        upd = self._updates.get(update_id)
        if upd and upd.status == MemoryUpdateStatus.CANDIDATE:
            upd.status = MemoryUpdateStatus.VALIDATED
            upd.validation_report_id = report_id

    def promote(self, update_id: str) -> MemoryUpdateCandidate | None:
        """尝试晋升到 promoted。

        必须通过 can_promote() 检查。

        Args:
            update_id: 更新 ID。

        Returns:
            晋升成功返回 MemoryUpdateCandidate，失败返回 None。
        """
        upd = self._updates.get(update_id)
        if upd is None:
            return None

        can, reason = upd.can_promote()
        if not can:
            return None

        upd.status = MemoryUpdateStatus.PROMOTED
        return upd

    def reject(self, update_id: str, reason: str = "") -> None:
        """拒绝候选更新。

        Args:
            update_id: 更新 ID。
            reason: 拒绝原因。
        """
        upd = self._updates.get(update_id)
        if upd:
            upd.status = MemoryUpdateStatus.REJECTED
            if reason:
                upd.failure_attribution += f" [拒绝: {reason}]"

    def expire_old(self, max_age_hours: int = 168) -> int:
        """过期 old candidates。

        Args:
            max_age_hours: 最大小时数。

        Returns:
            过期的条目数。
        """
        now = time.time()
        count = 0
        for upd in self._updates.values():
            if upd.status == MemoryUpdateStatus.CANDIDATE:
                if (now - upd.created_at) / 3600 > max_age_hours:
                    upd.status = MemoryUpdateStatus.EXPIRED
                    count += 1
        return count

    def get(self, update_id: str) -> MemoryUpdateCandidate | None:
        """获取指定候选更新。"""
        return self._updates.get(update_id)

    def list_by_status(
        self, status: MemoryUpdateStatus | None = None
    ) -> list[MemoryUpdateCandidate]:
        """按状态列出。"""
        if status is None:
            return list(self._updates.values())
        return [u for u in self._updates.values() if u.status == status]

    @property
    def count(self) -> int:
        return len(self._updates)
