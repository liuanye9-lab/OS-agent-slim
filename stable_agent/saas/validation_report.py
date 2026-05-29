"""ValidationReport — Skill Patch 验证报告独立模块 (Commercial SaaS P0)。

从 regression_runner 中独立出来，提供 ValidationReport 和 RegressionCaseResult
数据模型，确保 old_score/new_score/delta 可查询，new_score <= old_score 必须不通过。

用法::

    from stable_agent.saas.validation_report import ValidationReport, RegressionCaseResult
    report = ValidationReport(patch_id="sp_xxx", baseline_score=0.5, candidate_score=0.8)
    assert report.passed  # True because 0.8 > 0.5
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegressionCaseResult:
    """单个回归用例的执行结果。

    Attributes:
        case_id: 用例唯一标识。
        passed: 是否通过（候选 Skill 修复了该 BadCase）。
        score: 评分（0.0-1.0）。
        failure_reason: 未通过时的失败描述。
    """

    case_id: str = ""
    passed: bool = False
    score: float = 0.0
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "score": round(self.score, 4),
            "failure_reason": self.failure_reason,
        }


@dataclass
class ValidationReport:
    """Skill Patch 验证报告。

    记录 baseline(旧 Skill) vs candidate(新 Skill) 的评分对比。
    candidate_score > baseline_score 时通过，否则不通过。

    Attributes:
        patch_id: 关联的 Skill Patch ID。
        baseline_score: 旧 Skill 的回归评分。
        candidate_score: 新 Skill 的回归评分。
        delta: 评分变化（candidate - baseline）。
        passed: 是否通过（candidate_score > baseline_score）。
        case_results: 各回归用例的结果列表。
        recommendation: 验证建议（通过/不通过原因）。
        created_at: 验证时间戳。
    """

    patch_id: str = ""
    baseline_score: float = 0.0
    candidate_score: float = 0.0
    delta: float = 0.0
    passed: bool = False
    case_results: list[RegressionCaseResult] = field(default_factory=list)
    failure_summary: str = ""
    recommendation: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """自动计算 delta 和 passed。"""
        self.delta = self.candidate_score - self.baseline_score
        # P0 规则: new_score <= old_score 必须不通过
        self.passed = self.candidate_score > self.baseline_score

    @property
    def run_at(self) -> float:
        """向后兼容：run_at = created_at。"""
        return self.created_at

    @run_at.setter
    def run_at(self, value: float) -> None:
        self.created_at = value

    @property
    def improvement_pct(self) -> float:
        """提升百分比。"""
        if self.baseline_score == 0:
            return 0.0 if self.candidate_score == 0 else 100.0
        return (self.delta / self.baseline_score) * 100

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典，供 API 响应和数据库存储。"""
        return {
            "patch_id": self.patch_id,
            "baseline_score": round(self.baseline_score, 4),
            "candidate_score": round(self.candidate_score, 4),
            "delta": round(self.delta, 4),
            "passed": self.passed,
            "improvement_pct": round(self.improvement_pct, 1),
            "case_results": [c.to_dict() for c in self.case_results],
            "failure_summary": self.failure_summary,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationReport:
        """从字典恢复 ValidationReport。"""
        case_results = []
        for cr in data.get("case_results", []):
            case_results.append(RegressionCaseResult(
                case_id=cr.get("case_id", ""),
                passed=cr.get("passed", False),
                score=cr.get("score", 0.0),
                failure_reason=cr.get("failure_reason", ""),
            ))
        return cls(
            patch_id=data.get("patch_id", ""),
            baseline_score=data.get("baseline_score", 0.0),
            candidate_score=data.get("candidate_score", 0.0),
            delta=data.get("delta", 0.0),
            passed=data.get("passed", False),
            case_results=case_results,
            recommendation=data.get("recommendation", ""),
            created_at=data.get("created_at", time.time()),
        )
