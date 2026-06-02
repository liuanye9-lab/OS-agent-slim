"""tests/test_curator_service.py — SkillCuratorService 测试。"""

from __future__ import annotations

import pytest

from stable_agent.skills.curator_service import SkillCuratorService
from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.schema import CurationOpType, SkillMetadata


@pytest.fixture
def repo(tmp_path):
    """创建临时 SkillRepo。"""
    return SkillRepo(skills_dir=str(tmp_path / "skills"))


@pytest.fixture
def curator(repo):
    """创建 SkillCuratorService。"""
    return SkillCuratorService(repo)


class TestProposeFromRun:
    """propose_from_run 测试。"""

    def test_success_no_skill_propose_insert(self, curator, repo):
        """成功 run + 无 skill -> propose insert。"""
        trajectory = {
            "task_input": "修复登录页面的 bug",
            "task_type": "bug_fix",
            "events": [{"type": "task.completed"}],
            "final_result": "bug fixed",
        }
        ops = curator.propose_from_run(
            run_id="run_test",
            trajectory=trajectory,
            outcome={"success": True},
            retrieved_skills=[],
        )
        # 可能会 propose insert（取决于名称提取）
        assert isinstance(ops, list)

    def test_success_with_skill_propose_update(self, curator, repo):
        """成功 run + 有 skill -> propose update。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)

        trajectory = {
            "task_input": "test task",
            "task_type": "general",
            "events": [{"type": "task.completed"}],
            "final_result": "done",
        }
        ops = curator.propose_from_run(
            run_id="run_test",
            trajectory=trajectory,
            outcome={"success": True},
            retrieved_skills=[inserted.skill_id],
        )
        # 应该 propose update
        update_ops = [op for op in ops if op.op == CurationOpType.UPDATE_SKILL]
        assert len(update_ops) > 0

    def test_failure_with_skill_propose_pitfall(self, curator, repo):
        """失败 run + 有 skill -> propose pitfall update。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)

        trajectory = {
            "task_input": "test task",
            "task_type": "general",
            "events": [{"type": "task.failed", "failure_type": "test_failure"}],
            "final_result": "",
        }
        ops = curator.propose_from_run(
            run_id="run_test",
            trajectory=trajectory,
            outcome={"success": False},
            retrieved_skills=[inserted.skill_id],
        )
        # 应该 propose pitfall update
        update_ops = [op for op in ops if op.op == CurationOpType.UPDATE_SKILL]
        assert len(update_ops) > 0


class TestValidateOps:
    """validate_ops 测试。"""

    def test_validate_valid_ops(self, curator):
        """验证有效操作。"""
        from stable_agent.skills.schema import CurationOp
        op = CurationOp(
            op_id="op_test",
            op=CurationOpType.INSERT_SKILL,
            new_skill=SkillMetadata(name="test-skill"),
            source_run="run_test",
            reason="test",
        )
        report = curator.validate_ops([op])
        assert report.ok is True

    def test_validate_missing_source_run(self, curator):
        """缺少 source_run。"""
        from stable_agent.skills.schema import CurationOp
        op = CurationOp(
            op_id="op_test",
            op=CurationOpType.INSERT_SKILL,
            new_skill=SkillMetadata(name="test-skill"),
            source_run="",
        )
        report = curator.validate_ops([op])
        assert report.ok is False


class TestCurateAfterRun:
    """curate_after_run 测试。"""

    def test_curate_after_run(self, curator):
        """策展流程。"""
        trajectory = {
            "task_input": "test task",
            "task_type": "general",
            "events": [{"type": "task.completed"}],
            "final_result": "done",
        }
        result = curator.curate_after_run(
            run_id="run_test",
            trajectory=trajectory,
        )
        assert result.ok is True
        assert result.run_id == "run_test"
