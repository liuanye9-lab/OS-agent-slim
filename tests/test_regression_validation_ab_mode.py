"""测试 regression_validation_ab_mode — A/B 回归与现有验证的集成。

验证以下约束：
- 没有 regression case 时验证失败
- new_skill 没有提升时失败
- new_skill 覆盖 must_keep 且避免 must_avoid 时通过
- dry_run 模式不写长期 best_skill
- validation 失败不进入 human review
- validation 通过后 pending review
"""

import pytest

from stable_agent.self_improvement.regression_validation_runner import RegressionValidationRunner
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchCandidate
from stable_agent.self_improvement.validation_report import ValidationReport
from stable_agent.personal_eval.ab_regression_runner import ABRegressionRunner
from stable_agent.personal_eval.schemas import PersonalEvalCase, Rubric


class TestRegressionValidationABMode:
    """A/B 回归模式与现有验证的集成测试。"""

    def test_no_regression_cases_fails(self):
        """没有回归用例时验证失败。"""
        runner = RegressionValidationRunner(min_delta=0.01)
        patch = SkillPatchCandidate(
            patch_id="patch-001",
            source_run_id="run-001",
            failure_mode="test",
            old_rule="old rule",
            new_rule="new rule",
        )
        report = runner.validate_patch(patch, regression_cases=[])
        assert report.passed is False
        assert "没有回归用例" in report.reason_zh

    def test_new_skill_no_improvement_fails(self):
        """new_skill 没有提升时失败。"""
        runner = RegressionValidationRunner(min_delta=0.01)
        patch = SkillPatchCandidate(
            patch_id="patch-002",
            source_run_id="run-002",
            failure_mode="test",
            old_rule="回答问题前先确认事实",
            new_rule="回答问题前先确认事实",  # 相同内容
        )
        cases = [{"case_id": "c1", "input": "验证事实准确性"}]
        report = runner.validate_patch(patch, cases, old_skill=patch.old_rule, candidate_skill=patch.new_rule)
        assert report.passed is False

    def test_ab_regression_new_better_passes(self):
        """A/B 回归：new_skill 覆盖 must_keep 且避免 must_avoid 时通过。"""
        runner = ABRegressionRunner(min_delta=0.01)
        case = PersonalEvalCase(
            case_id="ab-001",
            task="处理用户登录",
            must_keep=["登录", "验证"],
            must_avoid=["跳过验证"],
        )
        rubric = Rubric()
        old_skill = "处理登录"
        new_skill = (
            "处理用户登录请求。必须验证用户凭据。"
            "检查登录流程的完整性。禁止跳过验证步骤。"
            "测试登录功能。"
        )
        result = runner.run_ab(case, old_skill, new_skill, rubric)
        assert result.passed is True
        assert result.new_skill_score > result.old_skill_score

    def test_dry_run_does_not_write_best_skill(self, tmp_path):
        """dry_run 模式不写长期 best_skill。"""
        from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
        from stable_agent.self_improvement.memory_update_candidate import MemoryUpdateStore
        from stable_agent.self_improvement.skill_patch_candidate import SkillPatchStore

        loop = SelfImprovementProofLoop(
            memory_store=MemoryUpdateStore(),
            patch_store=SkillPatchStore(),
        )

        # dry_run_learning=True 应该阻止 human_review
        report = loop.evaluate_and_learn(
            run_id="dry-run-001",
            eval_passed=False,
            eval_score=0.3,
            eval_reason="测试 dry run",
            failure_mode="test_failure",
            dry_run_learning=True,
        )
        assert report.human_review_required is False
        assert report.human_review_status == "dry_run"

    def test_validation_failed_no_human_review(self):
        """validation 失败不进入 human review。"""
        from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
        from stable_agent.self_improvement.memory_update_candidate import MemoryUpdateStore
        from stable_agent.self_improvement.skill_patch_candidate import SkillPatchStore

        loop = SelfImprovementProofLoop(
            memory_store=MemoryUpdateStore(),
            patch_store=SkillPatchStore(),
        )

        # force_validation_passed=False → 验证失败，不进入 human review
        report = loop.evaluate_and_learn(
            run_id="val-fail-001",
            eval_passed=False,
            eval_score=0.2,
            eval_reason="验证失败测试",
            failure_mode="test_mode",
            force_regression_case=True,
            force_skill_patch=True,
            force_validation_passed=False,
        )
        assert report.validation_passed is False
        assert report.human_review_required is False

    def test_validation_passed_pending_review(self):
        """验证通过后 pending review。"""
        from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
        from stable_agent.self_improvement.memory_update_candidate import MemoryUpdateStore
        from stable_agent.self_improvement.skill_patch_candidate import SkillPatchStore

        loop = SelfImprovementProofLoop(
            memory_store=MemoryUpdateStore(),
            patch_store=SkillPatchStore(),
        )

        # force_validation_passed=True → 强制进入 human review
        report = loop.evaluate_and_learn(
            run_id="val-pass-001",
            eval_passed=False,
            eval_score=0.2,
            eval_reason="验证通过测试",
            failure_mode="test_mode",
            force_regression_case=True,
            force_skill_patch=True,
            force_validation_passed=True,
        )
        assert report.human_review_required is True
        assert report.human_review_status == "pending"
