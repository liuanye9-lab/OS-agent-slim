"""测试 RegressionRunner + ValidationReport (Phase 9+12)。

验证:
1. RegressionRunner 生成 ValidationReport
2. new_score <= old_score 时 skill patch 不通过
3. ValidationReport 字段完整
"""

import pytest
from stable_agent.saas.validation_report import (
    ValidationReport,
    RegressionCaseResult,
)
from stable_agent.saas.regression_runner import RegressionRunner


class TestValidationReport:
    """ValidationReport 测试。"""

    def test_report_creation(self):
        """验证报告创建。"""
        report = ValidationReport(
            patch_id="sp_001",
            baseline_score=0.5,
            candidate_score=0.8,
        )
        assert report.patch_id == "sp_001"
        assert report.baseline_score == 0.5
        assert report.candidate_score == 0.8
        assert report.delta == pytest.approx(0.3)
        assert report.passed is True

    def test_new_score_lte_old_score_fails(self):
        """new_score <= old_score 时不通过。"""
        report = ValidationReport(
            patch_id="sp_002",
            baseline_score=0.8,
            candidate_score=0.8,
        )
        assert report.delta == 0.0
        assert report.passed is False

    def test_new_score_lower_fails(self):
        """new_score < old_score 时不通过。"""
        report = ValidationReport(
            patch_id="sp_003",
            baseline_score=0.8,
            candidate_score=0.5,
        )
        assert report.delta == pytest.approx(-0.3)
        assert report.passed is False

    def test_improvement_pct(self):
        """提升百分比计算。"""
        report = ValidationReport(
            baseline_score=0.5,
            candidate_score=0.75,
        )
        assert report.improvement_pct == 50.0

    def test_to_dict(self):
        """验证 to_dict 输出。"""
        report = ValidationReport(
            patch_id="sp_001",
            baseline_score=0.6,
            candidate_score=0.9,
            recommendation="通过",
        )
        d = report.to_dict()
        assert d["patch_id"] == "sp_001"
        assert d["baseline_score"] == 0.6
        assert d["candidate_score"] == 0.9
        assert d["passed"] is True
        assert d["recommendation"] == "通过"

    def test_from_dict(self):
        """验证 from_dict 恢复。"""
        data = {
            "patch_id": "sp_005",
            "baseline_score": 0.4,
            "candidate_score": 0.7,
            "delta": 0.3,
            "passed": True,
            "case_results": [],
            "recommendation": "ok",
        }
        report = ValidationReport.from_dict(data)
        assert report.patch_id == "sp_005"
        assert report.baseline_score == 0.4
        assert report.passed is True

    def test_case_results_included(self):
        """验证 case_results 在 to_dict 中。"""
        report = ValidationReport(
            patch_id="sp_001",
            case_results=[
                RegressionCaseResult(case_id="c1", passed=True, score=0.9),
                RegressionCaseResult(case_id="c2", passed=False, score=0.3, failure_reason="失败"),
            ],
        )
        d = report.to_dict()
        assert len(d["case_results"]) == 2
        assert d["case_results"][0]["passed"] is True
        assert d["case_results"][1]["failure_reason"] == "失败"


class TestRegressionRunner:
    """Regression Runner 测试。"""

    def test_runner_creates_report_no_cases(self):
        """无回归用例时自动放行。"""
        runner = RegressionRunner(repository=None)
        report = runner.run_cases(
            project_id="proj_001",
            skill_content="test skill",
            patch_id="sp_001",
        )
        assert isinstance(report, ValidationReport)
        assert report.passed is True
        assert "无回归用例" in report.recommendation

    def test_runner_baseline_zero(self, tmp_path):
        """baseline 为 0 时 improvement_pct 正确处理。"""
        report = ValidationReport(
            baseline_score=0.0,
            candidate_score=0.5,
        )
        assert report.improvement_pct == 100.0

    def test_delta_calculation(self):
        """delta 计算准确。"""
        report = ValidationReport(
            baseline_score=0.6,
            candidate_score=0.9,
        )
        assert round(report.delta, 4) == 0.3
