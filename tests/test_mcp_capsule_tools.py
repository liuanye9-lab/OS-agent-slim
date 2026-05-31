"""测试 V11 Capsule 和 Memory Lifecycle MCP 工具。

验证 7 个新 MCP 工具的 handler 能正确执行并返回 JSON 可序列化结果。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.gateway.run_context import RunContext


@pytest.fixture
def ctx():
    """创建测试用 RunContext。"""
    return RunContext(run_id="run_test_capsule", trace_id="tr_test")


@pytest.fixture
def registry():
    """创建测试用 UnifiedToolRegistry。"""
    return UnifiedToolRegistry()


@pytest.fixture
def temp_capsule(tmp_path):
    """创建临时胶囊目录。"""
    from stable_agent.capsule.capsule_manager import CapsuleManager
    capsule_path = str(tmp_path / "test-capsule")
    CapsuleManager.create_capsule(capsule_path)
    return capsule_path


class TestCapsuleStatusTool:
    """测试 stableagent.capsule.status。"""

    def test_status_with_existing_capsule(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.capsule.status")
        assert handler is not None
        result = handler(ctx, {"capsule_path": temp_capsule})
        assert result.ok is True
        assert "capsule_id" in result.data
        assert result.data["exists"] is True

    def test_status_with_missing_capsule(self, registry, ctx, tmp_path):
        handler = registry.get_handler("stableagent.capsule.status")
        result = handler(ctx, {"capsule_path": str(tmp_path / "nope")})
        assert result.ok is True
        assert result.data["exists"] is False

    def test_status_json_serializable(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.capsule.status")
        result = handler(ctx, {"capsule_path": temp_capsule})
        # 确保可序列化
        json.dumps(result.data)
        json.dumps({"ok": result.ok, "data": result.data})


class TestCapsuleDoctorTool:
    """测试 stableagent.capsule.doctor。"""

    def test_doctor_healthy(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.capsule.doctor")
        assert handler is not None
        result = handler(ctx, {"capsule_path": temp_capsule})
        assert result.ok is True
        assert "health_score" in result.data
        assert result.data["health_score"] >= 0.5

    def test_doctor_missing_manifest(self, registry, ctx, tmp_path):
        handler = registry.get_handler("stableagent.capsule.doctor")
        result = handler(ctx, {"capsule_path": str(tmp_path / "empty")})
        # 空目录应该有错误
        assert len(result.data.get("errors", [])) > 0


class TestMemoryHealthTool:
    """测试 stableagent.memory.health。"""

    def test_health_empty_memory(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.memory.health")
        assert handler is not None
        result = handler(ctx, {"capsule_path": temp_capsule})
        assert result.ok is True
        assert "total_memories" in result.data
        assert result.data["total_memories"] == 0

    def test_health_with_memories(self, registry, ctx, temp_capsule):
        from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
        mgr = MemoryLifecycleManager(capsule_path=Path(temp_capsule))
        mgr.add_candidate("测试记忆内容", memory_type="raw_episode")
        mgr.add_candidate("高价值偏好", memory_type="semantic_memory", confidence=0.9)

        handler = registry.get_handler("stableagent.memory.health")
        result = handler(ctx, {"capsule_path": temp_capsule})
        assert result.ok is True
        assert result.data["total_memories"] == 2
        assert "summary_zh" in result.data


class TestMemoryReviewTool:
    """测试 stableagent.memory.review。"""

    def test_review_empty(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.memory.review")
        result = handler(ctx, {"capsule_path": temp_capsule})
        assert result.ok is True
        assert result.data["count"] == 0

    def test_review_with_unconfirmed(self, registry, ctx, temp_capsule):
        from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
        mgr = MemoryLifecycleManager(capsule_path=Path(temp_capsule))
        # 添加高价值但未确认的记忆
        mgr.add_candidate("用户偏好", memory_type="semantic_memory", confidence=0.9)

        handler = registry.get_handler("stableagent.memory.review")
        result = handler(ctx, {"capsule_path": temp_capsule})
        assert result.ok is True
        assert result.data["count"] >= 1


class TestMemoryPruneTool:
    """测试 stableagent.memory.prune。"""

    def test_prune_existing(self, registry, ctx, temp_capsule):
        from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
        mgr = MemoryLifecycleManager(capsule_path=Path(temp_capsule))
        mem = mgr.add_candidate("低价值记忆")

        handler = registry.get_handler("stableagent.memory.prune")
        result = handler(ctx, {"memory_ids": [mem["memory_id"]], "capsule_path": temp_capsule})
        assert result.ok is True
        assert result.data["deleted_count"] == 1

    def test_prune_empty_ids(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.memory.prune")
        result = handler(ctx, {"memory_ids": [], "capsule_path": temp_capsule})
        assert result.ok is False


class TestMemoryPromoteTool:
    """测试 stableagent.memory.promote。"""

    def test_promote_existing(self, registry, ctx, temp_capsule):
        from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
        mgr = MemoryLifecycleManager(capsule_path=Path(temp_capsule))
        mem = mgr.add_candidate("待晋升记忆", confidence=0.6)

        handler = registry.get_handler("stableagent.memory.promote")
        result = handler(ctx, {"memory_id": mem["memory_id"], "capsule_path": temp_capsule})
        assert result.ok is True
        assert result.data["new_type"] == "semantic_memory"

    def test_promote_nonexistent(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.memory.promote")
        assert handler is not None
        result = handler(ctx, {"memory_id": "mem_nonexist", "capsule_path": temp_capsule})
        assert result.ok is False


class TestMemoryDeleteTool:
    """测试 stableagent.memory.delete。"""

    def test_delete_existing(self, registry, ctx, temp_capsule):
        from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
        mgr = MemoryLifecycleManager(capsule_path=Path(temp_capsule))
        mem = mgr.add_candidate("待删除记忆")

        handler = registry.get_handler("stableagent.memory.delete")
        result = handler(ctx, {"memory_id": mem["memory_id"], "capsule_path": temp_capsule})
        assert result.ok is True
        assert result.data["deleted"] is True

    def test_delete_nonexistent(self, registry, ctx, temp_capsule):
        handler = registry.get_handler("stableagent.memory.delete")
        result = handler(ctx, {"memory_id": "mem_nonexist", "capsule_path": temp_capsule})
        assert result.ok is False
