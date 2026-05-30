"""V9.1: Human Review Export Gate Tests.

验证三个关键约束:
1. approve_patch 不自动导出 best_skill.md
2. export_approved_patch 需要 APPROVED 状态 + human_review_id + validation_report_id
3. dry_run_learning=True 时拒绝导出

配合 force_validation_passed 参数:
- force_validation_passed=False → validation_failed, 不进 human_review
- force_validation_passed=True → human_review.required, 但不自动 export
"""

from __future__ import annotations

import pytest

from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
from stable_agent.self_improvement.skill_patch_candidate import (
    SkillPatchCandidate,
    SkillPatchStatus,
    SkillPatchStore,
)


def _make_proof_loop() -> SelfImprovementProofLoop:
    """创建一个最小化的 proof_loop 实例用于测试。"""
    return SelfImprovementProofLoop()


class TestApprovePatchDoesNotExport:
    """approve_patch 通过后不自动导出 best_skill.md。"""

    def test_approve_no_export_call(self):
        """approve_patch 后 best_skill.md 不被创建。"""
        loop = _make_proof_loop()

        # 手动创建一个 patch 并通过完整状态链推进到 WAITING_REVIEW
        patch = SkillPatchCandidate(
            patch_id="test-patch-001",
            source_run_id="run-001",
            old_rule="old_rule_v1",
            new_rule="new_rule_v2",
            failure_mode="intent_drift",
            expected_improvement="fix intent drift",
            risk_level="low",
        )
        loop.patch_store.add(patch)

        # 完整状态链: CANDIDATE → VALIDATING → VALIDATED → WAITING_REVIEW
        loop.patch_store.start_validation(patch.patch_id)
        loop.patch_store.mark_validated(patch.patch_id, report_id="vr-001")
        loop.patch_store.submit_for_review(patch.patch_id)
        assert loop.patch_store.get(patch.patch_id).status == SkillPatchStatus.WAITING_REVIEW

        # 审核通过
        result = loop.approve_patch(patch.patch_id, review_id="review-001")

        # 验证: patch 是 APPROVED 但没有 EXPORTED
        assert result is not None
        assert result.status == SkillPatchStatus.APPROVED
        assert result.human_review_id == "review-001"

        # 验证: 状态不是 EXPORTED
        assert result.status != SkillPatchStatus.EXPORTED

        # 验证: can_export() 应该返回 True（满足三条件）
        can_export, reason = result.can_export()
        assert can_export is True, f"can_export should be True after approve, got: {reason}"


class TestExportRequiresApprovedPatch:
    """export_approved_patch 需要满足三条件: APPROVED + human_review_id + validation_report_id。"""

    def test_export_rejects_non_approved_patch(self):
        """非 APPROVED 状态的 patch 不能导出。"""
        loop = _make_proof_loop()

        # 创建一个 CANDIDATE 状态的 patch
        patch = SkillPatchCandidate(
            patch_id="test-patch-002",
            source_run_id="run-002",
            old_rule="old_rule",
            new_rule="new_rule",
            failure_mode="low_quality",
        )
        loop.patch_store._patches[patch.patch_id] = patch

        # 尝试导出 → 应该失败
        with pytest.raises(ValueError, match="不可导出"):
            loop.export_approved_patch(patch.patch_id)

    def test_export_rejects_without_human_review_id(self):
        """没有 human_review_id 的 patch 不能导出。"""
        loop = _make_proof_loop()

        # 创建一个 APPROVED 但没有 human_review_id 的 patch
        patch = SkillPatchCandidate(
            patch_id="test-patch-003",
            source_run_id="run-003",
            old_rule="old",
            new_rule="new",
            failure_mode="intent_drift",
            status=SkillPatchStatus.APPROVED,
            # 不设 human_review_id
        )
        loop.patch_store._patches[patch.patch_id] = patch

        with pytest.raises(ValueError, match="不可导出"):
            loop.export_approved_patch(patch.patch_id)

    def test_export_rejects_without_validation_report_id(self):
        """没有 validation_report_id 的 patch 不能导出。"""
        loop = _make_proof_loop()

        # 创建 APPROVED + human_review_id 但没有 validation_report_id
        patch = SkillPatchCandidate(
            patch_id="test-patch-004",
            source_run_id="run-004",
            old_rule="old",
            new_rule="new",
            failure_mode="intent_drift",
            status=SkillPatchStatus.APPROVED,
            human_review_id="review-004",
            # 不设 validation_report_id
        )
        loop.patch_store._patches[patch.patch_id] = patch

        with pytest.raises(ValueError, match="不可导出"):
            loop.export_approved_patch(patch.patch_id)


class TestDryRunLearningNeverExports:
    """dry_run_learning=True 时绝不导出 best_skill.md。"""

    def test_dry_run_blocks_export(self):
        """dry_run=True 时 export_approved_patch 拒绝执行。"""
        loop = _make_proof_loop()

        # 创建一个完全符合条件的 patch
        patch = SkillPatchCandidate(
            patch_id="test-patch-005",
            source_run_id="run-005",
            old_rule="old",
            new_rule="new",
            failure_mode="intent_drift",
            status=SkillPatchStatus.APPROVED,
            human_review_id="review-005",
            validation_report_id="vr-005",
        )
        loop.patch_store._patches[patch.patch_id] = patch

        # dry_run=True → 应该拒绝
        with pytest.raises(ValueError, match="dry_run"):
            loop.export_approved_patch(patch.patch_id, dry_run=True)

    def test_dry_run_in_evaluate_and_learn_sets_status(self):
        """dry_run_learning=True → human_review_status='dry_run'。"""
        loop = _make_proof_loop()

        report = loop.evaluate_and_learn(
            run_id="run-dry",
            eval_passed=False,
            eval_score=0.2,
            eval_reason="test dry run",
            failure_mode="intent_drift",
            force_regression_case=True,
            force_skill_patch=True,
            dry_run_learning=True,
        )

        assert report.human_review_status == "dry_run"
        assert report.human_review_required is False
        assert report.learning_triggered is True

    def test_force_validation_passed_false_no_human_review(self):
        """force_validation_passed=False → validation_failed, 不进 human_review。"""
        loop = _make_proof_loop()

        report = loop.evaluate_and_learn(
            run_id="run-val-fail",
            eval_passed=False,
            eval_score=0.2,
            eval_reason="test val fail",
            failure_mode="intent_drift",
            force_regression_case=True,
            force_skill_patch=True,
            force_validation_passed=False,
        )

        assert report.validation_passed is False
        assert report.human_review_status in ("validation_failed", "none")
        assert report.human_review_required is False

    def test_force_validation_passed_true_forces_human_review(self):
        """force_validation_passed=True → 强制进入 human_review.required。"""
        loop = _make_proof_loop()

        report = loop.evaluate_and_learn(
            run_id="run-val-pass",
            eval_passed=False,
            eval_score=0.2,
            eval_reason="test val pass",
            failure_mode="intent_drift",
            force_regression_case=True,
            force_skill_patch=True,
            force_validation_passed=True,
        )

        assert report.human_review_required is True
        assert report.human_review_status == "pending"
