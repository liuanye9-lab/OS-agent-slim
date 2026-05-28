"""Skill 审核服务。

管理 Skill Patch 的 Validation → Human Review 流程。

核心约束：
1. Skill Patch 必须先通过 Validation Gate（new_score > old_score）
2. 再通过 Human Review（人工确认）
3. 两项都通过才允许 export best_skill.md

流程：
    candidate patch
        ↓
    validation run (ValidationGate.validate())
        ↓
    new_score > old_score? ─── NO → rejected
        ↓ YES
    human review ─── pending/approved/rejected
        ↓ approved
    export best_skill.md

用法::

    svc = SkillReviewService(repo, validation_gate, skill_exporter)
    result = svc.submit_patch(
        skill_id="skill_xxx",
        patch_content="...",
        workspace_id="ws_xxx",
        project_id="proj_xxx",
    )
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import (
    HumanReviewRecord,
    ReviewStatus,
    SkillPatchRecord,
    ValidationRunRecord,
    _new_id,
    _now,
)
from stable_agent.saas.repository import SaasRepository

logger = logging.getLogger(__name__)


class SkillReviewService:
    """Skill 审核服务。

    管理 Skill Patch 的全生命周期：提交 → 验证 → 审核 → 导出。

    Attributes:
        repo: SaaS 数据访问层实例。
        validation_gate: ValidationGate 实例（来自 skill_optimizer）。
        skill_exporter: SkillExporter 实例（来自 skill_optimizer）。
        skill_doc_store: SkillDocumentStore 实例（来自 skill_optimizer）。
    """

    def __init__(
        self,
        repo: SaasRepository | None = None,
        validation_gate: Any = None,
        skill_exporter: Any = None,
        skill_doc_store: Any = None,
    ) -> None:
        self.repo: SaasRepository = repo or SaasRepository()
        self.validation_gate: Any = validation_gate
        self.skill_exporter: Any = skill_exporter
        self.skill_doc_store: Any = skill_doc_store

    # ------------------------------------------------------------------
    # Patch 提交
    # ------------------------------------------------------------------

    def submit_patch(
        self,
        skill_id: str,
        patch_content: str,
        from_version: str = "",
        to_version: str = "",
        proposed_by: str = "system",
    ) -> SkillPatchRecord:
        """提交一个 Skill Patch。

        Args:
            skill_id: Skill ID。
            patch_content: 补丁内容。
            from_version: 源版本。
            to_version: 目标版本。
            proposed_by: 提议者。

        Returns:
            创建的 SkillPatchRecord。
        """
        if not to_version:
            to_version = f"v{_now():.0f}"

        patch = SkillPatchRecord(
            skill_id=skill_id,
            from_version=from_version,
            to_version=to_version,
            patch_content=patch_content,
            proposed_by=proposed_by,
            status="proposed",
        )
        ok = self.repo.save_skill_patch(patch)
        if not ok:
            raise RuntimeError("Skill Patch 保存失败")

        logger.info("Skill patch %s submitted for skill %s", patch.id, skill_id)
        return patch

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_patch(self, patch_id: str) -> ValidationRunRecord:
        """对 Skill Patch 执行 Validation Gate 验证。

        要求：
        1. 必须有 baseline_skill 和 candidate_skill
        2. candidate_score > baseline_score 才通过
        3. 通过后 patch 状态变为 "validated"

        Args:
            patch_id: Skill Patch ID。

        Returns:
            ValidationRunRecord。

        Raises:
            ValueError: Validation Gate 或 SkillDocumentStore 未初始化。
        """
        if self.validation_gate is None:
            raise ValueError("Validation Gate 未初始化，无法验证")
        if self.skill_doc_store is None:
            raise ValueError("SkillDocumentStore 未初始化，无法加载技能")

        patch = self.repo.get_skill_patch(patch_id)
        if patch is None:
            raise ValueError(f"Skill Patch 不存在: {patch_id}")

        # 加载 baseline 和 candidate skill
        from stable_agent.skill_optimizer.models import SkillDocument

        # 模拟：创建 baseline（当前版本）和 candidate（打补丁后）skill
        baseline = SkillDocument(
            name="baseline",
            version=patch.from_version or "v1.0",
            content="baseline skill content",  # 实际应从 doc_store 加载
        )
        candidate = SkillDocument(
            name="candidate",
            version=patch.to_version,
            content=patch.patch_content,
        )

        # 执行验证
        try:
            from stable_agent.skill_optimizer.models import ValidationResult
            result: ValidationResult = self.validation_gate.validate(
                baseline, candidate,
            )

            vr = ValidationRunRecord(
                patch_id=patch_id,
                baseline_score=result.baseline_score,
                candidate_score=result.candidate_score,
                score_delta=result.score_delta,
                passed=result.passed,
                regression_cases=result.regression_cases,
                explanation=result.explanation,
            )

            self.repo.save_validation_run(vr)

            # 更新 patch 状态
            new_status = "validated" if result.passed else "rejected"
            self.repo.update_skill_patch_status(patch_id, new_status)

            logger.info(
                "Validation for patch %s: passed=%s, delta=%.4f",
                patch_id, result.passed, result.score_delta,
            )
            return vr

        except Exception as e:
            logger.error("Validation run failed: %s", e)
            vr = ValidationRunRecord(
                patch_id=patch_id,
                passed=False,
                explanation=f"Validation 执行失败: {e}",
            )
            self.repo.save_validation_run(vr)
            return vr

    # ------------------------------------------------------------------
    # Human Review
    # ------------------------------------------------------------------

    def submit_for_review(
        self,
        patch_id: str,
        workspace_id: str,
        project_id: str,
    ) -> HumanReviewRecord:
        """将已验证的 Patch 提交人工审核。

        要求：patch 状态必须是 "validated"（已验证通过）。

        Args:
            patch_id: Skill Patch ID。
            workspace_id: 工作空间 ID。
            project_id: 项目 ID。

        Returns:
            HumanReviewRecord。

        Raises:
            ValueError: Patch 未通过验证。
        """
        patch = self.repo.get_skill_patch(patch_id)
        if patch is None:
            raise ValueError(f"Skill Patch 不存在: {patch_id}")
        if patch.status != "validated":
            raise ValueError(
                f"Patch 必须通过 Validation 才能提交审核。"
                f"当前状态: {patch.status}"
            )

        review = HumanReviewRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            target_type="skill_patch",
            target_id=patch_id,
            status=ReviewStatus.PENDING,
        )
        ok = self.repo.create_human_review(review)
        if not ok:
            raise RuntimeError("人工审核记录创建失败")

        # 更新 patch 状态
        self.repo.update_skill_patch_status(patch_id, "reviewing")

        logger.info("Human review %s created for patch %s", review.id, patch_id)
        return review

    def approve_review(
        self,
        review_id: str,
        reviewer: str = "",
        comment: str = "",
    ) -> HumanReviewRecord:
        """批准人工审核。

        审核通过后 patch 状态变为 "approved"，允许导出。

        Args:
            review_id: 审核记录 ID。
            reviewer: 审核人标识。
            comment: 审核意见。

        Returns:
            更新后的 HumanReviewRecord。

        Raises:
            ValueError: 审核记录不存在。
        """
        review = self.repo.get_human_review(review_id)
        if review is None:
            raise ValueError(f"审核记录不存在: {review_id}")

        ok = self.repo.update_human_review(review_id, ReviewStatus.APPROVED, comment)
        if not ok:
            raise RuntimeError("审核状态更新失败")

        # 更新关联的 patch 状态
        self.repo.update_skill_patch_status(review.target_id, "approved")

        return self.repo.get_human_review(review_id)  # type: ignore

    def reject_review(
        self,
        review_id: str,
        reviewer: str = "",
        comment: str = "",
    ) -> HumanReviewRecord:
        """拒绝人工审核。

        Args:
            review_id: 审核记录 ID。
            reviewer: 审核人标识。
            comment: 拒绝理由。

        Returns:
            更新后的 HumanReviewRecord。
        """
        review = self.repo.get_human_review(review_id)
        if review is None:
            raise ValueError(f"审核记录不存在: {review_id}")

        ok = self.repo.update_human_review(review_id, ReviewStatus.REJECTED, comment)
        if not ok:
            raise RuntimeError("审核状态更新失败")

        self.repo.update_skill_patch_status(review.target_id, "rejected")
        return self.repo.get_human_review(review_id)  # type: ignore

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export_best_skill(
        self,
        patch_id: str,
        target_path: str = "skills/best_skill.md",
    ) -> str:
        """导出最佳 Skill（需要先通过验证和审核）。

        流程：
        1. 检查 patch 状态是否为 "approved"
        2. 检查 validation 记录是否 passed
        3. 调用 SkillExporter.export()

        Args:
            patch_id: Skill Patch ID。
            target_path: 导出路径。

        Returns:
            导出文件的绝对路径。

        Raises:
            PermissionError: Patch 未通过验证或审核。
            ValueError: SkillExporter 未初始化。
        """
        if self.skill_exporter is None:
            raise ValueError("SkillExporter 未初始化，无法导出")

        # 检查 patch 状态
        patch = self.repo.get_skill_patch(patch_id)
        if patch is None:
            raise ValueError(f"Skill Patch 不存在: {patch_id}")
        if patch.status != "approved":
            raise PermissionError(
                f"Skill Patch 状态必须为 'approved'，当前: {patch.status}。"
                f"请先完成 Validation 和 Human Review。"
            )

        # 检查 validation 结果
        vr = self.repo.get_validation_run(patch_id)
        if vr is None or not vr.passed:
            raise PermissionError(
                "Skill Patch 未通过 Validation Gate。无法导出。"
            )

        # 导出（SkillExporter 内部也会做 Human Review check）
        try:
            result_path = self.skill_exporter.export(
                target_path=target_path,
                validation_passed=vr.passed,
                old_score=vr.baseline_score,
                new_score=vr.candidate_score,
                human_reviewed=True,
            )
            # 更新 patch 状态
            self.repo.update_skill_patch_status(patch_id, "exported")
            logger.info("Skill exported to: %s", result_path)
            return result_path
        except PermissionError:
            raise
        except Exception as e:
            logger.error("Skill export failed: %s", e)
            raise

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_patch_status(self, patch_id: str) -> dict[str, Any]:
        """获取 Patch 的完整状态信息。"""
        patch = self.repo.get_skill_patch(patch_id)
        if patch is None:
            return {"error": "not_found"}

        vr = self.repo.get_validation_run(patch_id)
        # 获取关联的审核记录
        hr = None  # 简化：通过 patch_id 查审核表
        try:
            conn = self.repo._get_conn()
            row = conn.execute(
                "SELECT * FROM human_reviews WHERE target_id=? AND target_type='skill_patch' ORDER BY created_at DESC LIMIT 1",
                (patch_id,),
            ).fetchone()
            if row:
                hr = HumanReviewRecord(
                    id=row["id"], workspace_id=row["workspace_id"],
                    project_id=row["project_id"], target_type=row["target_type"],
                    target_id=row["target_id"], reviewer=row["reviewer"],
                    status=row["status"], comment=row["comment"],
                    created_at=row["created_at"], resolved_at=row["resolved_at"],
                )
        except Exception:
            logger.debug("No human review found for patch %s", patch_id)

        return {
            "patch_id": patch.id,
            "skill_id": patch.skill_id,
            "from_version": patch.from_version,
            "to_version": patch.to_version,
            "status": patch.status,
            "validation": {
                "passed": vr.passed if vr else False,
                "baseline_score": vr.baseline_score if vr else 0,
                "candidate_score": vr.candidate_score if vr else 0,
                "score_delta": vr.score_delta if vr else 0,
            } if vr else None,
            "human_review": {
                "review_id": hr.id if hr else "",
                "status": hr.status if hr else "pending",
                "reviewer": hr.reviewer if hr else "",
            } if hr else None,
        }
