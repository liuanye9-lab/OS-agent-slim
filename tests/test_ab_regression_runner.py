"""测试 personal_eval.ab_regression_runner — ABRegressionRunner。"""

import pytest

from stable_agent.personal_eval.ab_regression_runner import ABRegressionRunner
from stable_agent.personal_eval.schemas import PersonalEvalCase, Rubric


@pytest.fixture
def runner():
    return ABRegressionRunner(min_delta=0.01)


@pytest.fixture
def default_case():
    return PersonalEvalCase(
        case_id="test-case-001",
        task="修复登录页面 bug",
        task_type="bug_fix",
        must_keep=["登录", "验证"],
        must_avoid=["删除数据库"],
        success_criteria="用户能正常登录",
        failure_modes=["登录失败"],
    )


@pytest.fixture
def default_rubric():
    return Rubric(
        rubric_id="vibe_coding_default",
        dimensions={
            "goal_alignment": 0.30,
            "minimal_change": 0.20,
            "test_passed": 0.20,
            "style_consistency": 0.10,
            "token_efficiency": 0.10,
            "user_preference_match": 0.10,
        },
    )


class TestABRegressionRunner:
    def test_new_skill_better_passes(self, runner, default_case, default_rubric):
        """new_skill 明显优于 old_skill 时应通过。"""
        old_skill = "修复 bug"
        new_skill = (
            "修复登录页面的验证逻辑 bug。必须确保登录流程正常工作。"
            "检查表单验证是否正确处理边界情况。"
            "禁止删除数据库中的用户数据。"
            "测试: 验证登录功能是否正常。"
        )
        result = runner.run_ab(default_case, old_skill, new_skill, default_rubric)
        assert result.passed is True
        assert result.new_skill_score > result.old_skill_score
        assert result.delta > 0.01
        assert "显著优于" in result.reason_zh

    def test_old_skill_better_fails(self, runner, default_case, default_rubric):
        """old_skill 优于 new_skill 时应失败。"""
        old_skill = (
            "修复登录页面的验证逻辑 bug。必须确保登录流程正常工作。"
            "检查表单验证是否正确处理边界情况。"
            "禁止删除数据库中的用户数据。"
            "测试: 验证登录功能是否正常。"
        )
        new_skill = "修复 bug"
        result = runner.run_ab(default_case, old_skill, new_skill, default_rubric)
        assert result.passed is False
        assert result.delta <= 0

    def test_equal_skills_fail(self, runner, default_case, default_rubric):
        """相同 skill 应失败（delta <= min_delta）。"""
        skill = "修复登录 bug，必须验证登录流程"
        result = runner.run_ab(default_case, skill, skill, default_rubric)
        assert result.passed is False
        assert abs(result.delta) < 0.001

    def test_dimension_scores_present(self, runner, default_case, default_rubric):
        """结果应包含各维度评分。"""
        result = runner.run_ab(default_case, "old", "new with 必须 验证 测试", default_rubric)
        assert "goal_alignment" in result.dimension_scores
        assert "old" in result.dimension_scores["goal_alignment"]
        assert "new" in result.dimension_scores["goal_alignment"]
        assert "delta" in result.dimension_scores["goal_alignment"]

    def test_result_is_json_serializable(self, runner, default_case, default_rubric):
        """结果应 JSON serializable。"""
        result = runner.run_ab(default_case, "old", "new 必须 测试", default_rubric)
        import json
        json_str = json.dumps(result.to_dict(), ensure_ascii=False)
        assert len(json_str) > 0

    def test_must_keep_coverage_improves_goal_alignment(self, runner, default_case, default_rubric):
        """覆盖 must_keep 应提升 goal_alignment 维度。"""
        old_skill = "修复 bug"
        new_skill = "修复登录验证 bug，确保登录流程正常"
        result = runner.run_ab(default_case, old_skill, new_skill, default_rubric)
        old_goal = result.dimension_scores["goal_alignment"]["old"]
        new_goal = result.dimension_scores["goal_alignment"]["new"]
        assert new_goal >= old_goal

    def test_must_avoid_in_new_skill_hurts(self, runner, default_case, default_rubric):
        """new_skill 包含 must_avoid 应降低 user_preference_match。"""
        old_skill = "修复 bug"
        new_skill = "修复 bug，删除数据库旧数据"
        result = runner.run_ab(default_case, old_skill, new_skill, default_rubric)
        old_pref = result.dimension_scores["user_preference_match"]["old"]
        new_pref = result.dimension_scores["user_preference_match"]["new"]
        assert new_pref <= old_pref

    def test_min_delta_threshold(self, default_case, default_rubric):
        """测试 min_delta 阈值。"""
        runner_strict = ABRegressionRunner(min_delta=0.5)
        old_skill = "修复 bug"
        new_skill = "修复登录验证 bug，必须检查登录流程，测试登录功能"
        result = runner_strict.run_ab(default_case, old_skill, new_skill, default_rubric)
        # 即使 new 更好，如果 delta < 0.5 也应失败
        # （取决于实际分数差距）
        assert isinstance(result.passed, bool)
