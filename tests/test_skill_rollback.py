"""tests/test_skill_rollback.py — SkillRollbackManager 测试。"""

from __future__ import annotations

import pytest

from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.rollback import SkillRollbackManager
from stable_agent.skills.schema import SkillMetadata


@pytest.fixture
def repo(tmp_path):
    """创建临时 SkillRepo。"""
    return SkillRepo(skills_dir=str(tmp_path / "skills"))


@pytest.fixture
def manager(repo):
    """创建 SkillRollbackManager。"""
    return SkillRollbackManager(repo)


class TestRollback:
    """回滚测试。"""

    def test_rollback_to_v1(self, manager, repo):
        """回滚到 v1。"""
        m = SkillMetadata(name="test-skill", description="v1")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "v2"})
        repo.update_skill(inserted.skill_id, {"description": "v3"})

        result = manager.rollback(inserted.skill_id, target_version=1)
        assert result is not None
        assert result.description == "v1"
        assert result.version == 4  # 新版本号

    def test_rollback_generates_event(self, manager, repo):
        """回滚生成事件。"""
        m = SkillMetadata(name="test-skill", description="v1")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "v2"})

        manager.rollback(
            inserted.skill_id,
            target_version=1,
            source_run="run_test",
            reason="test rollback",
        )
        events = repo.get_curation_events(skill_id=inserted.skill_id)
        rollback_events = [e for e in events if "rollback" in e["reason"]]
        assert len(rollback_events) > 0

    def test_rollback_not_found(self, manager, repo):
        """回滚不存在的版本。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        result = manager.rollback(inserted.skill_id, target_version=99)
        assert result is None


class TestVersionHistory:
    """版本历史测试。"""

    def test_get_version_history(self, manager, repo):
        """获取版本历史。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "updated"})

        history = manager.get_version_history(inserted.skill_id)
        assert len(history) == 2

    def test_compare_versions(self, manager, repo):
        """比较版本差异。"""
        m = SkillMetadata(name="test-skill", description="v1")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "v2"})

        diff = manager.compare_versions(inserted.skill_id, 1, 2)
        assert diff["ok"] is True
        assert "description" in diff["diff"]

    def test_get_diff_from_current(self, manager, repo):
        """获取当前版本与目标版本的差异。"""
        m = SkillMetadata(name="test-skill", description="v1")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "v2"})

        diff = manager.get_diff_from_current(inserted.skill_id, 1)
        assert diff["ok"] is True
