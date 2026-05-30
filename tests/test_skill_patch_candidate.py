"""test_skill_patch_candidate — 测试 SkillPatchCandidate 生命周期。"""
import pytest
from stable_agent.self_improvement.skill_patch_candidate import (
    SkillPatchCandidate,
    SkillPatchStatus,
    SkillPatchStore,
)


class TestSkillPatchCandidate:
    """SkillPatchCandidate 核心测试。"""

    def test_cannot_export_without_review(self):
        """未审核不能导出。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="新规则",
            status=SkillPatchStatus.VALIDATED,
        )
        can, reason = patch.can_export()
        assert not can

    def test_cannot_export_without_validation_report(self):
        """缺少 validation_report_id 不能导出。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="新规则",
            human_review_id="review-001",
            status=SkillPatchStatus.APPROVED,
        )
        can, reason = patch.can_export()
        assert not can
        assert "validation" in reason.lower()

    def test_can_export_when_approved(self):
        """approved + 完整字段可导出。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="新规则",
            validation_report_id="val-001",
            human_review_id="review-001",
            status=SkillPatchStatus.APPROVED,
        )
        can, reason = patch.can_export()
        assert can

    def test_cannot_export_when_rejected(self):
        """rejected 状态不能导出。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="新规则",
            validation_report_id="val-001",
            human_review_id="review-001",
            status=SkillPatchStatus.REJECTED,
        )
        can, reason = patch.can_export()
        assert not can


class TestSkillPatchStore:
    """SkillPatchStore 核心测试。"""

    def setup_method(self):
        self.store = SkillPatchStore()

    def test_add_requires_source_run_id(self):
        """需要 source_run_id。"""
        with pytest.raises(ValueError):
            self.store.add(SkillPatchCandidate(source_run_id="", new_rule="rule"))

    def test_add_requires_new_rule(self):
        """需要 new_rule。"""
        with pytest.raises(ValueError):
            self.store.add(SkillPatchCandidate(source_run_id="run-001", new_rule=""))

    def test_full_lifecycle(self):
        """完整生命周期: candidate → validating → validated → waiting_review → approved → exported。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="不要在生产环境直接删除数据",
            failure_mode="数据丢失",
            risk_level="high",
        )
        self.store.add(patch)

        # 验证
        self.store.start_validation(patch.patch_id)
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.VALIDATING

        self.store.mark_validated(patch.patch_id, "val-001")
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.VALIDATED

        # 审核
        self.store.submit_for_review(patch.patch_id)
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.WAITING_REVIEW

        self.store.approve(patch.patch_id, "review-001")
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.APPROVED

        # 导出
        self.store.mark_exported(patch.patch_id)
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.EXPORTED

    def test_validation_failed(self):
        """验证失败应正确标记。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="规则",
        )
        self.store.add(patch)
        self.store.start_validation(patch.patch_id)
        self.store.mark_validation_failed(patch.patch_id, "测试失败")
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.VALIDATION_FAILED

    def test_reject_patch(self):
        """审核拒绝。"""
        patch = SkillPatchCandidate(
            source_run_id="run-001",
            new_rule="规则",
        )
        self.store.add(patch)
        self.store.reject(patch.patch_id, "review-001", "不合理")
        p = self.store.get(patch.patch_id)
        assert p.status == SkillPatchStatus.REJECTED
        assert "审核拒绝" in p.failure_mode

    def test_list_exportable(self):
        """list_exportable 应只返回 approved 状态。"""
        p1 = SkillPatchCandidate(source_run_id="run-001", new_rule="规则1")
        p2 = SkillPatchCandidate(source_run_id="run-002", new_rule="规则2")
        self.store.add(p1)
        self.store.add(p2)

        # 只有 p1 走完审核
        self.store.start_validation(p1.patch_id)
        self.store.mark_validated(p1.patch_id, "val-001")
        self.store.submit_for_review(p1.patch_id)
        self.store.approve(p1.patch_id, "review-001")

        exportable = self.store.list_exportable()
        assert len(exportable) == 1
        assert exportable[0].patch_id == p1.patch_id

    def test_list_waiting_review(self):
        """list_waiting_review 应正确。"""
        p = SkillPatchCandidate(source_run_id="run-001", new_rule="规则")
        self.store.add(p)
        self.store.start_validation(p.patch_id)
        self.store.mark_validated(p.patch_id, "val-001")
        self.store.submit_for_review(p.patch_id)

        waiting = self.store.list_waiting_review()
        assert len(waiting) == 1
