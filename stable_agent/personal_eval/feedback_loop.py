"""personal_eval.feedback_loop — 反馈闭环处理器。

V11 新增：FeedbackProcessor 处理三种用户反馈动作：
- remember_this: 生成 memory candidate
- dont_do_this_again: 生成 bad case → eval case → skill patch candidate
- correct_and_remember: 生成 correction record → memory candidate → regression case
"""

from __future__ import annotations

import logging
import time
from typing import Any

from stable_agent.personal_eval.schemas import (
    FeedbackRecord,
    PersonalEvalCase,
)
from stable_agent.personal_eval.eval_case import EvalCaseManager

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """反馈闭环处理器。

    处理用户反馈，生成对应的 memory candidate / bad case / eval case /
    skill patch candidate。

    Attributes:
        eval_case_manager: 评估用例管理器。
        _feedback_records: 反馈记录列表。
    """

    def __init__(self, eval_case_manager: EvalCaseManager | None = None) -> None:
        """初始化反馈处理器。

        Args:
            eval_case_manager: 评估用例管理器（可选，默认创建新实例）。
        """
        self.eval_case_manager: EvalCaseManager = eval_case_manager or EvalCaseManager()
        self._feedback_records: list[FeedbackRecord] = []

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def process_remember_this(
        self,
        run_id: str,
        user_note: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理"记住这个"反馈。

        生成 memory candidate，风险低时标记 confirmed_by_user=True。

        Args:
            run_id: 关联的运行 ID。
            user_note: 用户备注。
            context: 附加上下文。

        Returns:
            包含 memory_candidate 和 feedback_record 的字典。
        """
        if context is None:
            context = {}

        # 生成 memory candidate
        memory_candidate = {
            "content": user_note,
            "type": "user_pref",
            "source": f"feedback_remember_this_{run_id}",
            "confirmed_by_user": True,
            "confidence": 0.85,
            "risk_level": "low",
            "tags": ["user_feedback", "remember_this"],
            "created_at": time.time(),
        }

        # 记录反馈
        record = FeedbackRecord(
            run_id=run_id,
            action="remember_this",
            user_note=user_note,
            target="memory",
        )
        self._feedback_records.append(record)

        logger.info("Feedback remember_this: run=%s, note=%s", run_id, user_note[:50])

        return {
            "status": "ok",
            "action": "remember_this",
            "memory_candidate": memory_candidate,
            "feedback_record": record.to_dict(),
        }

    def process_dont_do_this_again(
        self,
        run_id: str,
        user_note: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理"下次别这样"反馈。

        生成 bad case → 归因 failure_mode → 生成 personal eval case →
        生成 skill patch candidate → 进入 validation。

        Args:
            run_id: 关联的运行 ID。
            user_note: 用户备注。
            context: 附加上下文（可包含 task_type, failure_mode 等）。

        Returns:
            包含 bad_case, eval_case, skill_patch_candidate 的字典。
        """
        if context is None:
            context = {}

        task_type = context.get("task_type", "general")
        failure_mode = context.get("failure_mode", "user_rejection")

        # 1. 生成 bad case
        bad_case = {
            "id": f"bc_feedback_{run_id}",
            "task_type": task_type,
            "input_context": context.get("task_input", ""),
            "output": context.get("model_output", ""),
            "failure_reason": user_note,
            "source_run_id": run_id,
            "tags": ["user_feedback", "dont_do_this_again"],
            "created_at": time.time(),
        }

        # 2. 归因 failure_mode
        attribution = f"用户拒绝: {user_note[:100]}"

        # 3. 生成 personal eval case
        eval_case = self.eval_case_manager.create_case(
            task=context.get("task_input", user_note),
            task_type=task_type,
            must_keep=context.get("must_keep", []),
            must_avoid=[user_note[:50]] if user_note else [],
            success_criteria=f"避免重复: {user_note[:100]}",
            failure_modes=[failure_mode],
            source_bad_case_id=bad_case["id"],
        )

        # 4. 生成 skill patch candidate
        skill_patch_candidate = {
            "patch_id": f"patch_feedback_{run_id}",
            "source_run_id": run_id,
            "failure_mode": failure_mode,
            "old_rule": context.get("current_rule", ""),
            "new_rule": f"避免: {user_note[:100]}",
            "patch_diff": f"+ 新增约束: {user_note[:80]}",
            "expected_improvement": f"防止用户再次遇到: {user_note[:60]}",
            "risk_level": "medium",
            "status": "candidate",
            "created_at": time.time(),
        }

        # 5. 记录反馈
        record = FeedbackRecord(
            run_id=run_id,
            action="dont_do_this_again",
            user_note=user_note,
            target="bad_case",
        )
        self._feedback_records.append(record)

        logger.info(
            "Feedback dont_do_this_again: run=%s, eval_case=%s",
            run_id, eval_case.case_id,
        )

        return {
            "status": "ok",
            "action": "dont_do_this_again",
            "bad_case": bad_case,
            "eval_case": eval_case.to_dict(),
            "skill_patch_candidate": skill_patch_candidate,
            "feedback_record": record.to_dict(),
        }

    def process_correct_and_remember(
        self,
        run_id: str,
        user_note: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理"纠正并记住"反馈。

        生成 correction record → expression rule candidate → memory candidate →
        必要时生成 regression case。

        Args:
            run_id: 关联的运行 ID。
            user_note: 用户备注。
            context: 附加上下文（可包含 original_output, corrected_output 等）。

        Returns:
            包含 correction_record, memory_candidate, eval_case 的字典。
        """
        if context is None:
            context = {}

        # 1. 生成 correction record
        correction_record = {
            "id": f"corr_{run_id}",
            "original_output": context.get("original_output", ""),
            "corrected_output": context.get("corrected_output", user_note),
            "user_note": user_note,
            "source_run_id": run_id,
            "created_at": time.time(),
        }

        # 2. 生成 expression rule candidate
        expression_rule = {
            "rule_text": user_note[:200],
            "source": f"correction_{run_id}",
            "confidence": 0.8,
            "tags": ["user_correction"],
        }

        # 3. 生成 memory candidate
        memory_candidate = {
            "content": f"用户纠正: {user_note[:200]}",
            "type": "correction",
            "source": f"feedback_correct_and_remember_{run_id}",
            "confirmed_by_user": True,
            "confidence": 0.9,
            "risk_level": "low",
            "tags": ["user_feedback", "correct_and_remember"],
            "created_at": time.time(),
        }

        # 4. 必要时生成 regression case
        eval_case = None
        if context.get("create_regression_case", False):
            eval_case = self.eval_case_manager.create_case(
                task=context.get("task_input", user_note),
                task_type=context.get("task_type", "general"),
                must_keep=[user_note[:50]] if user_note else [],
                must_avoid=[],
                success_criteria=f"正确行为: {user_note[:100]}",
                failure_modes=["user_correction"],
                source_bad_case_id=f"corr_{run_id}",
            )

        # 5. 记录反馈
        record = FeedbackRecord(
            run_id=run_id,
            action="correct_and_remember",
            user_note=user_note,
            target="correction",
        )
        self._feedback_records.append(record)

        logger.info("Feedback correct_and_remember: run=%s", run_id)

        result: dict[str, Any] = {
            "status": "ok",
            "action": "correct_and_remember",
            "correction_record": correction_record,
            "expression_rule": expression_rule,
            "memory_candidate": memory_candidate,
            "feedback_record": record.to_dict(),
        }
        if eval_case is not None:
            result["eval_case"] = eval_case.to_dict()

        return result
