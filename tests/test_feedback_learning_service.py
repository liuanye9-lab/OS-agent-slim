"""test_feedback_learning_service.py — FeedbackLearningService 单元测试。

测试三个 handler 的真实产物生成和 generated 字段一致性。
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
from stable_agent.self_improvement.validation_report import ValidationReport
from stable_agent.understanding.expression_profile import ExpressionProfileManager


class PassValidationRunner(RegressionValidationRunner):
    """验证一定通过的 runner。"""

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
    """验证一定失败的 runner。"""

    def validate_patch(self, patch, regression_cases, old_skill="", candidate_skill="", llm_client=None):
        return ValidationReport.from_results(
            run_id=patch.source_run_id or "test",
            patch_id=patch.patch_id,
            old_score=0.8,
            new_score=0.3,
            case_results=[],
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


class TestHandleRemember:
    """remember 动作测试。"""

    def test_creates_memory_candidate(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_remember(run_id="r1", user_note="记住这个")
        assert result["generated"]["memory_update_candidate"] is True
        assert result["ids"]["memory_candidate_id"] is not None

    def test_memory_candidate_persisted(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_remember(run_id="r1", user_note="记住这个")
        mid = result["ids"]["memory_candidate_id"]
        assert service.memory_store.get(mid) is not None

    def test_empty_note_still_creates(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_remember(run_id="r1", user_note="")
        assert result["generated"]["memory_update_candidate"] is True


class TestHandleDontDoThisAgain:
    """dont_do_this_again 动作测试。"""

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

    def test_no_best_skill_md_written(self, tmp_dir):
        service = _make_service(tmp_dir, validation_passes=True)
        service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        for root, dirs, files in os.walk(tmp_dir):
            for f in files:
                assert "best_skill" not in f, f"best_skill file should not exist: {f}"

    def test_generated_matches_real_products(self, tmp_dir):
        """generated 字段必须和真实产物一致。"""
        service = _make_service(tmp_dir, validation_passes=True)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")

        # Verify eval case persisted
        eval_id = result["ids"]["eval_case_id"]
        assert eval_id is not None
        case = service.eval_case_manager.get_case(eval_id)
        assert case is not None

        # Verify patch persisted
        patch_id = result["ids"]["patch_id"]
        assert patch_id is not None
        patch = service.skill_patch_store.get(patch_id)
        assert patch is not None

        # Verify review persisted
        review_id = result["ids"]["review_id"]
        assert review_id is not None
        review = service.human_review_queue.get(review_id)
        assert review is not None

    def test_dry_run_no_best_skill_md(self, tmp_dir):
        """dry_run 验证也不能写 best_skill.md。"""
        service = _make_service(tmp_dir, validation_passes=True)
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad input")
        # validate_patch is called without dry_run, but still no best_skill.md
        for root, dirs, files in os.walk(tmp_dir):
            for f in files:
                assert "best_skill" not in f


class TestHandleCorrectAndRemember:
    """correct_and_remember 动作测试。"""

    def test_with_phrase_and_meaning(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_correct_and_remember(
            run_id="r1",
            user_note="这里的理解有偏差",
            context={"phrase": "搞一下", "corrected_meaning": "帮我创建一个文件"},
        )
        assert result["action"] == "correct_and_remember"
        assert "generated" in result

    def test_with_only_user_note(self, tmp_dir):
        service = _make_service(tmp_dir)
        result = service.handle_correct_and_remember(
            run_id="r1",
            user_note="帮我创建一个文件",
        )
        assert result["action"] == "correct_and_remember"
