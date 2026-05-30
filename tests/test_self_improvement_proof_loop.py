"""test_self_improvement_proof_loop — 测试 SelfImprovementProofLoop。"""
import pytest
from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
from stable_agent.self_improvement.memory_update_candidate import (
    MemoryUpdateStore,
    MemoryUpdateStatus,
)
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchStore


class TestSelfImprovementProofLoop:
    """SelfImprovementProofLoop 核心测试。"""

    def setup_method(self):
        self.loop = SelfImprovementProofLoop(
            memory_store=MemoryUpdateStore(),
            patch_store=SkillPatchStore(),
            min_confidence=0.6,
        )

    def test_no_learning_when_eval_passed(self):
        """评估通过时不触发学习。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=True,
            eval_score=0.9,
            eval_reason="测试通过",
        )
        assert not report.learning_triggered
        assert "未触发" in report.summary_zh

    def test_no_learning_when_score_high(self):
        """高分数不触发学习。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.85,
            eval_reason="高置信",
        )
        assert not report.learning_triggered

    def test_learning_triggered_when_failed(self):
        """评估失败应触发学习。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="上下文丢失",
            failure_mode="context_loss",
        )
        assert report.learning_triggered
        assert len(report.regression_cases) >= 1
        assert len(report.memory_candidates) >= 1

    def test_skill_patch_generated_on_failure_mode(self):
        """有 failure_mode 时应生成 skill patch。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="评估失败",
            failure_mode="数据丢失",
        )
        assert len(report.skill_patches) >= 1

    def test_no_skill_patch_without_failure_mode(self):
        """无 failure_mode 时不生成 skill patch。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="评估失败",
            failure_mode="",  # 空
        )
        assert len(report.skill_patches) == 0

    def test_human_review_required_when_patches(self):
        """有 patches 时需要人工审核。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="失败",
            failure_mode="error",
        )
        assert report.human_review_required

    def test_memory_not_promoted_directly(self):
        """失败经验不能直接 promoted（需通过 can_promote 检查）。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="失败",
            failure_mode="error",
        )
        # memory_candidates 应在 CANDIDATE 状态，不是 PROMOTED
        for mc in report.memory_candidates:
            assert mc.status == "candidate"

    def test_approve_patch(self):
        """审批通过 patch。"""
        self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="失败",
            failure_mode="error",
        )
        if self.loop.has_pending_reviews:
            waiting = self.loop.patch_store.list_waiting_review()
            if waiting:
                approved = self.loop.approve_patch(waiting[0].patch_id, "review-001")
                assert approved is not None
                assert approved.status.value == "approved"

    def test_reject_patch(self):
        """审批拒绝 patch。"""
        self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="失败",
            failure_mode="error",
        )
        if self.loop.has_pending_reviews:
            waiting = self.loop.patch_store.list_waiting_review()
            if waiting:
                rejected = self.loop.reject_patch(waiting[0].patch_id, "review-001", "不合理")
                assert rejected is not None
                assert rejected.status.value == "rejected"

    def test_get_report(self):
        """get_report 应返回 last_report。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="失败",
            failure_mode="error",
        )
        assert self.loop.get_report() is not None
        assert self.loop.get_report().run_id == "run-001"

    def test_min_confidence_threshold(self):
        """min_confidence 阈值应生效。"""
        loop = SelfImprovementProofLoop(min_confidence=0.5)
        report = loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=False,
            eval_score=0.55,  # > 0.5
            eval_reason="一般",
        )
        assert not report.learning_triggered

    def test_eval_passed_does_not_learn(self):
        """V8.1: 评估通过时不触发学习。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-001",
            eval_passed=True,
            eval_score=0.9,
            eval_reason="任务完成",
        )
        assert not report.learning_triggered

    def test_no_regression_cases_blocks_validation(self):
        """V8.1: 无回归用例时验证失败，不进 Human Review。"""
        loop = SelfImprovementProofLoop(min_confidence=0.1)
        report = loop.evaluate_and_learn(
            run_id="run-no-cases",
            eval_passed=False,
            eval_score=0.2,
            eval_reason="失败但无法生成用例",
            failure_mode="",
        )
        assert not report.validation_passed
        assert not report.human_review_required

    def test_memory_candidate_not_promoted_without_review(self):
        """V8.1: Memory candidate 不会自动 promote。"""
        report = self.loop.evaluate_and_learn(
            run_id="run-mem",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="失败",
            failure_mode="error",
        )
        if report.memory_candidates:
            for mc in report.memory_candidates:
                upd = self.loop.memory_store.get(mc.update_id)
                if upd:
                    from stable_agent.self_improvement.memory_update_candidate import MemoryUpdateStatus
                    assert upd.status != MemoryUpdateStatus.PROMOTED
