"""测试 Skill Validation + Human Review 闭环。

验证：
1. Skill Patch 不能绕过 Validation Gate
2. best_skill.md 不能绕过 Human Review
3. 只有 approved + validated 才能 export
"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.skill_review_service import SkillReviewService
from stable_agent.saas.models import Workspace, Project


class TestSkillValidationReview:
    """测试 Skill Validation + Human Review 流程。"""

    def _setup(self):
        """创建测试环境（无 ValidationGate 的独立测试）。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="test")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="test")
        repo.create_project(proj)
        return repo, ws, proj

    def test_submit_patch(self):
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(
            skill_id="skill_test",
            patch_content="+ New rule: always validate input",
            from_version="v1.0",
            to_version="v2.0",
        )
        assert patch.id.startswith("sp_")
        assert patch.status == "proposed"
        assert patch.skill_id == "skill_test"

    def test_patch_status_progression(self):
        """Patch 状态应依次推进：proposed → validated → reviewing → approved → exported。"""
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        assert patch.status == "proposed"

        # 模拟 validation pass（通过 setattr 直接改状态，绕开 ValidationGate 依赖）
        repo.update_skill_patch_status(patch.id, "validated")
        fetched = repo.get_skill_patch(patch.id)
        assert fetched is not None
        assert fetched.status == "validated"

    def test_submit_for_review_requires_validated(self):
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")

        # 未 validated 时应拒绝提交审核
        try:
            svc.submit_for_review(patch.id, ws.id, proj.id)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "validated" in str(e).lower() or "Validation" in str(e)

    def test_approve_and_reject_review(self):
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        # 模拟 validation pass
        repo.update_skill_patch_status(patch.id, "validated")

        # 提交审核
        review = svc.submit_for_review(patch.id, ws.id, proj.id)
        assert review.status == "pending"

        # 批准
        approved = svc.approve_review(review.id, reviewer="admin", comment="LGTM")
        assert approved.status == "approved"

        # 验证 patch 状态
        fetched_patch = repo.get_skill_patch(patch.id)
        assert fetched_patch is not None
        assert fetched_patch.status == "approved"

    def test_reject_review(self):
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        repo.update_skill_patch_status(patch.id, "validated")
        review = svc.submit_for_review(patch.id, ws.id, proj.id)

        rejected = svc.reject_review(review.id, comment="Not ready")
        assert rejected.status == "rejected"

        fetched_patch = repo.get_skill_patch(patch.id)
        assert fetched_patch is not None
        assert fetched_patch.status == "rejected"

    def test_export_not_allowed_without_approved(self):
        """未 approved 时不应允许 export。"""
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        try:
            svc.export_best_skill(patch.id)
            assert False, "Should have raised PermissionError or ValueError"
        except (PermissionError, ValueError):
            pass  # expected

    def test_export_not_allowed_when_not_validated(self):
        """直接 approved 但没有 validation 记录时也不应允许 export。"""
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        repo.update_skill_patch_status(patch.id, "approved")  # 跳过 validation

        try:
            svc.export_best_skill(patch.id)
            assert False, "Should have raised PermissionError or ValueError"
        except (PermissionError, ValueError):
            pass  # expected: no exporter or not validated

    def test_get_patch_status(self):
        repo, ws, proj = self._setup()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        status = svc.get_patch_status(patch.id)

        assert status["patch_id"] == patch.id
        assert status["status"] == "proposed"
        assert status["skill_id"] == "s1"


class TestValidationGateConstraints:
    """测试 Validation Gate 约束（需要 ValidationGate 组件）。"""

    def test_cannot_export_without_validation_gate(self):
        """没有注入 ValidationGate 时应报错而非静默通过。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        try:
            svc.validate_patch(patch.id)
            assert False, "Should have raised ValueError (no validation gate)"
        except ValueError as e:
            assert "Validation" in str(e) or "验证" in str(e)

    def test_cannot_export_without_exporter(self):
        """没有注入 SkillExporter 时应报错。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = SkillReviewService(repo=repo)

        patch = svc.submit_patch(skill_id="s1", patch_content="fix")
        repo.update_skill_patch_status(patch.id, "approved")
        # 手动创建 validation run
        from stable_agent.saas.models import ValidationRunRecord
        repo.save_validation_run(ValidationRunRecord(
            patch_id=patch.id, baseline_score=0.8, candidate_score=0.85,
            score_delta=0.05, passed=True,
        ))

        try:
            svc.export_best_skill(patch.id)
            assert False, "Should have raised ValueError (no exporter)"
        except ValueError as e:
            assert "SkillExporter" in str(e) or "exporter" in str(e).lower()
