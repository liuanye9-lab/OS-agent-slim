"""self_improvement_report — 自我优化闭环报告。

每轮自我优化完成后输出结构化报告，Dashboard 必须显示此报告。
包含：是否触发学习、触发原因、失败归因、regression case、
memory candidate、skill patch、验证状态、人工审核状态、导出状态。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from stable_agent.self_improvement.validation_report import ValidationReport


@dataclass
class RegressionCaseEntry:
    """回归用例条目。"""

    case_id: str = ""
    description: str = ""
    source_run_id: str = ""
    status: str = "new"  # new / passing / failing


@dataclass
class MemoryCandidateEntry:
    """记忆候选条目（摘要）。"""

    update_id: str = ""
    summary: str = ""
    status: str = "candidate"


@dataclass
class SkillPatchEntry:
    """Skill Patch 条目（摘要）。"""

    patch_id: str = ""
    failure_mode: str = ""
    new_rule_summary: str = ""
    status: str = "candidate"


@dataclass
class SelfImprovementReport:
    """自我优化闭环报告。

    每轮 Eval → Regression → Memory Candidate → Skill Patch → 
    Validation → Human Review → Export 完整闭环的状态记录。

    Dashboard 必须展示此报告，使用户可以理解 Agent 的自我优化进度。

    Attributes:
        report_id: 报告 ID。
        run_id: 关联的 run ID。
        timestamp: 生成时间戳。
        learning_triggered: 是否触发了学习。
        trigger_reason_zh: 触发原因（中文）。
        failure_attribution_zh: 失败归因说明。
        regression_cases: 生成的回归用例列表。
        memory_candidates: 生成的记忆候选列表。
        skill_patches: 生成的 skill patch 列表。
        validation_passed: 验证是否通过。
        validation_report_id: 验证报告 ID。
        human_review_required: 是否需要人工审核。
        human_review_id: 审核 ID。
        human_review_status: 审核状态。
        best_skill_exported: 是否已导出 best_skill.md。
        summary_zh: 中文摘要。
    """

    report_id: str = field(default_factory=lambda: f"report_{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # 学习触发
    learning_triggered: bool = False
    trigger_reason_zh: str = ""

    # 失败归因
    failure_attribution_zh: str = ""

    # 案例分析
    regression_cases: list[RegressionCaseEntry] = field(default_factory=list)
    memory_candidates: list[MemoryCandidateEntry] = field(default_factory=list)
    skill_patches: list[SkillPatchEntry] = field(default_factory=list)

    # 验证与审核
    validation_passed: bool = False
    validation_report_id: str = ""
    validation_reports: list = field(default_factory=list)  # V6.1: list[ValidationReport]
    human_review_required: bool = False
    human_review_id: str = ""
    human_review_status: str = "pending"  # pending / approved / rejected / validation_failed / none
    best_skill_exported: bool = False

    # 摘要
    summary_zh: str = ""

    def to_dict(self) -> dict:
        """转换为字典格式（供 Dashboard 渲染）。"""
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "learning_triggered": self.learning_triggered,
            "trigger_reason_zh": self.trigger_reason_zh,
            "failure_attribution_zh": self.failure_attribution_zh,
            "regression_cases": [
                {"case_id": c.case_id, "description": c.description, "status": c.status}
                for c in self.regression_cases
            ],
            "memory_candidates": [
                {"update_id": m.update_id, "summary": m.summary, "status": m.status}
                for m in self.memory_candidates
            ],
            "skill_patches": [
                {
                    "patch_id": p.patch_id,
                    "failure_mode": p.failure_mode,
                    "new_rule_summary": p.new_rule_summary,
                    "status": p.status,
                }
                for p in self.skill_patches
            ],
            "validation_passed": self.validation_passed,
            "validation_report_id": self.validation_report_id,
            "validation_reports": [
                {
                    "report_id": vr.report_id,
                    "passed": vr.passed,
                    "old_score": vr.old_score,
                    "new_score": vr.new_score,
                    "delta": vr.delta,
                    "reason_zh": vr.reason_zh,
                }
                for vr in self.validation_reports
            ],
            "human_review_required": self.human_review_required,
            "human_review_id": self.human_review_id,
            "human_review_status": self.human_review_status,
            "best_skill_exported": self.best_skill_exported,
            "summary_zh": self.summary_zh,
        }

    @classmethod
    def create_no_learning(cls, run_id: str) -> "SelfImprovementReport":
        """创建"未触发学习"的报告。

        Args:
            run_id: 关联的运行 ID。

        Returns:
            SelfImprovementReport 实例。
        """
        return cls(
            run_id=run_id,
            learning_triggered=False,
            trigger_reason_zh="本轮评估结果良好，未触发学习",
            summary_zh="未触发学习 — 评估通过，无需优化",
        )

    @classmethod
    def create_from_failure(
        cls,
        run_id: str,
        failure_reason: str,
        regression_cases: list[RegressionCaseEntry],
        memory_candidates: list[MemoryCandidateEntry],
        skill_patches: list[SkillPatchEntry],
    ) -> "SelfImprovementReport":
        """从失败归因创建学习报告。

        Args:
            run_id: 关联的运行 ID。
            failure_reason: 失败原因。
            regression_cases: 回归用例。
            memory_candidates: 记忆候选。
            skill_patches: skill patch。

        Returns:
            SelfImprovementReport 实例。
        """
        patches_need_review = [p for p in skill_patches if p.status in ("validated", "waiting_review")]

        return cls(
            run_id=run_id,
            learning_triggered=True,
            trigger_reason_zh=f"评估未通过: {failure_reason}",
            failure_attribution_zh=failure_reason,
            regression_cases=regression_cases,
            memory_candidates=memory_candidates,
            skill_patches=skill_patches,
            human_review_required=len(patches_need_review) > 0,
            summary_zh=cls._build_failure_summary(
                failure_reason,
                len(regression_cases),
                len(memory_candidates),
                len(skill_patches),
                len(patches_need_review),
            ),
        )

    @staticmethod
    def _build_failure_summary(
        failure_reason: str,
        regression_count: int,
        memory_count: int,
        patch_count: int,
        review_count: int,
    ) -> str:
        """构建失败学习摘要。"""
        return (
            f"触发学习: {failure_reason[:60]} | "
            f"回归用例: {regression_count} | "
            f"记忆候选: {memory_count} | "
            f"Skill Patches: {patch_count} | "
            f"待审核: {review_count}"
        )
