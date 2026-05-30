"""proof_loop — 自我优化闭环证明引擎。

实现完整的自我优化闭环：
    Eval result
    ↓
    Failure Attribution
    ↓
    Regression Case
    ↓
    Memory Update Candidate
    ↓
    Skill Patch Candidate
    ↓
    Validation Gate
    ↓
    Human Review
    ↓
    best_skill.md

关键约束：
- 失败经验只能进入 candidate，不能直接 promoted
- Skill patch 不能绕过 validation gate
- best_skill.md 不能绕过 human review
- 不在无失败时强制触发学习
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from stable_agent.self_improvement.memory_update_candidate import (
    MemoryUpdateCandidate,
    MemoryUpdateStatus,
    MemoryUpdateStore,
)
from stable_agent.self_improvement.skill_patch_candidate import (
    SkillPatchCandidate,
    SkillPatchStatus,
    SkillPatchStore,
)
from stable_agent.self_improvement.self_improvement_report import (
    MemoryCandidateEntry,
    RegressionCaseEntry,
    SelfImprovementReport,
    SkillPatchEntry,
)
from stable_agent.self_improvement.regression_validation_runner import (
    RegressionValidationRunner,
)
from stable_agent.self_improvement.validation_report import ValidationReport
from stable_agent.self_improvement.human_review_queue import HumanReviewQueue  # V6.3
from stable_agent.self_improvement.feishu_notifier import FeishuNotifier  # V7.1

logger = logging.getLogger(__name__)


class SelfImprovementProofLoop:
    """自我优化闭环证明引擎。

    协调 Eval → Regression → Memory → SkillPatch → Validation → 
    HumanReview → Export 的完整流程，确保每一步都有明确的闸门控制。

    Attributes:
        memory_store: 记忆更新候选存储。
        patch_store: Skill Patch 候选存储。
        last_report: 最近一次学习报告。
        min_confidence_for_learning: 触发学习的最低置信度阈值。
    """

    def __init__(
        self,
        memory_store: MemoryUpdateStore | None = None,
        patch_store: SkillPatchStore | None = None,
        min_confidence: float = 0.6,
        storage: Any = None,
    ) -> None:
        """初始化自我优化引擎。

        Args:
            memory_store: 记忆更新存储（可选，默认创建新实例）。
            patch_store: Skill Patch 存储（可选，默认创建新实例）。
            min_confidence: 触发学习的最低 eval 置信度阈值。
            storage: V6.2 持久化存储（用于保存回归用例）。
        """
        self.memory_store = memory_store or MemoryUpdateStore()
        self.patch_store = patch_store or SkillPatchStore()
        self.min_confidence = min_confidence
        self.last_report: SelfImprovementReport | None = None
        self._storage = storage  # V6.2: 回归用例持久化

        # V6.1: 真实 Regression Validation Runner
        self._validator: RegressionValidationRunner = RegressionValidationRunner()

        # V6.3: Human Review Queue（真实审核通道）
        self.review_queue: HumanReviewQueue = HumanReviewQueue()

        # V7.1: Feishu Notifier
        self.feishu: FeishuNotifier = FeishuNotifier()

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def evaluate_and_learn(
        self,
        run_id: str,
        eval_passed: bool,
        eval_score: float,
        eval_reason: str = "",
        failure_mode: str = "",
        observations: list[dict] | None = None,
        # V9.0: 测试模式参数
        force_regression_case: bool = False,
        force_skill_patch: bool = False,
    ) -> SelfImprovementReport:
        """评估结果并决定是否触发学习。

        如果 eval_passed=True 或 eval_score >= min_confidence，
        则不触发学习（返回 no_learning 报告）。

        如果 eval 未通过，将执行完整闭环：
        1. 失败归因 → 2. 生成回归用例 → 3. 生成记忆候选
        → 4. 生成 skill patch → 5. 设置验证/审核待处理

        Args:
            run_id: 运行 ID。
            eval_passed: 评估是否通过。
            eval_score: 评估分数（0~1）。
            eval_reason: 评估结果描述。
            failure_mode: 失败模式（如果失败）。
            observations: 观察记录列表（用于归因分析）。

        Returns:
            SelfImprovementReport 实例。
        """
        if observations is None:
            observations = []

        # 不触发学习
        if eval_passed or eval_score >= self.min_confidence:
            report = SelfImprovementReport.create_no_learning(run_id)
            self.last_report = report
            logger.info("Self-improvement: 跳过学习（eval_passed=%s, score=%.2f）",
                        eval_passed, eval_score)
            return report

        # 触发学习闭环
        logger.info("Self-improvement: 触发学习（run=%s, score=%.2f, reason=%s）",
                    run_id, eval_score, eval_reason)

        # 1. 失败归因
        attribution = self._attribute_failure(eval_reason, failure_mode, observations)

        # 2. 生成回归用例
        regression_cases = self._generate_regression_cases(run_id, attribution)

        # V9.0: force_regression_case — 确保至少 1 个回归用例
        if force_regression_case and not regression_cases:
            regression_cases = self._generate_regression_cases(run_id, attribution or f"force test (run={run_id})")

        # V6.2: 回归用例持久化
        if self._storage is not None and regression_cases:
            for rc in regression_cases:
                try:
                    # 动态导入避免硬依赖
                    from stable_agent.saas.repository import RegressionCaseRecord
                    record = RegressionCaseRecord(
                        id=f"reg_{rc.case_id}",
                        task_input=attribution[:200],
                        expected_behavior="",
                        failure_mode=failure_mode,
                        source_run_id=run_id,
                        source_bad_case_id="",
                        tags=["auto_generated", failure_mode],
                        overall_score=eval_score,
                    )
                    self._storage.save_regression_case(record)
                    logger.info("回归用例已持久化: %s", rc.case_id)
                except Exception as e:
                    logger.warning("回归用例持久化失败: %s", e)

        # 3. 生成记忆候选
        memory_entries = self._generate_memory_candidates(run_id, attribution, observations)

        # 4. 生成 skill patch
        # V9.0: force_skill_patch — 即使 failure_mode 为空也生成
        effective_failure_mode = failure_mode or ("forced_test" if force_skill_patch else "")
        patch_entries = self._generate_skill_patches(run_id, attribution, effective_failure_mode)

        # 5. 构建报告
        need_review = len(patch_entries) > 0
        report = SelfImprovementReport.create_from_failure(
            run_id=run_id,
            failure_reason=attribution,
            regression_cases=regression_cases,
            memory_candidates=memory_entries,
            skill_patches=patch_entries,
        )

        # V8.1: validation_passed 默认 False，只有真实验证通过才为 True
        # 旧行为: validation_passed = True（默认通过，不安全）
        validation_passed = False
        validation_reports: list[ValidationReport] = []

        if patch_entries:
            # 对每个 patch 执行真实验证
            for entry in patch_entries:
                patch = self.patch_store.get(entry.patch_id)
                if patch is None:
                    logger.warning("patch %s 不在 store 中，跳过验证", entry.patch_id)
                    continue

                # 获取原始回归用例数据
                case_data = [
                    {"case_id": rc.case_id, "input": rc.description}
                    for rc in regression_cases
                ]

                vr = self._validator.validate_patch(
                    patch=patch,
                    regression_cases=case_data,
                    old_skill=patch.old_rule,
                    candidate_skill=patch.new_rule,
                )
                validation_reports.append(vr)

                if vr.passed:
                    # 验证通过 → 可以进入审核
                    validation_passed = True
                    self.patch_store.submit_for_review(entry.patch_id)
                    # V6.3: 提交到真实 Review Queue
                    patch = self.patch_store.get(entry.patch_id)
                    if patch:
                        review_req = self.review_queue.submit(
                            patch_id=entry.patch_id,
                            run_id=run_id,
                            failure_mode=failure_mode,
                            old_rule=patch.old_rule,
                            new_rule=patch.new_rule,
                            expected_improvement=patch.expected_improvement or "",
                            risk_level=patch.risk_level,
                            validation_report_id=vr.report_id,
                        )
                        logger.info(
                            "ReviewQueue submitted: %s (patch=%s, notification=%d chars)",
                            review_req.review_id, entry.patch_id,
                            len(review_req.to_notification()),
                        )
                    logger.info("patch %s validation passed, → waiting_review", entry.patch_id)
                    # V7.1: 飞书通知
                    if review_req:
                        self.feishu.send_review_notification(
                            patch_id=entry.patch_id,
                            review_id=review_req.review_id,
                            action="submitted",
                            failure_mode=failure_mode,
                            new_rule_preview=patch.new_rule[:100] if patch else "",
                            risk_level=patch.risk_level if patch else "low",
                        )
                else:
                    # 验证失败 → 标记但状态不同
                    validation_passed = False
                    logger.warning(
                        "patch %s validation FAILED: %s (delta=%.2f)",
                        entry.patch_id, vr.reason_zh, vr.delta,
                    )

        # 设置验证和审核状态
        if validation_passed and need_review:
            report.human_review_required = True
            report.human_review_status = "pending"
        else:
            report.human_review_required = False
            report.human_review_status = "none" if not need_review else "validation_failed"

        report.validation_passed = validation_passed
        report.validation_reports = validation_reports

        # V6.2: MemoryCandidate 推进 — 验证通过后自动 validate
        # （promote 仍需 human_review，在外部分支 approve 中触发）
        if validation_passed and memory_entries:
            vr_id = validation_reports[0].report_id if validation_reports else ""
            for mentry in memory_entries:
                try:
                    self.memory_store.validate(mentry.update_id, vr_id)
                    logger.info("MemoryCandidate %s validated (report=%s)", mentry.update_id, vr_id[:12])
                except Exception as e:
                    logger.warning("MemoryCandidate validate 失败: %s", e)

        self.last_report = report
        logger.info("Self-improvement: 学习完成 — 回归=%d, 记忆=%d, patches=%d, validation=%s",
                    len(regression_cases), len(memory_entries), len(patch_entries),
                    "PASSED" if validation_passed else "FAILED")
        return report

    def approve_patch(self, patch_id: str, review_id: str) -> SkillPatchCandidate | None:
        """人工审核通过 skill patch。

        V9.0: 审核通过后 **不再自动导出** best_skill.md。
        需要显式调用 export_approved_patch() 才会写 best_skill.md。

        Args:
            patch_id: 补丁 ID。
            review_id: 审核记录 ID。

        Returns:
            更新后的 SkillPatchCandidate 或 None。
        """
        patch = self.patch_store.get(patch_id)
        if patch is None:
            logger.warning("Self-improvement: patch %s 不存在", patch_id)
            return None

        self.patch_store.approve(patch_id, review_id)
        logger.info("Self-improvement: patch %s 审核通过 (review=%s), ready_to_export=True",
                     patch_id, review_id)

        # V9.0: 审核通过后不再自动导出，需显式调用 export_approved_patch()

        # V7.1: 审核通过后发送飞书通知
        self._notify_feishu(patch_id, review_id, "approved")
        return self.patch_store.get(patch_id)

    def export_approved_patch(self, patch_id: str) -> str:
        """显式导出已审核通过的 skill patch 到 best_skill.md。

        V9.0: 从 approve_patch 中拆分出来，确保导出是显式操作。
        必须在 approve_patch() 之后调用。

        Args:
            patch_id: 补丁 ID。

        Returns:
            导出的 best_skill.md 文件路径。

        Raises:
            ValueError: patch 不存在或状态不是 approved。
        """
        patch = self.patch_store.get(patch_id)
        if patch is None:
            raise ValueError(f"patch {patch_id} 不存在")

        can_export, reason = patch.can_export()
        if not can_export:
            raise ValueError(f"patch {patch_id} 不可导出: {reason}")

        export_path = self._export_best_skill_versioned()
        self.patch_store.mark_exported(patch_id)
        logger.info("Self-improvement: patch %s 已显式导出到 %s", patch_id, export_path)
        return export_path

    def reject_patch(self, patch_id: str, review_id: str, reason: str = "") -> SkillPatchCandidate | None:
        """人工审核拒绝 skill patch。

        Args:
            patch_id: 补丁 ID。
            review_id: 审核记录 ID。
            reason: 拒绝原因。

        Returns:
            更新后的 SkillPatchCandidate 或 None。
        """
        patch = self.patch_store.get(patch_id)
        if patch is None:
            return None

        self.patch_store.reject(patch_id, review_id, reason)
        logger.info("Self-improvement: patch %s 被拒绝 (reason=%s)", patch_id, reason)
        return self.patch_store.get(patch_id)

    def promote_memory(self, update_id: str) -> MemoryUpdateCandidate | None:
        """尝试将记忆候选晋升为长期记忆。

        必须通过 can_promote() 检查。

        Args:
            update_id: 记忆更新 ID。

        Returns:
            晋升后的 MemoryUpdateCandidate 或 None。
        """
        return self.memory_store.promote(update_id)

    def get_report(self) -> SelfImprovementReport | None:
        """获取最近一次学习报告。

        Returns:
            SelfImprovementReport 或 None（尚未执行学习）。
        """
        return self.last_report

    @property
    def has_pending_reviews(self) -> bool:
        """是否有待审核的 patches。"""
        return len(self.patch_store.list_waiting_review()) > 0

    # ------------------------------------------------------------------
    # V6.3: best_skill.md 导出 + Human Review Queue
    # ------------------------------------------------------------------

    def _export_best_skill(self) -> str:
        """收集所有已审核通过的 skill rules，导出为 best_skill.md。

        Returns:
            导出的 best_skill.md 文件路径。
        """
        import os
        import time

        approved_patches = (
            self.patch_store.list_by_status("approved")
            if hasattr(self.patch_store, 'list_by_status')
            else []
        )

        lines = [
            f"<!-- auto-generated by SelfImprovementProofLoop -->",
            f"<!-- exported: {time.strftime('%Y-%m-%d %H:%M:%S')} -->",
            f"# best_skill.md",
            f"",
            f"## Core Rules",
            f"",
        ]

        rule_count = 0
        for i, patch in enumerate(approved_patches, 1):
            if hasattr(patch, 'new_rule') and patch.new_rule:
                lines.append(f"### Rule {i}")
                lines.append(f"")
                lines.append(f"```")
                lines.append(patch.new_rule)
                lines.append(f"```")
                if hasattr(patch, 'expected_improvement') and patch.expected_improvement:
                    lines.append(f"")
                    lines.append(f"*预期效果: {patch.expected_improvement}*")
                lines.append(f"")
                rule_count += 1

        if not approved_patches:
            lines.append("*尚无已审核通过的 skill rules*")
            lines.append("")

        # 写入 skills/ 目录
        skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "skills",
        )
        os.makedirs(skills_dir, exist_ok=True)
        best_path = os.path.join(skills_dir, "best_skill.md")

        with open(best_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("best_skill.md exported: %d rules → %s", rule_count, best_path)
        return best_path

    def _export_best_skill_versioned(self) -> str:
        """V7.1: 导出 best_skill.md 并保留历史版本到 skill_versions/。

        Returns:
            导出的 best_skill.md 路径。
        """
        import os
        import shutil
        import time

        skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "skills",
        )
        versions_dir = os.path.join(skills_dir, "skill_versions")
        os.makedirs(versions_dir, exist_ok=True)

        best_path = os.path.join(skills_dir, "best_skill.md")

        # 如果已有 best_skill.md，先归档
        if os.path.exists(best_path):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            version_name = f"best_skill_{timestamp}.md"
            shutil.copy2(best_path, os.path.join(versions_dir, version_name))
            logger.info("Archived previous best_skill: %s", version_name)

        # 导出新版
        return self._export_best_skill()

    def _notify_feishu(self, patch_id: str, review_id: str, action: str) -> str:
        """V7.1: 飞书通知（真实发送）。

        Args:
            patch_id: Patch ID。
            review_id: Review ID。
            action: "submitted" / "approved" / "rejected"。

        Returns:
            发送结果。
        """
        queue = self.review_queue
        req = queue.get(review_id)
        if req is None:
            return "review not found"

        success = self.feishu.send_review_notification(
            patch_id=patch_id,
            review_id=review_id,
            action=action,
            failure_mode=req.failure_mode,
            new_rule_preview=req.new_rule[:100],
            risk_level=req.risk_level,
        )
        return f"feishu sent: {success}" if success else "feishu skipped (not configured)"

    @property
    def stats(self) -> dict:
        """获取统计信息。"""
        return {
            "memory_candidates": self.memory_store.count,
            "skill_patches": self.patch_store.count,
            "pending_reviews": len(self.patch_store.list_waiting_review()),
            "exportable_patches": self.patch_store.exportable_count,
            "last_triggered": (
                self.last_report.learning_triggered if self.last_report else None
            ),
        }

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _attribute_failure(
        eval_reason: str,
        failure_mode: str,
        observations: list[dict],
    ) -> str:
        """对评估失败进行归因分析。

        Args:
            eval_reason: 评估结果描述。
            failure_mode: 预定义的失败模式。
            observations: 观察记录。

        Returns:
            归因分析文本。
        """
        if failure_mode:
            return f"失败模式: {failure_mode} | 评估: {eval_reason}"

        # 从 observations 中提取失败线索
        obs_texts = [o.get("text", "") for o in observations if o.get("text")]
        if obs_texts:
            combined = "; ".join(obs_texts[:3])
            return f"评估未通过: {eval_reason} | 观察: {combined}"

        return f"评估未通过: {eval_reason}"

    @staticmethod
    def _generate_regression_cases(
        run_id: str,
        attribution: str,
    ) -> list[RegressionCaseEntry]:
        """从失败归因生成回归测试用例。

        Args:
            run_id: 运行 ID。
            attribution: 归因文本。

        Returns:
            回归用例列表。
        """
        case = RegressionCaseEntry(
            case_id=f"reg_{run_id}",
            description=attribution[:80],
            source_run_id=run_id,
            status="new",
        )
        return [case]

    def _generate_memory_candidates(
        self,
        run_id: str,
        attribution: str,
        observations: list[dict],
    ) -> list[MemoryCandidateEntry]:
        """从失败归因生成记忆候选。

        Args:
            run_id: 运行 ID。
            attribution: 归因文本。
            observations: 观察记录。

        Returns:
            记忆候选条目列表。
        """
        # 创建 MemoryUpdateCandidate 存储
        content = (
            f"失败经验 (run={run_id}): {attribution[:200]}"
            if attribution
            else f"未命名失败 (run={run_id})"
        )
        upd = MemoryUpdateCandidate(
            source_run_id=run_id,
            content=content,
            failure_attribution=attribution,
            status=MemoryUpdateStatus.CANDIDATE,
            confidence=0.6,
            tags=["auto_generated", f"run_{run_id}"],
        )
        self.memory_store.add(upd)

        entry = MemoryCandidateEntry(
            update_id=upd.update_id,
            summary=content[:60],
            status="candidate",
        )
        return [entry]

    def _generate_skill_patches(
        self,
        run_id: str,
        attribution: str,
        failure_mode: str,
    ) -> list[SkillPatchEntry]:
        """从失败归因生成 skill patch 候选。

        Args:
            run_id: 运行 ID。
            attribution: 归因文本。
            failure_mode: 失败模式。

        Returns:
            Skill Patch 条目列表。
        """
        if not failure_mode or not attribution:
            return []

        patch = SkillPatchCandidate(
            source_run_id=run_id,
            failure_mode=failure_mode,
            old_rule="无（首次遇到此问题）",
            new_rule=f"避免 {failure_mode}: {attribution[:80]}",
            patch_diff=f"+ 新增规则: {attribution[:60]}",
            expected_improvement=f"防止将来出现类似 {failure_mode} 错误",
            risk_level="medium",
            status=SkillPatchStatus.CANDIDATE,
        )
        self.patch_store.add(patch)

        entry = SkillPatchEntry(
            patch_id=patch.patch_id,
            failure_mode=failure_mode,
            new_rule_summary=patch.new_rule[:60],
            status="candidate",
        )

        # V8.0: 不自动推进状态线。验证由 evaluate_and_learn() 中的
        # RegressionValidationRunner.validate_patch() 驱动，
        # 审核由 HumanReviewQueue 守卫。
        # 旧行为：start_validation → mark_validated → submit_for_review（已移除）

        return [entry]
