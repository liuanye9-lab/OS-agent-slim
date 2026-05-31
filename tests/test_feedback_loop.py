"""测试 personal_eval.feedback_loop — FeedbackProcessor。

验证以下场景：
- 用户点击"下次别这样"后，能生成 bad case + eval case + skill patch candidate
- remember_this 生成 memory candidate
- correct_and_remember 生成 correction + memory + 可选 regression case
"""

import pytest

from stable_agent.personal_eval.feedback_loop import FeedbackProcessor
from stable_agent.personal_eval.eval_case import EvalCaseManager


@pytest.fixture
def tmp_eval_cases(tmp_path):
    """返回临时 JSONL 路径。"""
    return str(tmp_path / "feedback_eval_cases.jsonl")


@pytest.fixture
def processor(tmp_eval_cases):
    """返回使用临时路径的 FeedbackProcessor。"""
    mgr = EvalCaseManager(storage_path=tmp_eval_cases)
    return FeedbackProcessor(eval_case_manager=mgr)


class TestFeedbackProcessor:
    def test_remember_this(self, processor):
        """remember_this 应生成 memory candidate。"""
        result = processor.process_remember_this(
            run_id="run-001",
            user_note="用户偏好使用 TypeScript",
        )
        assert result["status"] == "ok"
        assert result["action"] == "remember_this"
        assert "memory_candidate" in result
        assert result["memory_candidate"]["confirmed_by_user"] is True
        assert result["memory_candidate"]["type"] == "user_pref"
        assert "feedback_record" in result

    def test_dont_do_this_again_generates_bad_case_and_eval_case(self, processor):
        """dont_do_this_again 应生成 bad case + eval case + skill patch candidate。"""
        result = processor.process_dont_do_this_again(
            run_id="run-002",
            user_note="不要在生产环境直接执行 DELETE 语句",
            context={
                "task_type": "bug_fix",
                "task_input": "清理旧数据",
                "failure_mode": "unsafe_deletion",
            },
        )
        assert result["status"] == "ok"
        assert result["action"] == "dont_do_this_again"

        # 验证 bad case
        assert "bad_case" in result
        assert result["bad_case"]["source_run_id"] == "run-002"
        assert "不要在生产环境直接执行 DELETE 语句" in result["bad_case"]["failure_reason"]

        # 验证 eval case
        assert "eval_case" in result
        assert result["eval_case"]["task_type"] == "bug_fix"
        assert len(result["eval_case"]["must_avoid"]) > 0

        # 验证 skill patch candidate
        assert "skill_patch_candidate" in result
        assert result["skill_patch_candidate"]["status"] == "candidate"
        assert result["skill_patch_candidate"]["source_run_id"] == "run-002"

        # 验证 feedback record
        assert "feedback_record" in result
        assert result["feedback_record"]["action"] == "dont_do_this_again"

    def test_correct_and_remember(self, processor):
        """correct_and_remember 应生成 correction + memory。"""
        result = processor.process_correct_and_remember(
            run_id="run-003",
            user_note="应该使用 left join 而不是 inner join",
            context={
                "original_output": "SELECT * FROM users INNER JOIN orders",
                "corrected_output": "SELECT * FROM users LEFT JOIN orders",
            },
        )
        assert result["status"] == "ok"
        assert result["action"] == "correct_and_remember"

        # 验证 correction record
        assert "correction_record" in result
        assert "LEFT JOIN" in result["correction_record"]["corrected_output"]

        # 验证 memory candidate
        assert "memory_candidate" in result
        assert result["memory_candidate"]["confirmed_by_user"] is True

        # 验证 expression rule
        assert "expression_rule" in result

    def test_correct_and_remember_with_regression_case(self, processor):
        """correct_and_remember 可选生成 regression case。"""
        result = processor.process_correct_and_remember(
            run_id="run-004",
            user_note="错误的 API 调用方式",
            context={
                "create_regression_case": True,
                "task_input": "调用用户 API",
                "task_type": "code_gen",
            },
        )
        assert "eval_case" in result
        assert result["eval_case"]["task_type"] == "code_gen"

    def test_correct_and_remember_without_regression_case(self, processor):
        """correct_and_remember 默认不生成 regression case。"""
        result = processor.process_correct_and_remember(
            run_id="run-005",
            user_note="简单的纠正",
        )
        assert "eval_case" not in result

    def test_feedback_records_accumulate(self, processor):
        """多次反馈应累积记录。"""
        processor.process_remember_this(run_id="r1", user_note="note1")
        processor.process_dont_do_this_again(run_id="r2", user_note="note2")
        processor.process_correct_and_remember(run_id="r3", user_note="note3")
        assert len(processor._feedback_records) == 3

    def test_eval_cases_created_by_dont_do_this_again(self, tmp_eval_cases):
        """dont_do_this_again 创建的 eval case 应被持久化。"""
        mgr = EvalCaseManager(storage_path=tmp_eval_cases)
        proc = FeedbackProcessor(eval_case_manager=mgr)

        proc.process_dont_do_this_again(
            run_id="run-persist",
            user_note="不要这样做",
            context={"task_type": "bug_fix", "task_input": "test task"},
        )

        # 重新加载应能找到
        mgr2 = EvalCaseManager(storage_path=tmp_eval_cases)
        cases = mgr2.list_cases()
        assert len(cases) == 1
        assert cases[0].task_type == "bug_fix"

    def test_all_results_json_serializable(self, processor):
        """所有结果应 JSON serializable。"""
        import json

        r1 = processor.process_remember_this(run_id="r1", user_note="note1")
        r2 = processor.process_dont_do_this_again(run_id="r2", user_note="note2")
        r3 = processor.process_correct_and_remember(run_id="r3", user_note="note3")

        for r in [r1, r2, r3]:
            json.dumps(r, ensure_ascii=False)
