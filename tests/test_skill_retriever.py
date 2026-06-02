"""tests/test_skill_retriever.py — SkillRetriever 测试。"""

from __future__ import annotations

import pytest

from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.retriever import SkillRetriever
from stable_agent.skills.schema import SkillMetadata, SkillTags


@pytest.fixture
def repo(tmp_path):
    """创建临时 SkillRepo。"""
    return SkillRepo(skills_dir=str(tmp_path / "skills"))


@pytest.fixture
def retriever(repo):
    """创建 SkillRetriever。"""
    return SkillRetriever(repo)


class TestSkillRetriever:
    """SkillRetriever 测试。"""

    def test_search_empty(self, retriever):
        """空搜索。"""
        results = retriever.search("test")
        assert results == []

    def test_search_by_name(self, retriever, repo):
        """按名称搜索。"""
        repo.insert_skill(SkillMetadata(name="avoid-over-editing"))
        results = retriever.search("over-editing")
        assert len(results) > 0
        assert results[0].name == "avoid-over-editing"

    def test_search_by_trigger(self, retriever, repo):
        """按触发短语搜索。"""
        m = SkillMetadata(
            name="no-ai-flavor",
            trigger_phrases=["不要AI味", "避免模板化"],
        )
        repo.insert_skill(m)
        results = retriever.search("AI味")
        assert len(results) > 0
        assert results[0].name == "no-ai-flavor"

    def test_search_by_description(self, retriever, repo):
        """按描述搜索。"""
        m = SkillMetadata(
            name="test-skill",
            description="当 coding agent 执行代码修改任务时使用",
        )
        repo.insert_skill(m)
        results = retriever.search("coding agent")
        assert len(results) > 0

    def test_search_by_tags(self, retriever, repo):
        """按标签搜索。"""
        m = SkillMetadata(
            name="test-skill",
            tags=SkillTags(topic=["testing", "efficiency"]),
        )
        repo.insert_skill(m)
        results = retriever.search("testing")
        assert len(results) > 0

    def test_search_deleted_not_returned(self, retriever, repo):
        """已删除的技能不返回。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        repo.delete_skill(inserted.skill_id)
        results = retriever.search("test-skill")
        assert len(results) == 0

    def test_search_top_k(self, retriever, repo):
        """top_k 生效。"""
        for i in range(10):
            repo.insert_skill(SkillMetadata(name=f"skill-{i}"))
        results = retriever.search("skill", top_k=3)
        assert len(results) <= 3

    def test_search_returns_reason(self, retriever, repo):
        """返回 reason。"""
        repo.insert_skill(SkillMetadata(name="test-skill"))
        results = retriever.search("test")
        assert len(results) > 0
        assert results[0].reason != ""

    def test_get_skill_full(self, retriever, repo):
        """获取技能完整信息。"""
        m = SkillMetadata(name="test-skill")
        inserted = repo.insert_skill(m)
        result = retriever.get_skill_full(inserted.skill_id)
        assert result is not None
        assert result["name"] == "test-skill"

    def test_get_skill_summary(self, retriever, repo):
        """获取技能摘要。"""
        m = SkillMetadata(
            name="test-skill",
            description="test description",
            trigger_phrases=["test"],
        )
        inserted = repo.insert_skill(m)
        summary = retriever.get_skill_summary(inserted.skill_id)
        assert summary is not None
        assert "test-skill" in summary
