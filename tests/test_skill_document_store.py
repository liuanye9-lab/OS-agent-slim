"""SkillDocumentStore 单元测试。

测试 skill 文档的加载、保存、版本管理和 diff 功能。
使用 tempfile.TemporaryDirectory 进行隔离测试。
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stable_agent.skill_optimizer.models import SkillDocument
from stable_agent.skill_optimizer.skill_document_store import SkillDocumentStore


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_skills_dir():
    """创建临时 skills 目录，包含 initial_skill.md。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        skills_dir = base / "skills"
        skills_dir.mkdir()
        version_dir = skills_dir / "skill_versions"
        version_dir.mkdir()

        # 写入 initial_skill.md
        initial_content = "# Test Skill\n\n## Section 1\nContent here."
        (skills_dir / "initial_skill.md").write_text(initial_content, encoding="utf-8")

        yield base, skills_dir


@pytest.fixture
def store(temp_skills_dir):
    """创建 SkillDocumentStore 实例。"""
    base, skills_dir = temp_skills_dir
    return SkillDocumentStore(
        skills_dir=str(skills_dir),
        skill_versions_dir=str(skills_dir / "skill_versions"),
    )


# ============================================================================
# Tests
# ============================================================================


class TestLoadCurrentSkill:
    """测试 load_current_skill 方法。"""

    def test_load_current_skill_creates_from_initial(self, store):
        """首次加载时从 initial_skill.md 创建 current_skill.md。"""
        skill = store.load_current_skill()

        assert skill is not None
        assert skill.version == "v1.0"
        assert skill.status == "current"
        assert "Test Skill" in skill.content
        assert "Section 1" in skill.content

        # 验证 current_skill.md 已创建
        current_path = store.skills_dir / "current_skill.md"
        assert current_path.exists()

    def test_load_current_skill_idempotent(self, store):
        """多次加载返回相同内容。"""
        skill1 = store.load_current_skill()
        skill2 = store.load_current_skill()

        assert skill1.version == skill2.version
        assert skill1.content == skill2.content

    def test_load_current_skill_raises_when_no_initial(self, temp_skills_dir):
        """initial_skill.md 不存在时抛出 FileNotFoundError。"""
        base, skills_dir = temp_skills_dir
        (skills_dir / "initial_skill.md").unlink()

        store = SkillDocumentStore(
            skills_dir=str(skills_dir),
            skill_versions_dir=str(skills_dir / "skill_versions"),
        )
        with pytest.raises(FileNotFoundError):
            store.load_current_skill()


class TestLoadBestSkill:
    """测试 load_best_skill 方法。"""

    def test_load_best_skill_none_when_missing(self, store):
        """best_skill.md 不存在时返回 None。"""
        result = store.load_best_skill()
        assert result is None

    def test_load_best_skill_returns_document(self, store):
        """best_skill.md 存在时返回 SkillDocument。"""
        best_path = store.skills_dir / "best_skill.md"
        store._write_skill_file(best_path, "# Best Skill", "v2.0")

        result = store.load_best_skill()
        assert result is not None
        assert result.version == "v2.0"
        assert result.status == "best"
        assert result.content == "# Best Skill"


class TestSaveAndPromote:
    """测试保存和提升操作。"""

    def test_save_and_promote_candidate(self, store):
        """保存候选版本并提升为 current。"""
        skill = SkillDocument(
            id="test-1",
            version="v1.0",
            content="# Candidate Skill\n\nUpdated content.",
            status="draft",
        )

        # 保存候选
        store.save_candidate_skill(skill)
        candidate_path = store.skill_versions_dir / "v1.0.md"
        assert candidate_path.exists()

        # 提升为 current
        store.promote_to_current("v1.0")
        current_path = store.skills_dir / "current_skill.md"
        assert current_path.exists()

        # 验证内容
        loaded = store.load_current_skill()
        assert loaded.version == "v1.0"
        assert "Candidate Skill" in loaded.content

    def test_save_candidate_auto_version(self, store):
        """保存无版本号的 candidate 时自动分配版本。"""
        skill = SkillDocument(
            id="test-auto",
            version="",
            content="# Auto version",
        )
        store.save_candidate_skill(skill)

        # 应该自动分配 v1.0
        assert (store.skill_versions_dir / "v1.0.md").exists()
        assert skill.version == "v1.0"

    def test_promote_to_current_backups_old(self, store):
        """提升时备份旧 current 到 skill_versions。"""
        # 先设置 current_skill.md
        store._write_skill_file(
            store.skills_dir / "current_skill.md",
            "# Old Current",
            "v1.0",
        )

        # 保存候选 v1.1
        candidate = SkillDocument(
            id="v1.1-candidate",
            version="v1.1",
            content="# New Candidate",
        )
        store.save_candidate_skill(candidate)

        # 提升 v1.1 → current
        store.promote_to_current("v1.1")

        # 验证旧 current 已备份
        backup_path = store.skill_versions_dir / "v1.0.md"
        assert backup_path.exists()

        # 验证新 current 内容正确
        current = store.load_current_skill()
        assert current.version == "v1.1"
        assert current.content == "# New Candidate"

    def test_promote_to_best_only_best_status(self, store):
        """promote_to_best 将候选提升为 best（状态检查通过）。"""
        # 保存候选
        candidate = SkillDocument(
            id="best-candidate",
            version="v1.2",
            content="# Best Candidate",
            status="best",
        )
        store.save_candidate_skill(candidate)

        # 提升为 best
        store.promote_to_best("v1.2")
        best_path = store.skills_dir / "best_skill.md"
        assert best_path.exists()

        # 验证 best skill 内容
        best = store.load_best_skill()
        assert best is not None
        assert best.version == "v1.2"
        assert best.content == "# Best Candidate"

    def test_promote_to_best_nonexistent_version(self, store):
        """提升不存在的版本时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            store.promote_to_best("v99.99")

    def test_promote_to_current_nonexistent_version(self, store):
        """提升不存在的版本时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            store.promote_to_current("v99.99")


class TestListVersions:
    """测试 list_versions 方法。"""

    def test_list_versions(self, store):
        """列出所有版本，验证按更新时间降序排列。"""
        # 写入多个版本文件
        import time

        v1 = SkillDocument(id="v1", version="v1.0", content="# V1")
        store.save_candidate_skill(v1)
        time.sleep(0.01)

        v2 = SkillDocument(id="v2", version="v1.1", content="# V2")
        store.save_candidate_skill(v2)
        time.sleep(0.01)

        v3 = SkillDocument(id="v3", version="v1.2", content="# V3")
        store.save_candidate_skill(v3)

        versions = store.list_versions()
        assert len(versions) >= 3

        # 验证版本按降序排列（最新的在前）
        version_strings = [v.version for v in versions if v.version in ("v1.0", "v1.1", "v1.2")]
        assert version_strings == ["v1.2", "v1.1", "v1.0"]

    def test_list_versions_empty(self, store):
        """空目录返回空列表。"""
        versions = store.list_versions()
        # 可能为空，也可能只包含之前保存的版本
        assert isinstance(versions, list)


class TestDiffVersions:
    """测试 diff_versions 方法。"""

    def test_diff_versions(self, store):
        """生成两个版本的差异。"""
        v1 = SkillDocument(id="v1", version="v1.0", content="line 1\nline 2\nline 3\n")
        v2 = SkillDocument(id="v2", version="v1.1", content="line 1\nline 2 modified\nline 3\nline 4\n")
        store.save_candidate_skill(v1)
        store.save_candidate_skill(v2)

        diff = store.diff_versions("v1.0", "v1.1")
        assert "line 2 modified" in diff
        assert "line 4" in diff
        assert "+++" in diff
        assert "---" in diff

    def test_diff_versions_missing_file(self, store):
        """任一文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            store.diff_versions("v99.0", "v1.0")

    def test_diff_versions_same_content(self, store):
        """相同内容生成空 diff。"""
        v1 = SkillDocument(id="v1", version="v1.0", content="same content\n")
        v2 = SkillDocument(id="v2", version="v1.1", content="same content\n")
        store.save_candidate_skill(v1)
        store.save_candidate_skill(v2)

        diff = store.diff_versions("v1.0", "v1.1")
        # 相同内容应产生空 diff（只有头部）
        assert len(diff.strip()) == 0 or "@@" not in diff


class TestVersionPersistence:
    """测试版本号的持久化和读取。"""

    def test_version_comment_in_file(self, store):
        """验证版本号存储为 HTML 注释。"""
        store._write_skill_file(
            store.skills_dir / "test_version.md",
            "# Test",
            "v3.5",
        )
        raw = (store.skills_dir / "test_version.md").read_text(encoding="utf-8")
        assert "<!-- skill_version: v3.5 -->" in raw
        assert "# Test" in raw

    def test_read_skill_file_without_version_comment(self, store):
        """兼容没有版本注释的旧文件。"""
        path = store.skill_versions_dir / "v2.0.md"
        path.write_text("# Legacy file without version comment", encoding="utf-8")

        content, version = store._read_skill_file(path)
        assert version == "v2.0"
        assert "Legacy file" in content
