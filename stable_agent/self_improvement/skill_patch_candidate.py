"""skill_patch_candidate — Skill Patch 候选管理。

Skill patch 不能绕过 Validation Gate，必须包含完整追溯信息。
状态流转：
    candidate → validating → validated / validation_failed
    validated → waiting_review → approved / rejected
    approved → exported
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class SkillPatchStatus(StrEnum):
    """Skill Patch 状态。"""

    CANDIDATE = "candidate"                # 初始候选
    VALIDATING = "validating"              # 验证中
    VALIDATED = "validated"                # 验证通过
    VALIDATION_FAILED = "validation_failed"  # 验证失败
    WAITING_REVIEW = "waiting_review"      # 等待人工审核
    APPROVED = "approved"                  # 审核通过
    REJECTED = "rejected"                  # 审核拒绝
    EXPORTED = "exported"                  # 已导出


@dataclass
class SkillPatchCandidate:
    """Skill Patch 候选条目。

    每次 SkillOpt 分析产出后，生成 SkillPatchCandidate。
    必须通过 validation gate → human review 才能 exported。

    Attributes:
        patch_id: 补丁 ID。
        source_run_id: 来源 run ID。
        failure_mode: 失败模式描述。
        old_rule: 旧规则文本。
        new_rule: 新规则文本。
        patch_diff: diff 格式的变更摘要。
        expected_improvement: 期望的改进描述。
        risk_level: 风险等级（low/medium/high）。
        validation_report_id: 验证报告 ID。
        human_review_id: 人工审核 ID。
        status: 当前状态。
        created_at: 创建时间。
    """

    patch_id: str = field(default_factory=lambda: f"patch_{uuid.uuid4().hex[:12]}")
    source_run_id: str = ""
    failure_mode: str = ""
    old_rule: str = ""
    new_rule: str = ""
    patch_diff: str = ""
    expected_improvement: str = ""
    risk_level: str = "medium"
    validation_report_id: str = ""
    human_review_id: str = ""
    status: SkillPatchStatus = SkillPatchStatus.CANDIDATE
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """转换为字典格式（用于 JSON 序列化）。"""
        return {
            "patch_id": self.patch_id,
            "source_run_id": self.source_run_id,
            "failure_mode": self.failure_mode,
            "old_rule": self.old_rule,
            "new_rule": self.new_rule,
            "patch_diff": self.patch_diff,
            "expected_improvement": self.expected_improvement,
            "risk_level": self.risk_level,
            "validation_report_id": self.validation_report_id,
            "human_review_id": self.human_review_id,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    def can_export(self) -> tuple[bool, str]:
        """检查是否可以导出 best_skill.md。

        Returns:
            (是否可导出, 失败原因)。
        """
        if self.status != SkillPatchStatus.APPROVED:
            return False, f"状态必须是 approved，当前: {self.status.value}"
        if not self.human_review_id:
            return False, "缺少 human_review_id"
        if not self.validation_report_id:
            return False, "缺少 validation_report_id"
        return True, ""


class SkillPatchStore:
    """Skill Patch 候选存储。

    Attributes:
        _patches: 补丁字典。
    """

    def __init__(self) -> None:
        """初始化。"""
        self._patches: dict[str, SkillPatchCandidate] = {}

    def add(self, patch: SkillPatchCandidate) -> SkillPatchCandidate:
        """添加补丁候选。

        Args:
            patch: SkillPatchCandidate 实例。

        Returns:
            存储的实例。

        Raises:
            ValueError: 缺少必需字段。
        """
        if not patch.source_run_id:
            raise ValueError("SkillPatchCandidate 必须有 source_run_id")
        if not patch.new_rule.strip():
            raise ValueError("SkillPatchCandidate 必须有 new_rule")

        self._patches[patch.patch_id] = patch
        return patch

    def start_validation(self, patch_id: str) -> None:
        """开始验证 → validating。"""
        patch = self._patches.get(patch_id)
        if patch and patch.status == SkillPatchStatus.CANDIDATE:
            patch.status = SkillPatchStatus.VALIDATING

    def mark_validated(self, patch_id: str, report_id: str) -> None:
        """验证通过 → validated。"""
        patch = self._patches.get(patch_id)
        if patch and patch.status == SkillPatchStatus.VALIDATING:
            patch.status = SkillPatchStatus.VALIDATED
            patch.validation_report_id = report_id

    def mark_validation_failed(self, patch_id: str, reason: str = "") -> None:
        """验证失败 → validation_failed。"""
        patch = self._patches.get(patch_id)
        if patch and patch.status == SkillPatchStatus.VALIDATING:
            patch.status = SkillPatchStatus.VALIDATION_FAILED
            if reason:
                patch.failure_mode += f" [验证失败: {reason}]"

    def submit_for_review(self, patch_id: str) -> None:
        """提交人工审核 → waiting_review。"""
        patch = self._patches.get(patch_id)
        if patch and patch.status == SkillPatchStatus.VALIDATED:
            patch.status = SkillPatchStatus.WAITING_REVIEW

    def approve(self, patch_id: str, review_id: str) -> None:
        """审核通过 → approved。"""
        patch = self._patches.get(patch_id)
        if patch and patch.status == SkillPatchStatus.WAITING_REVIEW:
            patch.status = SkillPatchStatus.APPROVED
            patch.human_review_id = review_id

    def reject(self, patch_id: str, review_id: str, reason: str = "") -> None:
        """审核拒绝 → rejected。"""
        patch = self._patches.get(patch_id)
        if patch:
            patch.status = SkillPatchStatus.REJECTED
            patch.human_review_id = review_id
            if reason:
                patch.failure_mode += f" [审核拒绝: {reason}]"

    def mark_exported(self, patch_id: str) -> None:
        """标记已导出 → exported。"""
        patch = self._patches.get(patch_id)
        if patch and patch.status == SkillPatchStatus.APPROVED:
            patch.status = SkillPatchStatus.EXPORTED

    def get(self, patch_id: str) -> SkillPatchCandidate | None:
        """获取补丁候选。"""
        return self._patches.get(patch_id)

    def list_by_status(
        self, status: SkillPatchStatus | None = None
    ) -> list[SkillPatchCandidate]:
        """按状态列出。"""
        if status is None:
            return list(self._patches.values())
        return [p for p in self._patches.values() if p.status == status]

    def list_exportable(self) -> list[SkillPatchCandidate]:
        """列出所有 approved 状态（可导出）的补丁。"""
        return self.list_by_status(SkillPatchStatus.APPROVED)

    def list_waiting_review(self) -> list[SkillPatchCandidate]:
        """列出所有 waiting_review 状态的补丁。"""
        return self.list_by_status(SkillPatchStatus.WAITING_REVIEW)

    @property
    def count(self) -> int:
        return len(self._patches)

    @property
    def exportable_count(self) -> int:
        return len(self.list_exportable())
