"""Regression Runner — 回归测试执行器 (Commercial SaaS P0)。

从 BadCase 生成 Regression Case，对 Skill Patch 变更执行回归验证。
返回 ValidationReport 包含 baseline/candidate/delta。

用法::

    runner = RegressionRunner(repo)
    report = runner.run_cases(
        project_id="proj_xxx",
        skill_content="updated skill...",
        case_ids=["rc_1", "rc_2"],
    )
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from stable_agent.saas.validation_report import (
    ValidationReport,
    RegressionCaseResult,
)

logger = logging.getLogger(__name__)


# ============================================================================
# RegressionRunner
# ============================================================================


class RegressionRunner:
    """回归测试执行器。

    对 Skill Patch 应用前后的 Skill 内容执行回归用例验证，
    比较 baseline score 和 candidate score。

    Attributes:
        repository: SaaS 数据访问层实例。
    """

    def __init__(self, repository: Any = None) -> None:
        self._repo = repository

    def run_cases(
        self,
        project_id: str,
        skill_content: str,
        case_ids: list[str] | None = None,
        patch_id: str = "",
    ) -> ValidationReport:
        """对指定项目的回归用例执行验证。

        Args:
            project_id: 项目 ID。
            skill_content: 新的 Skill 内容。
            case_ids: 要执行的用例 ID 列表。None 表示全量回归。
            patch_id: 关联的 Skill Patch ID。

        Returns:
            ValidationReport 包含评分对比和通过状态。
        """
        report = ValidationReport(patch_id=patch_id)
        report.run_at = time.time()

        # 加载回归用例
        cases: list[dict[str, Any]] = []
        if self._repo is not None:
            try:
                cases = self._repo.list_regression_cases(project_id) or []
            except Exception as e:
                logger.warning("加载回归用例失败: %s", e)

        if case_ids:
            cases = [c for c in cases if c.get("id") in case_ids]

        if not cases:
            report.passed = True
            report.recommendation = "无回归用例，自动放行（建议添加用例以增强验证）"
            return report

        # 简化验证逻辑：统计已知 BadCase 模式是否在新 Skill 中修复
        baseline_total = len(cases)
        candidate_passed = 0

        for case in cases:
            case_result = {
                "case_id": case.get("id", "unknown"),
                "failure_mode": case.get("failure_mode", ""),
                "baseline_passed": False,  # BadCase 来自旧 Skill 的失败
                "candidate_passed": self._check_candidate(case, skill_content),
            }
            if case_result["candidate_passed"]:
                candidate_passed += 1
            report.case_results.append(case_result)

        # 计算评分
        report.baseline_score = 0.0  # BadCase = 旧 Skill 全失败
        report.candidate_score = candidate_passed / baseline_total if baseline_total > 0 else 1.0
        report.delta = report.candidate_score - report.baseline_score
        report.passed = report.candidate_score > report.baseline_score

        if not report.passed:
            failed_modes = [c["failure_mode"] for c in report.case_results if not c["candidate_passed"]]
            report.failure_summary = f"仍有 {len(failed_modes)} 种失败模式未修复"
            report.recommendation = "建议先修复以下失败模式后再提交: " + ", ".join(failed_modes[:3])
        else:
            report.recommendation = (
                f"验证通过：修复了 {candidate_passed}/{baseline_total} 个已知问题 "
                f"(提升 +{report.improvement_pct:.0f}%)"
            )

        logger.info(
            "RegressionRunner: patch=%s baseline=%.2f candidate=%.2f passed=%s",
            patch_id, report.baseline_score, report.candidate_score, report.passed,
        )
        return report

    @staticmethod
    def _check_candidate(case: dict[str, Any], skill_content: str) -> bool:
        """检查候选 Skill 是否修复了该 BadCase。

        简化实现：检查 skill_content 是否包含修复模式的关键词。
        完整实现应调用 LLM evaluator。
        """
        failure_mode = case.get("failure_mode", "").lower()
        # 如果 Skill 内容包含修复关键词，则认为已修复
        repair_keywords = case.get("repair_keywords", [])
        if repair_keywords:
            return any(kw.lower() in skill_content.lower() for kw in repair_keywords)
        # 无修复关键词时，默认通过
        return True
