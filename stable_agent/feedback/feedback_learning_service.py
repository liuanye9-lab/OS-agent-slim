"""feedback.feedback_learning_service — V11.2 反馈学习服务。

将三个 feedback 动作真正接入闭环：
  - remember → MemoryUpdateCandidate
  - dont_do_this_again → BadCase → EvalCase → SkillPatchCandidate → Validation → HumanReview
  - correct_and_remember → ExpressionProfileManager (candidate 状态)

所有产物必须真实创建，generated 字段只标记真实产物。
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from stable_agent.capsule import ensure_capsule
from stable_agent.personal_eval.eval_case import EvalCaseManager
from stable_agent.self_improvement.human_review_queue import HumanReviewQueue
from stable_agent.self_improvement.memory_update_candidate import (
    MemoryUpdateCandidate,
    MemoryUpdateStore,
)
from stable_agent.self_improvement.regression_validation_runner import RegressionValidationRunner
from stable_agent.self_improvement.skill_patch_candidate import (
    SkillPatchCandidate,
    SkillPatchStore,
)
from stable_agent.understanding.expression_profile import ExpressionProfileManager

logger = logging.getLogger(__name__)


class FeedbackLearningService:
    """Feedback 三动作闭环服务。

    每个 handler 返回标准化 dict，generated 字段只标记真实产物。
    """

    def __init__(
        self,
        eval_case_manager: EvalCaseManager | None = None,
        skill_patch_store: SkillPatchStore | None = None,
        regression_runner: RegressionValidationRunner | None = None,
        human_review_queue: HumanReviewQueue | None = None,
        memory_store: MemoryUpdateStore | None = None,
        expression_manager: ExpressionProfileManager | None = None,
    ) -> None:
        capsule = ensure_capsule()
        base = str(capsule)
        self.eval_case_manager = eval_case_manager or EvalCaseManager()
        self.skill_patch_store = skill_patch_store or SkillPatchStore()
        self.regression_runner = regression_runner or RegressionValidationRunner()
        self.human_review_queue = human_review_queue or HumanReviewQueue()
        self.memory_store = memory_store or MemoryUpdateStore()
        self.expression_manager = expression_manager or ExpressionProfileManager(
            data_dir=os.path.join(base, "profile"),
        )
        self._bad_cases_path = os.path.join(base, "bad_cases.jsonl")

    # ------------------------------------------------------------------
    # handle_remember
    # ------------------------------------------------------------------

    def handle_remember(
        self,
        run_id: str = "",
        user_note: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """记住：创建 MemoryUpdateCandidate。"""
        errors: list[dict[str, str]] = []
        memory_candidate = None
        try:
            memory_candidate = MemoryUpdateCandidate(
                source_run_id=run_id or "feedback-remember",
                content=user_note or "用户反馈记忆",
                failure_attribution="user_feedback",
                tags=["user_preference", "feedback"],
            )
            self.memory_store.add(memory_candidate)
        except Exception as exc:
            logger.warning("Failed to create memory candidate: %s", exc)
            errors.append({"stage": "memory_candidate", "error": str(exc)})

        return {
            "ok": len(errors) == 0,
            "action": "remember",
            "run_id": run_id,
            "generated": {
                "memory_update_candidate": memory_candidate is not None,
            },
            "ids": {
                "memory_candidate_id": memory_candidate.update_id if memory_candidate else None,
            },
            "summary_zh": "已记录偏好记忆候选。" + (f" ({len(errors)} 个错误)" if errors else ""),
            "errors": errors if errors else None,
        }

    # ------------------------------------------------------------------
    # handle_dont_do_this_again
    # ------------------------------------------------------------------

    def handle_dont_do_this_again(
        self,
        run_id: str = "",
        user_note: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """下次别这样：BadCase → EvalCase → SkillPatch → Validation → (HumanReview)。

        每一步独立 try/except，产物标记只反映真实结果。
        """
        errors: list[dict[str, str]] = []
        ctx = context or {}

        # Step 1: Bad Case
        bad_case_id = None
        try:
            bad_case_id = f"bc_{uuid.uuid4().hex[:12]}"
            bad_record = {
                "bad_case_id": bad_case_id,
                "run_id": run_id,
                "user_note": user_note,
                "task_type": ctx.get("task_type", "general"),
                "action": "dont_do_this_again",
                "context": ctx,
            }
            os.makedirs(os.path.dirname(self._bad_cases_path) or ".", exist_ok=True)
            with open(self._bad_cases_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(bad_record, ensure_ascii=False) + "\n")
            logger.info("Recorded bad case %s", bad_case_id)
        except Exception as exc:
            logger.warning("Failed to record bad case: %s", exc)
            errors.append({"stage": "bad_case", "error": str(exc)})

        # Step 2: Eval Case
        eval_case = None
        try:
            eval_case = self.eval_case_manager.create_case(
                task=user_note or "用户反馈失败案例",
                task_type=ctx.get("task_type", "general"),
                must_keep=ctx.get("must_keep", []),
                must_avoid=ctx.get("must_avoid", [user_note] if user_note else []),
                success_criteria=ctx.get("success_criteria", ""),
                failure_modes=[user_note] if user_note else [],
                source_bad_case_id=bad_case_id or "",
            )
            logger.info("Created eval case %s", eval_case.case_id)
        except Exception as exc:
            logger.warning("Failed to create eval case: %s", exc)
            errors.append({"stage": "eval_case", "error": str(exc)})

        # Step 3: SkillPatchCandidate
        patch_candidate = None
        try:
            patch_candidate = SkillPatchCandidate(
                run_id=run_id or "feedback-dont-do-this",
                trigger="user_feedback:dont_do_this_again",
                task_type=ctx.get("task_type", "general"),
                old_rule=ctx.get("old_rule", ""),
                new_rule=user_note or "用户反馈: 下次别这样",
                summary=user_note or "用户反馈: 下次别这样",
                source_run_ids=[run_id] if run_id else [],
            )
            self.skill_patch_store.save(patch_candidate)
            logger.info("Created skill patch candidate %s", patch_candidate.patch_id)
        except Exception as exc:
            logger.warning("Failed to create skill patch candidate: %s", exc)
            errors.append({"stage": "skill_patch_candidate", "error": str(exc)})

        # Step 4: Validation via RegressionValidationRunner
        validation_report = None
        validation_passed = False
        if patch_candidate is not None:
            try:
                # Convert eval cases to regression_cases format
                regression_cases = []
                for case in self.eval_case_manager.list_cases():
                    regression_cases.append({
                        "case_id": case.case_id,
                        "input": case.task,
                        "expected": case.success_criteria,
                        "must_keep": case.must_keep,
                        "must_avoid": case.must_avoid,
                    })
                # Fallback: if no regression cases from store, create one from user_note
                if not regression_cases and user_note:
                    regression_cases = [{
                        "case_id": "feedback_case",
                        "input": user_note,
                        "expected": "不重复之前的错误",
                    }]

                validation_report = self.regression_runner.validate_patch(
                    patch=patch_candidate,
                    regression_cases=regression_cases,
                    old_skill=patch_candidate.old_rule,
                    candidate_skill=patch_candidate.new_rule,
                )
                validation_passed = validation_report.passed
                logger.info(
                    "Validation %s for patch %s",
                    "passed" if validation_passed else "failed",
                    patch_candidate.patch_id,
                )
            except Exception as exc:
                logger.warning("Validation failed with exception: %s", exc)
                errors.append({"stage": "validation", "error": str(exc)})

        # Step 5: HumanReview (only if validation passed)
        review_id = None
        if validation_passed and patch_candidate is not None:
            try:
                review_request = self.human_review_queue.submit(
                    patch_id=patch_candidate.patch_id,
                    run_id=run_id,
                    failure_mode=user_note[:200] if user_note else "",
                    old_rule=patch_candidate.old_rule,
                    new_rule=patch_candidate.new_rule,
                    expected_improvement=f"避免重复: {user_note}" if user_note else "",
                    risk_level="low",
                    validation_report_id=validation_report.report_id if validation_report else "",
                )
                review_id = review_request.review_id
                logger.info("Submitted review %s", review_id)
            except Exception as exc:
                logger.warning("Failed to submit human review: %s", exc)
                errors.append({"stage": "human_review", "error": str(exc)})

        # Build validation reason
        val_reason_zh = ""
        if validation_report is not None:
            val_reason_zh = validation_report.reason_zh
        elif patch_candidate is None:
            val_reason_zh = "SkillPatchCandidate 未创建，跳过验证。"
        else:
            val_reason_zh = "验证过程异常。"

        return {
            "ok": len(errors) == 0,
            "action": "dont_do_this_again",
            "run_id": run_id,
            "generated": {
                "bad_case": bad_case_id is not None,
                "eval_case": eval_case is not None,
                "skill_patch_candidate": patch_candidate is not None,
                "validation_report": validation_report is not None,
                "human_review_required": review_id is not None,
            },
            "ids": {
                "bad_case_id": bad_case_id,
                "eval_case_id": eval_case.case_id if eval_case else None,
                "patch_id": patch_candidate.patch_id if patch_candidate else None,
                "validation_report_id": validation_report.report_id if validation_report else None,
                "review_id": review_id,
            },
            "validation": {
                "passed": validation_passed,
                "reason_zh": val_reason_zh,
            },
            "summary_zh": _build_dont_do_summary(
                bad_case_id, eval_case, patch_candidate, validation_passed, review_id, errors
            ),
            "errors": errors if errors else None,
        }

    # ------------------------------------------------------------------
    # handle_correct_and_remember
    # ------------------------------------------------------------------

    def handle_correct_and_remember(
        self,
        run_id: str = "",
        user_note: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """纠正并记住：写入 ExpressionProfileManager candidate 规则。

        如果 body 有 phrase / corrected_meaning，优先使用。
        否则 user_note 作为 corrected_meaning，创建 candidate（不直接 confirmed）。
        """
        errors: list[dict[str, str]] = []
        ctx = context or {}
        phrase = ctx.get("phrase", "")
        corrected_meaning = ctx.get("corrected_meaning", "")

        if not phrase and not corrected_meaning:
            corrected_meaning = user_note
            phrase = ctx.get("original_input", user_note[:30] if user_note else "unknown")

        rule_id = None
        try:
            rule_id = self.expression_manager.update_expression_rule(
                phrase=phrase,
                corrected_meaning=corrected_meaning,
                source="user_correction",
            )
            logger.info("Created expression rule candidate %s", rule_id)
        except Exception as exc:
            logger.warning("Failed to update expression rule: %s", exc)
            errors.append({"stage": "expression_rule", "error": str(exc)})

        return {
            "ok": len(errors) == 0,
            "action": "correct_and_remember",
            "run_id": run_id,
            "generated": {
                "expression_profile": rule_id is not None,
                "expression_rule_candidate": rule_id is not None,
            },
            "ids": {
                "expression_rule_id": rule_id,
            },
            "summary_zh": (
                f"已创建表达习惯候选规则 (id={rule_id})，将在下一次 os_agent 语义理解时生效。"
                if rule_id
                else "表达习惯记录失败。"
            ) + (f" ({len(errors)} 个错误)" if errors else ""),
            "errors": errors if errors else None,
        }


def _build_dont_do_summary(
    bad_case_id: str | None,
    eval_case: object | None,
    patch_candidate: object | None,
    validation_passed: bool,
    review_id: str | None,
    errors: list[dict[str, str]],
) -> str:
    """构建 dont_do_this_again 中文摘要。"""
    parts = ["已记录失败案例"]
    if eval_case:
        parts.append("并生成评估用例")
    if patch_candidate:
        parts.append("和 SkillPatchCandidate")
    summary = "".join(parts)

    if validation_passed:
        summary += "，验证通过"
        if review_id:
            summary += "，已提交人工审核。"
        else:
            summary += "，但人工审核提交失败。"
    elif patch_candidate:
        summary += "，但验证未通过，未进入人工审核。"
    else:
        summary += "，但 SkillPatch 未创建，跳过验证。"

    if errors:
        summary += f" ({len(errors)} 个错误)"
    return summary
