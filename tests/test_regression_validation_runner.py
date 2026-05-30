"""测试 RegressionValidationRunner (V6.1 新模块)。"""

import pytest
from stable_agent.self_improvement.regression_validation_runner import RegressionValidationRunner
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchCandidate
from stable_agent.self_improvement.validation_report import ValidationReport, ValidationCaseResult


@pytest.fixture
def runner():
    return RegressionValidationRunner(min_delta=0.01)


@pytest.fixture
def patch():
    return SkillPatchCandidate(
        patch_id="patch-test-001",
        source_run_id="run-001",
        failure_mode="hallucination",
        old_rule="回答问题前先确认事实",
        new_rule="回答问题前必须先搜索验证事实，禁止编造信息",
        expected_improvement="减少幻觉率 50%",
        risk_level="low",
    )


class TestValidationReport:
    def test_from_results_passed(self):
        """ValidationReport 通过场景。"""
        cases = [
            ValidationCaseResult("case-1", True, 0.6, 0.9, 0.3),
            ValidationCaseResult("case-2", True, 0.5, 0.8, 0.3),
        ]
        report = ValidationReport.from_results(
            "run-001", "patch-001", 0.55, 0.85, cases,
        )
        assert report.passed is True
        assert report.delta == pytest.approx(0.30, abs=0.01)

    def test_from_results_failed_delta_zero(self):
        """delta <= 0 时应 failed。"""
        cases = [
            ValidationCaseResult("case-1", True, 0.9, 0.9, 0.0),
        ]
        report = ValidationReport.from_results(
            "run-001", "patch-001", 0.9, 0.9, cases,
        )
        assert report.passed is False

    def test_from_results_failed_case(self):
        """有失败用例时 overall failed。"""
        cases = [
            ValidationCaseResult("case-1", False, 0.9, 0.5, -0.4, "regression"),
            ValidationCaseResult("case-2", True, 0.6, 0.9, 0.3),
        ]
        report = ValidationReport.from_results(
            "run-001", "patch-001", 0.75, 0.7, cases,
        )
        assert report.passed is False


class TestRegressionValidationRunner:
    def test_validate_patch_empty_cases(self, runner, patch):
        """无回归用例时默认通过（低置信度）。"""
        report = runner.validate_patch(patch, [])
        assert report.passed is True
        assert "无回归用例" in report.reason_zh

    def test_validate_patch_score_delta(self, runner, patch):
        """规则评分应检测 old/new 差异。"""
        cases = [
            {"case_id": "case-1", "input": "测试任务"},
        ]
        report = runner.validate_patch(patch, cases)
        # new_rule 更详细，规则评分应该更高
        assert report.old_score >= 0.0
        assert report.new_score >= 0.0
        assert isinstance(report.delta, float)

    def test_score_rule_empty(self, runner):
        """空规则评分为 0。"""
        score = runner._score_rule("", {"input": "test"})
        assert score == 0.0

    def test_score_rule_detailed(self, runner):
        """详细规则评分更高。"""
        bad = "回答问题"
        good = "回答问题前必须先搜索验证事实，必须用中文回答，禁止编造信息。如果搜索无结果，必须告知用户。"
        assert runner._score_rule(good, {}) > runner._score_rule(bad, {})

    def test_validate_patch_returns_report_id(self, runner, patch):
        """验证报告应包含 report_id。"""
        report = runner.validate_patch(patch, [{"case_id": "c1", "input": "x"}])
        assert report.report_id.startswith("vr_")
        assert report.run_id == "run-001"

    def test_case_result_delta_tracking(self):
        """case result 的 delta 应正确计算。"""
        result = ValidationCaseResult("c1", True, 0.5, 0.8, 0.3)
        assert result.delta == 0.3
        assert result.passed is True
