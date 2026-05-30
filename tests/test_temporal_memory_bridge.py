"""测试 TemporalMemoryBridge + 完整数据流 (V6.1)。

验证从旧 MemoryRouter → TemporalMemoryHit →
TemporalMemoryRouter.retrieve 的完整桥接链路。
"""

import time
import pytest
from stable_agent.memory.temporal_memory_bridge import TemporalMemoryBridge
from stable_agent.memory.temporal_memory_router import TemporalMemoryHit


class TestTemporalMemoryBridge:
    def test_load_empty(self):
        """空输入不崩溃。"""
        bridge = TemporalMemoryBridge()
        hits = bridge.load_for_project()
        assert hits == []

    def test_from_memory_item(self):
        """旧记忆条目 → TemporalMemoryHit。"""
        bridge = TemporalMemoryBridge()
        item = {
            "id": "mem-1",
            "content": "记得测试 ABC",
            "created_at": time.time(),
            "source": "memory_bank",
            "tags": ["test"],
        }
        hit = bridge.from_memory_item(item, project_id="proj-1")
        assert hit is not None
        assert hit.memory_id == "mem-1"
        assert "测试 ABC" in hit.content
        assert hit.project_id == "proj-1"
        assert hit.source == "memory_bank"

    def test_from_memory_item_no_content(self):
        """无 content → None。"""
        bridge = TemporalMemoryBridge()
        assert bridge.from_memory_item({}) is None

    def test_from_bad_case(self):
        """失败案例转换。"""
        bridge = TemporalMemoryBridge()
        case = {
            "id": "bc-1",
            "description": "幻觉输出了错误信息",
            "created_at": time.time(),
            "severity": 0.8,
        }
        hit = bridge.from_bad_case(case, project_id="proj-2")
        assert hit is not None
        assert "[失败案例]" in hit.content
        assert hit.source == "bad_case"
        assert hit.source_quality == 0.8

    def test_from_skill_rule(self):
        """已验证规则转换。"""
        bridge = TemporalMemoryBridge()
        rule = {
            "id": "rule-1",
            "rule": "所有输出必须先经过事实核查",
            "created_at": time.time(),
            "confidence": 0.95,
        }
        hit = bridge.from_skill_rule(rule)
        assert hit is not None
        assert "[已验证规则]" in hit.content
        assert hit.source_quality == 0.9
        assert hit.confidence == 0.95

    def test_project_id_filtering(self):
        """project_id 过滤。"""
        bridge = TemporalMemoryBridge()

        # 加载proj-A记忆
        bridge.load_for_project(project_id="proj-A", existing_memories=[
            {"id": "a-1", "content": "项目A的记忆", "created_at": time.time()},
        ])
        # 加载proj-B记忆
        bridge.load_for_project(project_id="proj-B", existing_memories=[
            {"id": "b-1", "content": "项目B的记忆", "created_at": time.time()},
        ])

        # 最后加载的记忆覆盖了router(clear)，所以只有proj-B
        hits = bridge.retrieve("测试任务", project_id="proj-B")
        # proj-B的记忆应被检索
        for h in hits:
            assert h.project_id == "proj-B" or h.project_id is None

    def test_retrieve_with_keywords(self):
        """关键词检索。"""
        bridge = TemporalMemoryBridge()
        bridge.load_for_project(existing_memories=[
            {"id": "1", "content": "OS-Agent 调试经验", "created_at": time.time()},
            {"id": "2", "content": "网页前端开发", "created_at": time.time()},
        ])
        hits = bridge.retrieve("调试 OS-Agent", intent_keywords=["调试", "OS-Agent"])
        assert len(hits) >= 1
        # 包含"调试"的记忆排前面
        assert "调试" in hits[0].content
