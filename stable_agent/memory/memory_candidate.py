"""MemoryCandidate — 候选记忆生命周期管理。

失败经验不能直接进入长期记忆，必须先作为候选进入审查流程。
只有满足以下条件才允许 promoted（晋升为长期记忆）：
- 有 source_run_id（可追溯到具体运行）
- 有 failure_attribution（失败归因记录）
- 有 validation_record（验证通过记录）
- 不含隐私原文（通过 sanitize 检查）
- 不与现有高置信记忆冲突

状态流转：
    candidate → validated → promoted
    candidate → rejected
    validated → expired
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class MemoryCandidateStatus(StrEnum):
    """候选记忆状态。"""

    CANDIDATE = "candidate"       # 初始候选
    VALIDATED = "validated"       # 验证通过
    REJECTED = "rejected"         # 被拒绝
    EXPIRED = "expired"           # 过期未处理
    PROMOTED = "promoted"         # 晋升为长期记忆


@dataclass
class MemoryCandidate:
    """候选记忆条目。

    失败经验在被确认有效前，只存在于候选区。
    晋升（promoted）需要满足多重条件。

    Attributes:
        candidate_id: 候选 ID。
        content: 记忆内容（不允许包含隐私原文）。
        source_run_id: 来源 run ID（必须可追溯）。
        failure_attribution: 失败归因记录。
        validation_record: 验证通过记录 ID。
        status: 当前状态。
        confidence: 置信度 0~1。
        created_at: 创建时间戳。
        tags: 标签列表。
        promoted_at: 晋升时间戳。
        privacy_sanitized: 是否已做隐私脱敏。
    """

    candidate_id: str = field(default_factory=lambda: f"mem_cand_{uuid.uuid4().hex[:12]}")
    content: str = ""
    source_run_id: str = ""
    failure_attribution: str = ""
    validation_record: str = ""
    status: MemoryCandidateStatus = MemoryCandidateStatus.CANDIDATE
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    promoted_at: float | None = None
    privacy_sanitized: bool = False


class MemoryCandidateStore:
    """候选记忆存储管理器。

    管理候选记忆的完整生命周期：添加 → 验证 → 晋升/拒绝/过期。

    Attributes:
        _candidates: 候选记忆字典 {candidate_id: MemoryCandidate}。
    """

    def __init__(self) -> None:
        """初始化空候选库。"""
        self._candidates: dict[str, MemoryCandidate] = {}

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def add(self, candidate: MemoryCandidate) -> MemoryCandidate:
        """添加一条候选记忆。

        自动检查隐私并标记 privacy_sanitized。

        Args:
            candidate: MemoryCandidate 实例。

        Returns:
            存储的 MemoryCandidate（可能被 sanitize 修改）。

        Raises:
            ValueError: 如果候选记忆缺少必需字段。
        """
        # 检查必需字段
        if not candidate.source_run_id:
            raise ValueError("MemoryCandidate 必须有 source_run_id")
        if not candidate.content.strip():
            raise ValueError("MemoryCandidate 内容不能为空")

        # 隐私脱敏检查
        candidate.privacy_sanitized = self._check_privacy(candidate.content)
        if not candidate.privacy_sanitized:
            candidate.content = self._sanitize(candidate.content)
            candidate.privacy_sanitized = True

        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def validate(self, candidate_id: str, validation_record: str) -> None:
        """标记 candidate → validated。

        Args:
            candidate_id: 候选记忆 ID。
            validation_record: 验证记录（test_run_id 等）。
        """
        cand = self._candidates.get(candidate_id)
        if cand and cand.status == MemoryCandidateStatus.CANDIDATE:
            cand.status = MemoryCandidateStatus.VALIDATED
            cand.validation_record = validation_record

    def reject(self, candidate_id: str, reason: str = "") -> None:
        """标记 candidate → rejected。

        Args:
            candidate_id: 候选记忆 ID。
            reason: 拒绝原因。
        """
        cand = self._candidates.get(candidate_id)
        if cand and cand.status == MemoryCandidateStatus.CANDIDATE:
            cand.status = MemoryCandidateStatus.REJECTED
            if reason:
                cand.failure_attribution += f" [拒绝原因: {reason}]"

    def promote(self, candidate_id: str) -> MemoryCandidate | None:
        """尝试晋升 candidate → promoted。

        晋升前置条件检查（任一不满足则拒绝晋升并返回 None）：
        1. status 必须是 validated
        2. 有 source_run_id
        3. 有 failure_attribution
        4. 有 validation_record
        5. privacy_sanitized 必须为 True

        Args:
            candidate_id: 候选记忆 ID。

        Returns:
            晋升成功返回 MemoryCandidate，失败返回 None。
        """
        cand = self._candidates.get(candidate_id)
        if cand is None:
            return None

        # 检查晋升条件
        checks: list[tuple[bool, str]] = [
            (cand.status == MemoryCandidateStatus.VALIDATED, "状态必须为 validated"),
            (bool(cand.source_run_id), "必须有 source_run_id"),
            (bool(cand.failure_attribution), "必须有 failure_attribution"),
            (bool(cand.validation_record), "必须有 validation_record"),
            (cand.privacy_sanitized, "必须通过隐私脱敏检查"),
        ]

        for passed, reason in checks:
            if not passed:
                cand.failure_attribution += f" [晋升失败: {reason}]"
                return None

        cand.status = MemoryCandidateStatus.PROMOTED
        cand.promoted_at = time.time()
        return cand

    def expire_old(self, max_age_hours: int = 168) -> int:
        """将超过 max_age_hours 且仍为 candidate 的条目标记为 expired。

        Args:
            max_age_hours: 最大存活小时数，默认 168（7天）。

        Returns:
            标记为 expired 的条目数。
        """
        now = time.time()
        expired_count = 0
        for cand in self._candidates.values():
            if cand.status == MemoryCandidateStatus.CANDIDATE:
                age_hours = (now - cand.created_at) / 3600
                if age_hours > max_age_hours:
                    cand.status = MemoryCandidateStatus.EXPIRED
                    expired_count += 1
        return expired_count

    def get(self, candidate_id: str) -> MemoryCandidate | None:
        """获取指定候选记忆。

        Args:
            candidate_id: 候选记忆 ID。

        Returns:
            MemoryCandidate 或 None。
        """
        return self._candidates.get(candidate_id)

    def list_by_status(
        self, status: MemoryCandidateStatus | None = None
    ) -> list[MemoryCandidate]:
        """按状态列出候选记忆。

        Args:
            status: 过滤状态，None 返回全部。

        Returns:
            候选记忆列表。
        """
        if status is None:
            return list(self._candidates.values())
        return [c for c in self._candidates.values() if c.status == status]

    def list_promotable(self) -> list[MemoryCandidate]:
        """列出所有 validated 状态（可晋升）的候选。

        Returns:
            可晋升的候选记忆列表。
        """
        return self.list_by_status(MemoryCandidateStatus.VALIDATED)

    @property
    def count(self) -> int:
        """返回候选记忆总数。"""
        return len(self._candidates)

    @property
    def promotable_count(self) -> int:
        """返回可晋升的候选数量。"""
        return len(self.list_promotable())

    # ------------------------------------------------------------------
    # 隐私检查
    # ------------------------------------------------------------------

    # 隐私敏感模式
    _PRIVACY_PATTERNS: list[str] = [
        r"\b\d{15,19}\b",                     # 身份证/银行卡号（15-19位数字）
        r"\b1[3-9]\d{9}\b",                   # 中国手机号
        r"\b[\w.-]+@[\w.-]+\.\w{2,}\b",       # 邮箱
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IP地址
        r"(?:password|passwd|secret|token|api[_\s]?key)\s*[:=]\s*\S+",  # 凭据
    ]

    @classmethod
    def _check_privacy(cls, content: str) -> bool:
        """检查内容是否包含隐私敏感信息。

        Args:
            content: 待检查文本。

        Returns:
            True 表示无隐私问题，False 表示包含敏感信息。
        """
        for pattern in cls._PRIVACY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        return True

    @classmethod
    def _sanitize(cls, content: str) -> str:
        """对隐私敏感信息进行脱敏处理。

        将匹配到的敏感模式替换为占位符。

        Args:
            content: 原始内容。

        Returns:
            脱敏后的内容。
        """
        sanitized = content
        sanitized = re.sub(r"\b\d{15,19}\b", "[ID_NUMBER]", sanitized)
        sanitized = re.sub(r"\b1[3-9]\d{9}\b", "[PHONE]", sanitized)
        sanitized = re.sub(r"\b[\w.-]+@[\w.-]+\.\w{2,}\b", "[EMAIL]", sanitized)
        sanitized = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]", sanitized)
        sanitized = re.sub(
            r"(password|passwd|secret|token|api[_\s]?key)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
        return sanitized
