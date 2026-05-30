"""test_temporal_memory_router — 测试 TemporalMemoryRouter。"""
import time
import pytest
from stable_agent.memory.temporal_memory_router import (
    TemporalMemoryHit,
    TemporalMemoryQuery,
    TemporalMemoryRouter,
)


class TestTemporalMemoryRouter:
    """TemporalMemoryRouter 核心测试。"""

    def setup_method(self):
        self.router = TemporalMemoryRouter()

    def test_add_and_retrieve(self):
        """添加记忆后可检索。"""
        hit = TemporalMemoryHit(
            memory_id="m1",
            content="OS-Agent 使用 Python 3.13",
            created_at=time.time(),
            updated_at=time.time(),
            confidence=0.9,
            source="project_init",
            tags=["project_config"],
        )
        self.router.add(hit)
        query = TemporalMemoryQuery(
            task_input="Python 版本",
            intent_keywords=["Python", "3.13"],
        )
        results = self.router.retrieve(query)
        assert len(results) >= 1

    def test_retrieve_top_k(self):
        """检索应限制 top_k 条。"""
        for i in range(10):
            self.router.add(TemporalMemoryHit(
                memory_id=f"m{i}",
                content=f"记忆 {i}: Python 项目配置",
                created_at=time.time() - i * 3600,
                updated_at=time.time() - i * 3600,
                confidence=0.8,
                source="test",
                tags=["test"],
            ))
        query = TemporalMemoryQuery(
            task_input="Python",
            intent_keywords=["Python"],
            top_k=3,
        )
        results = self.router.retrieve(query)
        assert len(results) <= 3

    def test_expired_memory_filtered(self):
        """过期记忆不应被检索到。"""
        now = time.time()
        hit = TemporalMemoryHit(
            memory_id="expired",
            content="旧配置",
            created_at=now - 3600,
            updated_at=now - 3600,
            valid_until=now - 1,  # 已过期
            confidence=0.9,
            source="test",
        )
        self.router.add(hit)
        query = TemporalMemoryQuery(
            task_input="配置",
            intent_keywords=["配置"],
        )
        results = self.router.retrieve(query)
        assert len(results) == 0

    def test_not_yet_valid_memory_filtered(self):
        """未生效的记忆不应被检索。"""
        hit = TemporalMemoryHit(
            memory_id="future",
            content="未来配置",
            created_at=time.time(),
            updated_at=time.time(),
            valid_from=time.time() + 86400,  # 明天生效
            confidence=0.9,
            source="test",
        )
        self.router.add(hit)
        query = TemporalMemoryQuery(
            task_input="配置",
            intent_keywords=["配置"],
        )
        results = self.router.retrieve(query)
        assert len(results) == 0

    def test_time_window_filter(self):
        """时间窗口过滤应生效。"""
        now = time.time()
        # 旧记忆
        self.router.add(TemporalMemoryHit(
            memory_id="old",
            content="旧配置",
            created_at=now - 10 * 86400,  # 10天前
            updated_at=now - 10 * 86400,
            confidence=0.9,
            source="test",
        ))
        # 新记忆
        self.router.add(TemporalMemoryHit(
            memory_id="new",
            content="新配置",
            created_at=now - 3600,  # 1小时前
            updated_at=now - 3600,
            confidence=0.9,
            source="test",
        ))
        query = TemporalMemoryQuery(
            task_input="配置",
            intent_keywords=["配置"],
            time_window_days=3,
        )
        results = self.router.retrieve(query)
        memory_ids = [h.memory_id for h in results]
        assert "new" in memory_ids
        assert "old" not in memory_ids

    def test_reason_zh_generated(self):
        """检索结果应有 reason_zh。"""
        self.router.add(TemporalMemoryHit(
            memory_id="m1",
            content="Python 项目配置",
            created_at=time.time(),
            updated_at=time.time(),
            confidence=0.9,
            source="project_init",
            tags=["project"],
        ))
        query = TemporalMemoryQuery(
            task_input="Python 项目",
            intent_keywords=["Python", "项目"],
        )
        results = self.router.retrieve(query)
        if results:
            assert results[0].reason_zh, "reason_zh 不应为空"

    def test_conflict_detection(self):
        """冲突检测应发现相似记忆。"""
        h1 = TemporalMemoryHit(
            memory_id="m1",
            content="Python 版本应为 3.13",
            created_at=time.time(),
            updated_at=time.time(),
        )
        self.router.add(h1)
        h2 = TemporalMemoryHit(
            memory_id="m2",
            content="Python 版本应为 3.10 旧版本",
            created_at=time.time(),
            updated_at=time.time(),
        )
        conflicts = self.router.detect_conflicts(h2)
        assert len(conflicts) >= 1
        assert conflicts[0].memory_id == "m1"

    def test_batch_add(self):
        """批量添加应正确。"""
        hits = [
            TemporalMemoryHit(
                memory_id=f"b{i}",
                content=f"批量记忆 {i}",
                created_at=time.time(),
                updated_at=time.time(),
            )
            for i in range(5)
        ]
        self.router.add_batch(hits)
        assert self.router.size == 5

    def test_clear(self):
        """清空后 size 应为 0。"""
        self.router.add(TemporalMemoryHit(
            memory_id="m1",
            content="test",
            created_at=time.time(),
            updated_at=time.time(),
        ))
        assert self.router.size == 1
        self.router.clear()
        assert self.router.size == 0
