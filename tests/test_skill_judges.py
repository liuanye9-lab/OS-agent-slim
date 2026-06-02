"""tests/test_skill_judges.py — OutcomeJudge + ContentJudge 测试。"""

from __future__ import annotations

import pytest

from stable_agent.skills.judges import ContentJudge, OutcomeJudge


class TestOutcomeJudge:
    """OutcomeJudge 测试。"""

    def test_task_completed_success(self):
        """task.completed -> success。"""
        judge = OutcomeJudge()
        result = judge.judge(
            run_id="run_test",
            events=[{"type": "task.completed"}],
        )
        assert result.success is True
        assert result.confidence > 0.5

    def test_task_failed(self):
        """task.failed -> failure。"""
        judge = OutcomeJudge()
        result = judge.judge(
            run_id="run_test",
            events=[{"type": "task.failed", "failure_type": "error"}],
        )
        assert result.success is False
        assert result.failure_type == "error"

    def test_missing_final_result_uncertain(self):
        """缺少 final result -> uncertain。"""
        judge = OutcomeJudge()
        result = judge.judge(
            run_id="run_test",
            events=[],
        )
        assert result.success is False
        assert result.confidence < 0.5

    def test_user_negative_feedback(self):
        """用户负反馈 -> failure。"""
        judge = OutcomeJudge()
        result = judge.judge(
            run_id="run_test",
            events=[{"type": "task.completed"}],
            user_feedback="这个结果是错的",
        )
        assert result.success is False

    def test_tests_passed(self):
        """tests passed -> success with high confidence。"""
        judge = OutcomeJudge()
        result = judge.judge(
            run_id="run_test",
            events=[
                {"type": "task.completed"},
                {"type": "tests.passed"},
            ],
        )
        assert result.success is True
        assert result.confidence > 0.8


class TestContentJudge:
    """ContentJudge 测试。"""

    def test_empty_doc(self):
        """空文档。"""
        judge = ContentJudge()
        result = judge.judge(skill_doc="")
        assert result.valid is False
        assert result.score == 0.0

    def test_dangerous_command(self):
        """危险命令。"""
        judge = ContentJudge()
        result = judge.judge(
            skill_doc="# Test\n\nRun `rm -rf /` to clean up.",
        )
        assert result.valid is False
        assert any("dangerous" in issue for issue in result.issues)

    def test_good_skill(self):
        """好的技能。"""
        judge = ContentJudge()
        doc = """---
name: test-skill
description: Test skill
scope: global
risk_level: low
---

# Skill: Test

## When to use
When testing.

## Procedure
1. Step one.
2. Step two.

## Verification
- Check result.
"""
        result = judge.judge(skill_doc=doc)
        assert result.valid is True
        assert result.score > 0.5

    def test_too_long(self):
        """太长的技能。"""
        judge = ContentJudge()
        doc = "# Test\n\n" + "word " * 2000
        result = judge.judge(skill_doc=doc)
        # 应该有 compression 问题
        assert result.score < 1.0
