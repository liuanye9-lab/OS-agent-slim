"""tests/test_skill_repo.py — SkillRepo 测试。"""

from __future__ import annotations

import json
import os
import shutil
import tempfile

import pytest

from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.schema import (
    RiskLevel,
    SkillMetadata,
    SkillScope,
    SkillStatus,
    SkillTags,
)


@pytest.fixture
def tmp_skills_dir(tmp_path):
    """临时技能目录。"""
    return str(tmp_path / "skills")


@pytest.fixture
def repo(tmp_skills_dir):
    """创建临时 SkillRepo。"""
    return SkillRepo(skills_dir=tmp_skills_dir)


class TestSkillRepoInit:
    """初始化测试。"""

    def test_init_creates_dirs(self, tmp_skills_dir):
        """初始化创建目录和数据库。"""
        repo = SkillRepo(skills_dir=tmp_skills_dir)
        assert os.path.exists(tmp_skills_dir)
        assert os.path.exists(os.path.join(tmp_skills_dir, "skills.sqlite"))
        assert os.path.exists(os.path.join(tmp_skills_dir, "packages"))

    def test_init_idempotent(self, tmp_skills_dir):
        """重复初始化不报错。"""
        repo1 = SkillRepo(skills_dir=tmp_skills_dir)
        repo2 = SkillRepo(skills_dir=tmp_skills_dir)
        assert repo1.db_path == repo2.db_path


class TestSkillRepoCRUD:
    """CRUD 操作测试。"""

    def test_insert_skill(self, repo):
        """插入技能。"""
        m = SkillMetadata(
            name="test-skill",
            description="test description",
        )
        result = repo.insert_skill(m, source_run="run_test", reason="test")
        assert result.skill_id
        assert result.name == "test-skill"
        assert result.version == 1
        assert result.status == SkillStatus.ACTIVE

    def test_get_skill(self, repo):
        """获取技能。"""
        m = SkillMetadata(name="test-skill", description="test")
        inserted = repo.insert_skill(m)
        fetched = repo.get_skill(inserted.skill_id)
        assert fetched is not None
        assert fetched.name == "test-skill"

    def test_get_skill_not_found(self, repo):
        """获取不存在的技能。"""
        assert repo.get_skill("nonexistent") is None

    def test_list_skills(self, repo):
        """列出技能。"""
        repo.insert_skill(SkillMetadata(name="skill-1"))
        repo.insert_skill(SkillMetadata(name="skill-2"))
        skills = repo.list_skills(status="active")
        assert len(skills) == 2

    def test_list_skills_by_status(self, repo):
        """按状态列出技能。"""
        m = SkillMetadata(name="skill-1")
        inserted = repo.insert_skill(m)
        repo.delete_skill(inserted.skill_id)

        active = repo.list_skills(status="active")
        deleted = repo.list_skills(status="deleted")
        assert len(active) == 0
        assert len(deleted) == 1

    def test_update_skill(self, repo):
        """更新技能。"""
        m = SkillMetadata(name="test-skill", description="original")
        inserted = repo.insert_skill(m)

        updated = repo.update_skill(
            inserted.skill_id,
            {"description": "updated", "quality_score": 0.8},
            source_run="run_test",
            reason="test update",
        )
        assert updated is not None
        assert updated.description == "updated"
        assert updated.quality_score == 0.8
        assert updated.version == 2

    def test_update_skill_not_found(self, repo):
        """更新不存在的技能。"""
        result = repo.update_skill("nonexistent", {"description": "test"})
        assert result is None

    def test_delete_skill_soft(self, repo):
        """软删除技能。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        ok = repo.delete_skill(inserted.skill_id)
        assert ok is True

        # 仍然可以获取
        fetched = repo.get_skill(inserted.skill_id)
        assert fetched is not None
        assert fetched.status == SkillStatus.DELETED

    def test_delete_skill_not_found(self, repo):
        """删除不存在的技能。"""
        assert repo.delete_skill("nonexistent") is False

    def test_archive_skill(self, repo):
        """归档技能。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        ok = repo.archive_skill(inserted.skill_id)
        assert ok is True

        fetched = repo.get_skill(inserted.skill_id)
        assert fetched.status == SkillStatus.ARCHIVED


class TestSkillRepoVersion:
    """版本管理测试。"""

    def test_version_created_on_insert(self, repo):
        """插入时创建版本。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        versions = repo.get_versions(inserted.skill_id)
        assert len(versions) == 1
        assert versions[0].version == 1

    def test_version_created_on_update(self, repo):
        """更新时创建版本。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "updated"})
        versions = repo.get_versions(inserted.skill_id)
        assert len(versions) == 2

    def test_rollback(self, repo):
        """回滚技能。"""
        m = SkillMetadata(name="test-skill", description="v1")
        inserted = repo.insert_skill(m)
        repo.update_skill(inserted.skill_id, {"description": "v2"})
        repo.update_skill(inserted.skill_id, {"description": "v3"})

        result = repo.rollback(inserted.skill_id, target_version=1)
        assert result is not None
        assert result.description == "v1"
        assert result.version == 4  # 新版本号

    def test_rollback_not_found(self, repo):
        """回滚不存在的版本。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        result = repo.rollback(inserted.skill_id, target_version=99)
        assert result is None


class TestSkillRepoSearch:
    """搜索测试。"""

    def test_search_by_name(self, repo):
        """按名称搜索。"""
        repo.insert_skill(SkillMetadata(name="avoid-over-editing"))
        results = repo.search_metadata("over-editing")
        assert len(results) > 0
        assert results[0]["name"] == "avoid-over-editing"

    def test_search_by_trigger(self, repo):
        """按触发短语搜索。"""
        m = SkillMetadata(
            name="test-skill",
            trigger_phrases=["不要AI味", "避免模板化"],
        )
        repo.insert_skill(m)
        results = repo.search_metadata("AI味")
        assert len(results) > 0

    def test_search_deleted_not_returned(self, repo):
        """已删除的技能不返回。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        repo.delete_skill(inserted.skill_id)
        results = repo.search_metadata("test-skill")
        assert len(results) == 0


class TestSkillRepoUsage:
    """使用记录测试。"""

    def test_record_usage(self, repo):
        """记录使用。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        record = repo.record_usage(
            run_id="run_test",
            skill_id=inserted.skill_id,
            outcome="success",
            token_cost=100,
        )
        assert record.run_id == "run_test"
        assert record.outcome == "success"

    def test_usage_updates_skill_stats(self, repo):
        """使用记录更新技能统计。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        repo.record_usage("run_1", inserted.skill_id, outcome="success")
        repo.record_usage("run_2", inserted.skill_id, outcome="failure")

        fetched = repo.get_skill(inserted.skill_id)
        assert fetched.usage_count == 2
        assert fetched.success_count == 1
        assert fetched.failure_count == 1


class TestSkillRepoHealth:
    """健康检查测试。"""

    def test_health_check(self, repo):
        """健康检查。"""
        repo.insert_skill(SkillMetadata(name="skill-1"))
        health = repo.health_check()
        assert health["ok"] is True
        assert health["active_skills"] == 1


class TestSkillRepoImportExport:
    """导入导出测试。"""

    def test_export_bundle(self, repo, tmp_path):
        """导出 bundle。"""
        repo.insert_skill(SkillMetadata(name="skill-1"))
        export_path = str(tmp_path / "export.json")
        ok = repo.export_bundle(export_path)
        assert ok is True
        assert os.path.exists(export_path)

    def test_import_bundle(self, repo, tmp_path):
        """导入 bundle。"""
        # 先导出
        repo.insert_skill(SkillMetadata(name="skill-1", skill_id="skill_1"))
        export_path = str(tmp_path / "export.json")
        repo.export_bundle(export_path)

        # 创建新 repo 导入
        repo2 = SkillRepo(skills_dir=str(tmp_path / "skills2"))
        count = repo2.import_bundle(export_path)
        assert count == 1
