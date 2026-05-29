"""测试 ValidationReport 独立模块 (Phase 9+12)。

验证:
1. ValidationReport.new_score <= old_score 时不通过
2. RegressionCaseResult 正确序列化
3. to_dict/from_dict 往返一致
"""

import pytest
from stable_agent.saas.validation_report import (
    ValidationReport,
    RegressionCaseResult,
)


class TestValidationReportGate:
    """Validation Gate 测试。"""

    def test_gate_blocks_when_no_improvement(self):
        """未提升时 gate 阻断。"""
        # old=0.8, new=0.8 → 未提升 → gate 阻断
        report = ValidationReport(
            patch_id="sp_001",
            baseline_score=0.8,
            candidate_score=0.8,
        )
        assert report.passed is False

    def test_gate_blocks_when_regression(self):
        """退化时 gate 阻断。"""
        # old=0.8, new=0.6 → 退化 → gate 阻断
        report = ValidationReport(
            patch_id="sp_002",
            baseline_score=0.8,
            candidate_score=0.6,
        )
        assert report.passed is False
        assert report.delta < 0

    def test_gate_passes_with_improvement(self):
        """提升时 gate 放行。"""
        report = ValidationReport(
            patch_id="sp_003",
            baseline_score=0.6,
            candidate_score=0.85,
        )
        assert report.passed is True
        assert report.delta > 0

    def test_roundtrip_serialization(self):
        """验证序列化往返一致。"""
        original = ValidationReport(
            patch_id="sp_roundtrip",
            baseline_score=0.55,
            candidate_score=0.78,
            case_results=[
                RegressionCaseResult(case_id="c1", passed=True, score=0.9),
                RegressionCaseResult(
                    case_id="c2", passed=False, score=0.3,
                    failure_reason="输出不完整",
                ),
            ],
            recommendation="建议采用新 Skill",
        )
        data = original.to_dict()
        restored = ValidationReport.from_dict(data)

        assert restored.patch_id == original.patch_id
        assert restored.baseline_score == original.baseline_score
        assert restored.candidate_score == original.candidate_score
        assert restored.delta == original.delta
        assert restored.passed == original.passed
        assert len(restored.case_results) == len(original.case_results)
        assert restored.recommendation == original.recommendation
