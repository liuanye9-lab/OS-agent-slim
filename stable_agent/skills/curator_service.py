"""stable_agent.skills.curator_service — SkillCuratorService 技能策展服务。

任务结束后，根据 run trace 自动生成 curation ops。
采用"双阶段"：propose + review/apply。
默认需要人工确认，confidence 足够高且 risk_level=low 时可自动应用。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from stable_agent.skills.judges import ContentJudge, OutcomeJudge
from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.schema import (
    ApplyResult,
    CurationOp,
    CurationOpType,
    CuratorRunResult,
    RiskLevel,
    SkillMetadata,
    SkillScope,
    SkillStatus,
    SkillTags,
    ValidationReport,
    generate_id,
)

logger = logging.getLogger(__name__)


class SkillCuratorService:
    """技能策展服务。

    任务结束后，根据 run trace 自动生成 curation ops。

    Attributes:
        repo: SkillRepo 实例。
        outcome_judge: 结果评判器。
        content_judge: 内容评判器。
    """

    def __init__(
        self,
        repo: SkillRepo,
        outcome_judge: OutcomeJudge | None = None,
        content_judge: ContentJudge | None = None,
    ) -> None:
        """初始化策展服务。

        Args:
            repo: SkillRepo 实例。
            outcome_judge: 结果评判器。
            content_judge: 内容评判器。
        """
        self.repo = repo
        self.outcome_judge = outcome_judge or OutcomeJudge()
        self.content_judge = content_judge or ContentJudge()

    def propose_from_run(
        self,
        run_id: str,
        trajectory: dict[str, Any],
        outcome: dict[str, Any],
        retrieved_skills: list[str] | None = None,
    ) -> list[CurationOp]:
        """从 run 生成候选策展操作。

        规则：
        1. 任务成功 + 无 skill 命中 -> propose insert_skill
        2. 任务成功 + 有 skill 命中 -> propose update_skill
        3. 任务失败 + 有 skill 命中 -> propose update_skill (pitfall)
        4. 某 skill 多次失败 -> propose archive_skill
        5. 两个 skill trigger 高度相似 -> propose merge_skill

        Args:
            run_id: 运行 ID。
            trajectory: 运行轨迹。
            outcome: 运行结果。
            retrieved_skills: 检索到的技能 ID 列表。

        Returns:
            候选策展操作列表。
        """
        retrieved_skills = retrieved_skills or []
        ops: list[CurationOp] = []

        task_input = trajectory.get("task_input", "")
        task_type = trajectory.get("task_type", "general")
        events = trajectory.get("events", [])
        final_result = trajectory.get("final_result", "")

        # 使用 OutcomeJudge 判断结果
        judge_result = self.outcome_judge.judge(
            run_id=run_id,
            task_input=task_input,
            events=events,
            final_result=final_result,
        )

        success = judge_result.success
        confidence = judge_result.confidence

        if success:
            if not retrieved_skills:
                # 规则 1: 成功 + 无 skill -> propose insert
                op = self._propose_insert_from_success(
                    run_id=run_id,
                    task_input=task_input,
                    task_type=task_type,
                    final_result=final_result,
                    confidence=confidence,
                )
                if op:
                    ops.append(op)
            else:
                # 规则 2: 成功 + 有 skill -> propose update
                for skill_id in retrieved_skills:
                    op = self._propose_update_from_success(
                        run_id=run_id,
                        skill_id=skill_id,
                        task_input=task_input,
                        confidence=confidence,
                    )
                    if op:
                        ops.append(op)
        else:
            if retrieved_skills:
                # 规则 3: 失败 + 有 skill -> propose pitfall update
                for skill_id in retrieved_skills:
                    op = self._propose_pitfall_update(
                        run_id=run_id,
                        skill_id=skill_id,
                        task_input=task_input,
                        failure_type=judge_result.failure_type,
                        confidence=confidence,
                    )
                    if op:
                        ops.append(op)

                    # 规则 4: 检查是否多次失败
                    op = self._check_archive_candidate(
                        run_id=run_id,
                        skill_id=skill_id,
                    )
                    if op:
                        ops.append(op)

        return ops

    def validate_ops(self, ops: list[CurationOp]) -> ValidationReport:
        """验证策展操作。

        Args:
            ops: 策展操作列表。

        Returns:
            验证报告。
        """
        issues: list[str] = []
        warnings: list[str] = []

        for op in ops:
            # 检查 source_run
            if not op.source_run:
                issues.append(f"op {op.op_id}: missing source_run")

            # 检查 reason
            if not op.reason:
                warnings.append(f"op {op.op_id}: missing reason")

            # insert 必须有 new_skill
            if op.op == CurationOpType.INSERT_SKILL and not op.new_skill:
                issues.append(f"op {op.op_id}: insert requires new_skill")

            # update 必须有 patch
            if op.op == CurationOpType.UPDATE_SKILL and not op.patch:
                warnings.append(f"op {op.op_id}: update has empty patch")

            # skill name 必须 slug 化
            if op.new_skill and op.new_skill.name:
                if not self._is_slug(op.new_skill.name):
                    issues.append(f"op {op.op_id}: name must be slug format")

        return ValidationReport(
            ok=len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )

    def apply_ops(
        self,
        ops: list[CurationOp],
        auto_apply: bool = False,
    ) -> ApplyResult:
        """应用策展操作。

        Args:
            ops: 策展操作列表。
            auto_apply: 是否自动应用低风险操作。

        Returns:
            应用结果。
        """
        applied: list[str] = []
        rejected: list[str] = []
        errors: list[str] = []

        for op in ops:
            try:
                # 判断是否需要人工审核
                needs_review = op.requires_human_review
                if auto_apply and op.confidence >= 0.8:
                    if op.op == CurationOpType.INSERT_SKILL and op.new_skill:
                        if op.new_skill.risk_level == RiskLevel.LOW:
                            needs_review = False

                if needs_review:
                    rejected.append(op.op_id)
                    logger.info("Op %s requires human review", op.op_id)
                    continue

                # 应用操作
                ok = self._apply_single_op(op)
                if ok:
                    applied.append(op.op_id)
                else:
                    errors.append(f"op {op.op_id}: apply failed")
            except Exception as exc:
                errors.append(f"op {op.op_id}: {exc}")

        return ApplyResult(
            ok=len(errors) == 0,
            applied_ops=applied,
            rejected_ops=rejected,
            errors=errors,
        )

    def curate_after_run(
        self,
        run_id: str,
        trajectory: dict[str, Any] | None = None,
        outcome: dict[str, Any] | None = None,
        retrieved_skills: list[str] | None = None,
        auto_apply: bool = False,
    ) -> CuratorRunResult:
        """任务完成后的策展流程。

        Args:
            run_id: 运行 ID。
            trajectory: 运行轨迹。
            outcome: 运行结果。
            retrieved_skills: 检索到的技能 ID 列表。
            auto_apply: 是否自动应用低风险操作。

        Returns:
            策展运行结果。
        """
        trajectory = trajectory or {}
        outcome = outcome or {}
        retrieved_skills = retrieved_skills or []

        # Step 1: Propose
        proposed_ops = self.propose_from_run(
            run_id=run_id,
            trajectory=trajectory,
            outcome=outcome,
            retrieved_skills=retrieved_skills,
        )

        if not proposed_ops:
            return CuratorRunResult(
                ok=True,
                run_id=run_id,
                proposed_ops=[],
                applied_ops=[],
                rejected_ops=[],
            )

        # Step 2: Validate
        validation = self.validate_ops(proposed_ops)
        if not validation.ok:
            return CuratorRunResult(
                ok=False,
                run_id=run_id,
                proposed_ops=proposed_ops,
                errors=validation.issues,
            )

        # Step 3: Apply
        apply_result = self.apply_ops(proposed_ops, auto_apply=auto_apply)

        return CuratorRunResult(
            ok=apply_result.ok,
            run_id=run_id,
            proposed_ops=proposed_ops,
            applied_ops=apply_result.applied_ops,
            rejected_ops=apply_result.rejected_ops,
            errors=apply_result.errors,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _propose_insert_from_success(
        self,
        run_id: str,
        task_input: str,
        task_type: str,
        final_result: str,
        confidence: float,
    ) -> Optional[CurationOp]:
        """从成功 run 提议 insert skill。"""
        # 提取技能名称
        name = self._extract_skill_name(task_input)
        if not name:
            return None

        # 构建 skill metadata
        metadata = SkillMetadata(
            skill_id=generate_id("skill_"),
            name=name,
            description=f"从成功任务中提取的技能: {task_input[:100]}",
            scope=SkillScope.GLOBAL,
            tags=SkillTags(
                topic=[task_type],
                capabilities=["auto_extracted"],
            ),
            trigger_phrases=self._extract_trigger_phrases(task_input),
            source_runs=[run_id],
            quality_score=confidence,
            risk_level=RiskLevel.LOW,
            created_by="curator",
        )

        return CurationOp(
            op_id=generate_id("op_"),
            op=CurationOpType.INSERT_SKILL,
            skill_id=metadata.skill_id,
            new_skill=metadata,
            reason=f"successful run without matching skill",
            source_run=run_id,
            confidence=confidence,
            requires_human_review=True,
            created_at=time.time(),
        )

    def _propose_update_from_success(
        self,
        run_id: str,
        skill_id: str,
        task_input: str,
        confidence: float,
    ) -> Optional[CurationOp]:
        """从成功 run 提议 update skill。"""
        skill = self.repo.get_skill(skill_id)
        if skill is None:
            return None

        return CurationOp(
            op_id=generate_id("op_"),
            op=CurationOpType.UPDATE_SKILL,
            skill_id=skill_id,
            patch={
                "source_runs": skill.source_runs + [run_id],
                "quality_score": min(1.0, skill.quality_score + 0.1),
            },
            reason="successful run with matching skill",
            source_run=run_id,
            confidence=confidence,
            requires_human_review=False,
            created_at=time.time(),
        )

    def _propose_pitfall_update(
        self,
        run_id: str,
        skill_id: str,
        task_input: str,
        failure_type: str | None,
        confidence: float,
    ) -> Optional[CurationOp]:
        """从失败 run 提议 pitfall update。"""
        skill = self.repo.get_skill(skill_id)
        if skill is None:
            return None

        pitfall = f"failure in run {run_id}"
        if failure_type:
            pitfall = f"{failure_type}: {pitfall}"

        new_pitfalls = skill.tags.pitfalls + [pitfall]

        return CurationOp(
            op_id=generate_id("op_"),
            op=CurationOpType.UPDATE_SKILL,
            skill_id=skill_id,
            patch={
                "tags": {
                    **skill.tags.to_dict(),
                    "pitfalls": new_pitfalls,
                },
                "quality_score": max(0.0, skill.quality_score - 0.1),
            },
            reason=f"failure run with matching skill: {failure_type}",
            source_run=run_id,
            confidence=confidence,
            requires_human_review=True,
            created_at=time.time(),
        )

    def _check_archive_candidate(
        self,
        run_id: str,
        skill_id: str,
    ) -> Optional[CurationOp]:
        """检查是否应该归档技能。"""
        skill = self.repo.get_skill(skill_id)
        if skill is None:
            return None

        # 多次失败建议归档
        if skill.failure_count > skill.success_count * 2 and skill.failure_count >= 3:
            return CurationOp(
                op_id=generate_id("op_"),
                op=CurationOpType.ARCHIVE_SKILL,
                skill_id=skill_id,
                reason=f"multiple failures ({skill.failure_count} failures vs {skill.success_count} successes)",
                source_run=run_id,
                confidence=0.7,
                requires_human_review=True,
                created_at=time.time(),
            )

        return None

    def _apply_single_op(self, op: CurationOp) -> bool:
        """应用单个策展操作。"""
        if op.op == CurationOpType.INSERT_SKILL:
            if op.new_skill:
                self.repo.insert_skill(
                    op.new_skill,
                    source_run=op.source_run,
                    reason=op.reason,
                )
                return True
        elif op.op == CurationOpType.UPDATE_SKILL:
            result = self.repo.update_skill(
                op.skill_id,
                op.patch,
                source_run=op.source_run,
                reason=op.reason,
                requires_human_review=False,
            )
            return result is not None
        elif op.op == CurationOpType.DELETE_SKILL:
            return self.repo.delete_skill(
                op.skill_id,
                source_run=op.source_run,
                reason=op.reason,
            )
        elif op.op == CurationOpType.ARCHIVE_SKILL:
            return self.repo.archive_skill(
                op.skill_id,
                source_run=op.source_run,
                reason=op.reason,
            )
        return False

    def _extract_skill_name(self, task_input: str) -> str:
        """从任务输入提取技能名称。"""
        # 简单策略：取前 50 字符，slug 化
        text = task_input[:50].lower()
        # 移除特殊字符
        import re
        text = re.sub(r'[^\w\s-]', '', text)
        # 替换空格为 -
        text = re.sub(r'\s+', '-', text.strip())
        # 限制长度
        if len(text) > 40:
            text = text[:40]
        return text if text else ""

    def _extract_trigger_phrases(self, task_input: str) -> list[str]:
        """从任务输入提取触发短语。"""
        # 简单策略：提取关键短语
        phrases = []
        keywords = ["不要", "避免", "保持", "确保", "优先", "禁止"]
        for kw in keywords:
            if kw in task_input:
                # 提取关键词附近的内容
                idx = task_input.index(kw)
                segment = task_input[idx:idx + 30]
                phrases.append(segment.strip())
        return phrases[:5]

    def _is_slug(self, name: str) -> bool:
        """检查是否为 slug 格式。"""
        import re
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name))
