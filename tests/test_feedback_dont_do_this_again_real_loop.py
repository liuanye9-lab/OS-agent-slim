"""test_feedback_dont_do_this_again_real_loop.py — 验证 dont-do-this-again 真实闭环 (API 级别)。

测试要求：
1. dont_do_this_again 会真实生成 bad_case。
2. dont_do_this_again 会真实生成 eval_case。
3. dont_do_this_again 会真实生成 skill_patch_candidate。
4. validation_failed 时不会进入 human_review。
5. validation_passed 时进入 human_review，但不导出 best_skill.md。
6. dry_run 或 validation_failed 都不能写 best_skill.md。
7. API 返回 generated 字段必须和真实产物一致。
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from stable_agent.feedback.feedback_learning_service import FeedbackLearningService
from stable_agent.personal_eval.eval_case import EvalCaseManager
from stable_agent.self_improvement.human_review_queue import HumanReviewQueue
from stable_agent.self_improvement.memory_update_candidate import MemoryUpdateStore
from stable_agent.self_improvement.regression_validation_runner import RegressionValidationRunner
from stable_agent.self_improvement.skill_patch_candidate import SkillPatchStore
from stable_agent.self_improvement.validation_report import ValidationReport, ValidationCaseResult


class PassValidationRunner(RegressionValidationRunner):
    def validate_patch(self, patch, regression_cases, old_skill="", candidate_skill="", llm_client=None):
        return ValidationReport.from_results(
            run_id=patch.source_run_id or "test",
            patch_id=patch.patch_id,
            old_score=0.3,
            new_score=0.8,
            case_results=[],
            reason_zh="AB 回归测试通过 (模拟)",
        )


class FailValidationRunner(RegressionValidationRunner):
    def validate_patch(self, patch, regression_cases, old_skill="", candidate_skill="", llm_client=None):
        return ValidationReport.from_results(
            run_id=patch.source_run_id or "test",
            patch_id=patch.patch_id,
            old_score=0.8,
            new_score=0.3,
            case_results=[ValidationCaseResult(
                case_id="test_case",
                passed=False,
                old_score=0.8,
                new_score=0.3,
                delta=-0.5,
                failure_reason="模拟失败",
            )],
            reason_zh="AB 回归测试未通过 (模拟)",
        )


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _make_service(tmp_dir: str, validation_passes: bool = True) -> FeedbackLearningService:
    runner = PassValidationRunner() if validation_passes else FailValidationRunner()
    return FeedbackLearningService(
        eval_case_manager=EvalCaseManager(storage_path=os.path.join(tmp_dir, "evals.jsonl")),
        skill_patch_store=SkillPatchStore(storage_path=os.path.join(tmp_dir, "patches.jsonl")),
        regression_runner=runner,
        human_review_queue=HumanReviewQueue(),
        memory_store=MemoryUpdateStore(),
    )


class TestDontDoThisAgainRealLoop:
    """dont_do_this_again 真实闭环测试。"""

    def test_generates_bad_case(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert result["generated"]["bad_case"] is True
        assert result["ids"]["bad_case_id"] is not None

    def test_generates_eval_case(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert result["generated"]["eval_case"] is True
        assert result["ids"]["eval_case_id"] is not None

    def test_generates_skill_patch_candidate(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert result["generated"]["skill_patch_candidate"] is True
        assert result["ids"]["patch_id"] is not None

    def test_validation_failed_no_human_review(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=False)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert result["generated"]["validation_report"] is True
        assert result["generated"]["human_review_required"] is False
        assert result["validation"]["passed"] is False
        assert result["ids"]["review_id"] is None

    def test_validation_passed_enters_human_review(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=True)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert result["generated"]["validation_report"] is True
        assert result["generated"]["human_review_required"] is True
        assert result["validation"]["passed"] is True
        assert result["ids"]["review_id"] is not None

    def test_no_best_skill_md_written_validation_pass(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=True)
        service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        for root, dirs, files in os.walk(tmp_dir):
            for f in files:
                assert "best_skill" not in f, f"best_skill file should not exist: {f}"

    def test_no_best_skill_md_written_validation_fail(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=False)
        service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        for root, dirs, files in os.walk(tmp_dir):
            for f in files:
                assert "best_skill" not in f, f"best_skill file should not exist: {f}"

    def test_generated_matches_real_products_pass(self, tmp_dir):
        """验证通过时 generated 字段必须和真实产物一致。"""
        service = _make_service(tmp_dir, validation_passes=True)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")

        gen = result["generated"]
        ids = result["ids"]

        # All should be True when validation passes
        assert gen["bad_case"] is True
        assert gen["eval_case"] is True
        assert gen["skill_patch_candidate"] is True
        assert gen["validation_report"] is True
        assert gen["human_review_required"] is True

        # All IDs should be non-None
        assert ids["bad_case_id"] is not None
        assert ids["eval_case_id"] is not None
        assert ids["patch_id"] is not None
        assert ids["validation_report_id"] is not None
        assert ids["review_id"] is not None

    def test_generated_matches_real_products_fail(self, tmp_dir):
        """验证失败时 generated 字段必须和真实产物一致。"""
        service = _make_service(tmp_dir, validation_passes=False)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")

        gen = result["generated"]
        assert gen["bad_case"] is True
        assert gen["eval_case"] is True
        assert gen["skill_patch_candidate"] is True
        assert gen["validation_report"] is True
        assert gen["human_review_required"] is False  # Validation failed

    def test_review_queue_has_pending_item(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=True)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert service.human_review_queue.pending_count == 1

    def test_review_queue_empty_when_validation_fails(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=False)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        assert service.human_review_queue.pending_count == 0
