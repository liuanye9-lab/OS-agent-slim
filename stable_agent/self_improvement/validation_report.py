"""ValidationReport — 验证据实报告。

V6.1 Production Hardening:
- 替换 proof_loop 中的硬置 validation_passed=True。
- 必须比较 old_score / new_score / delta。
- new_score <= old_score 时 passed=False。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid


@dataclass
class ValidationCaseResult:
    """单个回归用例的验证结果。"""
    case_id: str
    passed: bool
    old_score: float
    new_score: float
    delta: float
    failure_reason: str = ""


@dataclass
class ValidationReport:
    """验证据实报告。

    不允许直接设 validation_passed=True；
    必须基于 case_results 计算。
    """

    report_id: str
    run_id: str
    patch_id: str | None
    old_score: float
    new_score: float
    delta: float
    passed: bool
    case_results: list[ValidationCaseResult] = field(default_factory=list)
    reason_zh: str = ""
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_results(
        cls,
        run_id: str,
        patch_id: str | None,
        old_score: float,
        new_score: float,
        case_results: list[ValidationCaseResult],
        reason_zh: str = "",
    ) -> ValidationReport:
        """基于真实验证结果构建报告。

        Args:
            run_id: 关联的 run。
            patch_id: 关联的 patch（可选）。
            old_score: 旧规则评分。
            new_score: 新规则评分。
            case_results: 各回归用例结果。
            reason_zh: 验证过程中文说明。

        Returns:
            完整的 ValidationReport，passed 自动计算。
        """
        delta = new_score - old_score
        failed_cases = [c for c in case_results if not c.passed]
        passed = len(failed_cases) == 0 and delta > 0

        if not passed:
            if failed_cases:
                reason_zh = (
                    f"有 {len(failed_cases)} 个回归用例失败"
                    + (f": {failed_cases[0].failure_reason}" if failed_cases else "")
                )
            elif delta <= 0:
                reason_zh = f"新规则未提升评分 (delta={delta:.2f})"

        return cls(
            report_id=f"vr_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            patch_id=patch_id,
            old_score=old_score,
            new_score=new_score,
            delta=delta,
            passed=passed,
            case_results=case_results,
            reason_zh=reason_zh,
        )
