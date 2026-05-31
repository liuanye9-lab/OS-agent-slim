"""test_no_silent_feedback_failures.py — 验证 feedback 路径无静默失败。

测试要求：
1. 模拟 memory 写入失败，API 仍 ok，但 errors 非空。
2. 模拟 eval case 创建失败，generated.eval_case=false。
3. 不允许 generated 标记和真实产物不一致。
"""

from __future__ import annotations

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


class AlwaysPassRunner(RegressionValidationRunner):
    def validate_patch(self, patch, regression_cases, old_skill="", candidate_skill="", llm_client=None):
        return ValidationReport.from_results(
            run_id="test", patch_id=patch.patch_id,
            old_score=0.3, new_score=0.8, case_results=[],
            reason_zh="pass",
        )


class FailingEvalCaseManager(EvalCaseManager):
    """创建 eval case 时抛异常。"""

    def create_case(self, **kwargs):
        raise RuntimeError("EvalCase creation failed (simulated)")


class FailingMemoryStore(MemoryUpdateStore):
    """添加 memory candidate 时抛异常。"""

    def add(self, update):
        raise RuntimeError("Memory store write failed (simulated)")


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestNoSilentFailures:
    """验证 generated 字段与真实产物一致。"""

    def test_eval_case_failure_sets_generated_false(self, tmp_dir):
        """eval case 创建失败时，generated.eval_case 必须是 false。"""
        service = FeedbackLearningService(
            eval_case_manager=FailingEvalCaseManager(
                storage_path=os.path.join(tmp_dir, "evals.jsonl")
            ),
            skill_patch_store=SkillPatchStore(storage_path=os.path.join(tmp_dir, "patches.jsonl")),
            regression_runner=AlwaysPassRunner(),
            human_review_queue=HumanReviewQueue(),
            memory_store=MemoryUpdateStore(),
        )
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad")
        assert result["generated"]["eval_case"] is False
        assert result["ids"]["eval_case_id"] is None
        # Other products should still be created
        assert result["generated"]["bad_case"] is True
        assert result["generated"]["skill_patch_candidate"] is True
        # Errors should be non-empty
        assert result["errors"] is not None
        assert any(e["stage"] == "eval_case" for e in result["errors"])

    def test_memory_failure_sets_generated_false(self, tmp_dir):
        """memory 写入失败时，generated.memory_update_candidate 必须是 false。"""
        service = FeedbackLearningService(
            eval_case_manager=EvalCaseManager(storage_path=os.path.join(tmp_dir, "evals.jsonl")),
            skill_patch_store=SkillPatchStore(storage_path=os.path.join(tmp_dir, "patches.jsonl")),
            regression_runner=AlwaysPassRunner(),
            human_review_queue=HumanReviewQueue(),
            memory_store=FailingMemoryStore(),
        )
        result = service.handle_remember(run_id="r1", user_note="记住这个")
        assert result["generated"]["memory_update_candidate"] is False
        assert result["ids"]["memory_candidate_id"] is None
        assert result["errors"] is not None
        assert any(e["stage"] == "memory_candidate" for e in result["errors"])

    def test_generated_matches_reality_all_pass(self, tmp_dir):
        """所有步骤成功时，generated 全为 true。"""
        service = FeedbackLearningService(
            eval_case_manager=EvalCaseManager(storage_path=os.path.join(tmp_dir, "evals.jsonl")),
            skill_patch_store=SkillPatchStore(storage_path=os.path.join(tmp_dir, "patches.jsonl")),
            regression_runner=AlwaysPassRunner(),
            human_review_queue=HumanReviewQueue(),
            memory_store=MemoryUpdateStore(),
        )
        result = service.handle_dont_do_this_again(run_id="r1", user_note="bad")
        gen = result["generated"]
        assert gen["bad_case"] is True
        assert gen["eval_case"] is True
        assert gen["skill_patch_candidate"] is True
        assert gen["validation_report"] is True
        assert gen["human_review_required"] is True
        assert result["errors"] is None

    def test_no_silent_exception_pass_in_api(self):
        """api.py 不应有 bare except Exception: pass。"""
        api_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "routes", "api.py",
        )
        with open(api_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except Exception:" or stripped == "except Exception: pass":
                # Next line should not be bare pass
                if i < len(lines) and lines[i].strip() == "pass":
                    pytest.fail(
                        f"api.py:{i}: bare 'except Exception: pass' found. "
                        "Must log the error."
                    )

    def test_no_silent_exception_pass_in_runs(self):
        """runs.py 不应有 bare except Exception: pass。"""
        runs_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "routes", "runs.py",
        )
        with open(runs_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except Exception: pass":
                pytest.fail(
                    f"runs.py:{i}: bare 'except Exception: pass' found. "
                    "Must log the error."
                )
