"""tests/test_memory_lifecycle.py — 记忆生命周期管理测试。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager


@pytest.fixture
def lifecycle(tmp_path: Path) -> MemoryLifecycleManager:
    """创建临时记忆生命周期管理器。"""
    capsule_path = tmp_path / "test_capsule"
    capsule_path.mkdir(parents=True, exist_ok=True)
    (capsule_path / "memory").mkdir(exist_ok=True)
    return MemoryLifecycleManager(capsule_path=capsule_path)


class TestMemoryLifecycleManager:
    """记忆生命周期管理器测试。"""

    def test_add_candidate(self, lifecycle: MemoryLifecycleManager) -> None:
        """添加候选记忆应成功。"""
        memory = lifecycle.add_candidate(
            content="用户偏好简洁代码风格",
            memory_type="raw_episode",
        )
        assert memory["memory_id"].startswith("mem_")
        assert memory["content"] == "用户偏好简洁代码风格"
        assert memory["memory_type"] == "raw_episode"
        assert memory["confidence"] == 0.5

    def test_add_candidate_with_tags(self, lifecycle: MemoryLifecycleManager) -> None:
        """添加带标签的候选记忆。"""
        memory = lifecycle.add_candidate(
            content="测试内容",
            tags=["coding", "preference"],
        )
        assert memory["tags"] == ["coding", "preference"]

    def test_promote_to_semantic(self, lifecycle: MemoryLifecycleManager) -> None:
        """晋升为 semantic_memory 应成功。"""
        memory = lifecycle.add_candidate(
            content="用户偏好 Python",
            memory_type="raw_episode",
        )
        promoted = lifecycle.promote_to_semantic(memory["memory_id"])
        assert promoted is not None
        assert promoted["memory_type"] == "semantic_memory"
        assert promoted["confirmed_by_user"] is True
        assert promoted["valid_until"] is None  # 长期

    def test_promote_nonexistent_returns_none(
        self, lifecycle: MemoryLifecycleManager
    ) -> None:
        """晋升不存在的记忆应返回 None。"""
        result = lifecycle.promote_to_semantic("nonexistent_id")
        assert result is None

    def test_mark_used(self, lifecycle: MemoryLifecycleManager) -> None:
        """标记使用应增加 reuse_count。"""
        memory = lifecycle.add_candidate(content="test content")
        lifecycle.mark_used(memory["memory_id"])
        lifecycle.mark_used(memory["memory_id"])
        m = lifecycle.get_memory(memory["memory_id"])
        assert m is not None
        assert m["reuse_count"] == 2
        assert m["last_used_at"] is not None

    def test_mark_conflict(self, lifecycle: MemoryLifecycleManager) -> None:
        """标记冲突应增加 conflict_count。"""
        m1 = lifecycle.add_candidate(content="内容 A")
        m2 = lifecycle.add_candidate(content="内容 B")
        lifecycle.mark_conflict(m1["memory_id"], m2["memory_id"])
        updated = lifecycle.get_memory(m1["memory_id"])
        assert updated is not None
        assert updated["conflict_count"] == 1

    def test_supersede(self, lifecycle: MemoryLifecycleManager) -> None:
        """取代旧记忆应成功。"""
        old = lifecycle.add_candidate(content="旧规则")
        new = lifecycle.add_candidate(content="新规则")
        lifecycle.supersede(old["memory_id"], new["memory_id"])
        updated_old = lifecycle.get_memory(old["memory_id"])
        assert updated_old is not None
        assert updated_old["superseded_by"] == new["memory_id"]

    def test_score_memory_value(self, lifecycle: MemoryLifecycleManager) -> None:
        """价值评分应在 0~1 之间。"""
        memory = lifecycle.add_candidate(content="test", confidence=0.8)
        score = lifecycle.score_memory_value(memory)
        assert 0.0 <= score <= 1.0

    def test_score_higher_for_confirmed(self, lifecycle: MemoryLifecycleManager) -> None:
        """用户确认的记忆价值更高。"""
        m1 = lifecycle.add_candidate(content="未确认", confidence=0.5)
        m2 = lifecycle.add_candidate(content="已确认", confidence=0.5)
        m2["confirmed_by_user"] = True
        score1 = lifecycle.score_memory_value(m1)
        score2 = lifecycle.score_memory_value(m2)
        assert score2 > score1

    def test_suggest_prune(self, lifecycle: MemoryLifecycleManager) -> None:
        """修剪建议应返回低价值记忆。"""
        lifecycle.add_candidate(content="低价值记忆", confidence=0.1)
        lifecycle.add_candidate(content="高价值记忆", confidence=0.9)
        prunes = lifecycle.suggest_prune(limit=10)
        assert len(prunes) > 0
        # 最低价值排第一
        assert prunes[0]["value"] <= prunes[-1]["value"]

    def test_suggest_review(self, lifecycle: MemoryLifecycleManager) -> None:
        """审核建议应返回未确认的 semantic_memory。"""
        lifecycle.add_candidate(
            content="重要规则",
            memory_type="semantic_memory",
            confidence=0.8,
        )
        reviews = lifecycle.suggest_review()
        assert len(reviews) > 0

    def test_generate_health_report(self, lifecycle: MemoryLifecycleManager) -> None:
        """健康报告应可生成。"""
        lifecycle.add_candidate(content="test1")
        lifecycle.add_candidate(content="test2", confidence=0.9)
        report = lifecycle.generate_memory_health_report()
        assert "total_memories" in report
        assert "suggest_keep" in report
        assert "suggest_delete" in report
        assert "summary_zh" in report
        assert isinstance(report["summary_zh"], str)

    def test_list_memories(self, lifecycle: MemoryLifecycleManager) -> None:
        """列出记忆应正确过滤。"""
        lifecycle.add_candidate(content="ep1", memory_type="raw_episode")
        lifecycle.add_candidate(content="sem1", memory_type="semantic_memory")
        episodes = lifecycle.list_memories(memory_type="raw_episode")
        assert len(episodes) == 1
        assert episodes[0]["content"] == "ep1"

    def test_delete_memory(self, lifecycle: MemoryLifecycleManager) -> None:
        """删除记忆应成功。"""
        memory = lifecycle.add_candidate(content="to delete")
        assert lifecycle.delete_memory(memory["memory_id"]) is True
        assert lifecycle.get_memory(memory["memory_id"]) is None

    def test_delete_nonexistent(self, lifecycle: MemoryLifecycleManager) -> None:
        """删除不存在的记忆应返回 False。"""
        assert lifecycle.delete_memory("nonexistent") is False

    def test_memory_persistence(self, tmp_path: Path) -> None:
        """记忆应在重启后持久化。"""
        capsule_path = tmp_path / "persist_capsule"
        capsule_path.mkdir(parents=True, exist_ok=True)
        (capsule_path / "memory").mkdir(exist_ok=True)

        # 创建并写入
        mgr1 = MemoryLifecycleManager(capsule_path=capsule_path)
        memory = mgr1.add_candidate(content="持久化测试")

        # 重新加载
        mgr2 = MemoryLifecycleManager(capsule_path=capsule_path)
        loaded = mgr2.get_memory(memory["memory_id"])
        assert loaded is not None
        assert loaded["content"] == "持久化测试"

    def test_count(self, lifecycle: MemoryLifecycleManager) -> None:
        """计数应正确。"""
        assert lifecycle.count == 0
        lifecycle.add_candidate(content="a")
        lifecycle.add_candidate(content="b")
        assert lifecycle.count == 2

    def test_health_report_json_serializable(
        self, lifecycle: MemoryLifecycleManager
    ) -> None:
        """健康报告应可 JSON 序列化。"""
        lifecycle.add_candidate(content="test")
        report = lifecycle.generate_memory_health_report()
        s = json.dumps(report, ensure_ascii=False)
        assert isinstance(s, str)
