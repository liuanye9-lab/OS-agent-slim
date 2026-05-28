"""test_tool_trace_integration.py — 工具调用追踪集成测试。

测试覆盖：
- ToolRouter 创建 RunContext
- ToolRouter 发布 mcp.call.received 事件
- 路由事件包含 avatar_state
- RunStore 存储事件
- EventStream 广播给订阅者
- 不同 run_id 的隔离
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.tool_router import ToolRouter
from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.observation.run_store import RunStore
from stable_agent.observation.event_stream import EventStream
from stable_agent.models import StableAgentToolResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def registry() -> UnifiedToolRegistry:
    """创建无 orchestrator 的注册中心。"""
    return UnifiedToolRegistry(orchestrator=None)


@pytest.fixture
def run_store() -> RunStore:
    """创建 RunStore 实例。"""
    return RunStore()


@pytest.fixture
def event_stream() -> EventStream:
    """创建 EventStream 实例。"""
    return EventStream()


@pytest.fixture
def router_with_store(
    registry: UnifiedToolRegistry,
    run_store: RunStore,
    event_stream: EventStream,
) -> ToolRouter:
    """创建带 RunStore 和 EventStream 的 ToolRouter。"""
    return ToolRouter(
        registry=registry,
        run_store=run_store,
        event_stream=event_stream,
    )


@pytest.fixture
def router_bare(registry: UnifiedToolRegistry) -> ToolRouter:
    """创建裸 ToolRouter（无 store/stream）。"""
    return ToolRouter(registry=registry)


# ============================================================================
# RunContext 创建
# ============================================================================


class TestRunContextCreation:
    """测试 RunContext 创建。"""

    def test_run_context_has_unique_ids(self) -> None:
        """每个 RunContext 应有唯一的 run_id、tool_call_id、trace_id、span_id。"""
        ctx1 = RunContext()
        ctx2 = RunContext()
        assert ctx1.run_id != ctx2.run_id
        assert ctx1.tool_call_id != ctx2.tool_call_id
        assert ctx1.trace_id != ctx2.trace_id
        assert ctx1.span_id != ctx2.span_id

    def test_run_context_has_started_at(self) -> None:
        """RunContext.started_at 应为合理的时间戳。"""
        now = time.time()
        ctx = RunContext()
        assert ctx.started_at <= now + 1
        assert ctx.started_at >= now - 1

    def test_parent_span_id_none_for_root(self) -> None:
        """根 RunContext 的 parent_span_id 应为 None。"""
        ctx = RunContext()
        assert ctx.parent_span_id is None

    def test_child_span_inherits_run_id(self) -> None:
        """子 span 应继承父级的 run_id。"""
        parent = RunContext()
        child = parent.child_span()
        assert child.run_id == parent.run_id
        assert child.tool_call_id == parent.tool_call_id
        assert child.trace_id == parent.trace_id

    def test_child_span_has_different_span_id(self) -> None:
        """子 span 应有不同的 span_id。"""
        parent = RunContext()
        child = parent.child_span()
        assert child.span_id != parent.span_id

    def test_child_span_parent_set(self) -> None:
        """子 span 的 parent_span_id 应为父级的 span_id。"""
        parent = RunContext()
        child = parent.child_span()
        assert child.parent_span_id == parent.span_id


# ============================================================================
# ToolRouter 路由测试
# ============================================================================


class TestToolRouterRouting:
    """测试 ToolRouter.route 的基本路由。"""

    def test_route_known_tool_returns_result(self, router_bare: ToolRouter) -> None:
        """路由已知工具应返回 StableAgentToolResult。"""
        result = router_bare.route(
            "stableagent.context.build",
            {"task_input": "测试任务"},
        )
        assert isinstance(result, StableAgentToolResult)

    def test_route_unknown_tool_returns_error(self, router_bare: ToolRouter) -> None:
        """路由未知工具应返回 is_error=True 的结果。"""
        result = router_bare.route(
            "stableagent.unknown.fake",
            {"task_input": "测试"},
        )
        assert result.is_error is True
        assert "未知工具" in result.plain_text

    def test_route_result_has_run_id(self, router_bare: ToolRouter) -> None:
        """路由结果应包含 run_id。"""
        result = router_bare.route(
            "stableagent.context.build",
            {"task_input": "测试"},
        )
        assert result.run_id != ""

    def test_route_result_has_tool_name(self, router_bare: ToolRouter) -> None:
        """路由结果应包含 tool_name。"""
        result = router_bare.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试"},
        )
        assert result.tool_name == "stableagent.memory.retrieve"


# ============================================================================
# RunStore 集成
# ============================================================================


class TestRunStoreIntegration:
    """测试 ToolRouter + RunStore 集成。"""

    def test_router_stores_events(self, router_with_store: ToolRouter, run_store: RunStore) -> None:
        """ToolRouter 路由后应在 RunStore 中存储事件。"""
        router_with_store.route(
            "stableagent.context.build",
            {"task_input": "测试"},
        )
        # 检查 RunStore 中有活跃的 runs
        active = run_store.list_active_runs()
        assert len(active) >= 1

    def test_router_events_have_event_type(self, router_with_store: ToolRouter, run_store: RunStore) -> None:
        """存储的事件应包含 event_type 字段。"""
        router_with_store.route(
            "stableagent.context.build",
            {"task_input": "测试"},
        )
        active = run_store.list_active_runs()
        assert len(active) >= 1
        events = run_store.get_events(active[0]["run_id"])
        event_types = [e.get("event_type", "") for e in events]
        # 至少应有 tool.completed 或 tool.started 事件
        assert any("tool.completed" in t or "tool.started" in t for t in event_types), (
            f"找不到 tool.completed 或 tool.started 事件: {event_types}"
        )

    def test_events_have_timestamp(self, router_with_store: ToolRouter, run_store: RunStore) -> None:
        """存储的事件应包含 timestamp 字段。"""
        router_with_store.route(
            "stableagent.context.build",
            {"task_input": "测试"},
        )
        active = run_store.list_active_runs()
        events = run_store.get_events(active[0]["run_id"])
        for event in events:
            assert "timestamp" in event, f"事件缺少 timestamp: {event}"

    def test_events_have_run_id(self, router_with_store: ToolRouter, run_store: RunStore) -> None:
        """存储的事件应包含 run_id 字段。"""
        router_with_store.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试"},
        )
        active = run_store.list_active_runs()
        events = run_store.get_events(active[0]["run_id"])
        for event in events:
            assert "run_id" in event, f"事件缺少 run_id: {event}"


# ============================================================================
# EventStream 集成
# ============================================================================


class TestEventStreamIntegration:
    """测试 EventStream 的发布/订阅。"""

    def test_event_stream_publish_subscribe(self) -> None:
        """EventStream 应能发布事件给订阅者。"""
        stream = EventStream()

        async def _test():
            queue = await stream.subscribe("run-001")
            await stream.publish("run-001", {"event_type": "test.event", "payload": {}})
            event = await queue.get()
            assert event["event_type"] == "test.event"
            stream.unsubscribe("run-001", queue)

        asyncio.run(_test())

    def test_event_stream_multiple_subscribers(self) -> None:
        """同一 run_id 的多个订阅者都应收到事件。"""
        stream = EventStream()

        async def _test():
            q1 = await stream.subscribe("run-001")
            q2 = await stream.subscribe("run-001")
            await stream.publish("run-001", {"event_type": "broadcast", "payload": {}})
            e1 = await q1.get()
            e2 = await q2.get()
            assert e1["event_type"] == "broadcast"
            assert e2["event_type"] == "broadcast"
            stream.unsubscribe("run-001", q1)
            stream.unsubscribe("run-001", q2)

        asyncio.run(_test())

    def test_event_stream_run_isolation(self) -> None:
        """不同 run_id 的事件应相互隔离。"""
        stream = EventStream()

        async def _test():
            q1 = await stream.subscribe("run-a")
            q2 = await stream.subscribe("run-b")
            await stream.publish("run-a", {"event_type": "a.event", "payload": {}})
            # run-b 的订阅者不应收到 run-a 的事件
            e1 = await q1.get()
            assert e1["event_type"] == "a.event"
            # q2 应该为空（timeout 测试）
            try:
                e2 = await asyncio.wait_for(q2.get(), timeout=0.1)
                assert e2["event_type"] != "a.event", "run-b 不应收到 run-a 的事件"
            except asyncio.TimeoutError:
                pass  # 期望超时
            stream.unsubscribe("run-a", q1)
            stream.unsubscribe("run-b", q2)

        asyncio.run(_test())

    def test_event_stream_unsubscribe_cleans_up(self) -> None:
        """取消订阅后 subscriber 字典应清理。"""
        stream = EventStream()

        async def _test():
            q = await stream.subscribe("run-001")
            stream.unsubscribe("run-001", q)
            # 订阅者字典应不再包含该 run_id
            assert "run-001" not in stream._subscribers

        asyncio.run(_test())

    def test_event_stream_publish_adds_timestamp(self) -> None:
        """publish 应自动添加 timestamp。"""
        stream = EventStream()

        async def _test():
            q = await stream.subscribe("run-001")
            await stream.publish("run-001", {"event_type": "no_ts"})
            event = await q.get()
            assert "timestamp" in event
            stream.unsubscribe("run-001", q)

        asyncio.run(_test())


# ============================================================================
# avatar_state 验证
# ============================================================================


class TestAvatarState:
    """测试路由事件的 avatar_state 映射。"""

    def test_avatar_state_in_tool_schemas(self) -> None:
        """工具 schema 中应包含 avatar_state 映射。"""
        from stable_agent.gateway.tool_schemas import AVATAR_STATE_MAP, get_avatar_state

        # 验证已知事件有映射
        assert get_avatar_state("mcp.call.received") in AVATAR_STATE_MAP.values()
        assert isinstance(get_avatar_state("tool.started"), str)
        assert get_avatar_state("tool.completed") is not None
        assert get_avatar_state("tool.failed") is not None

    def test_unknown_event_has_default_avatar_state(self) -> None:
        """未知事件应有默认 avatar_state。"""
        from stable_agent.gateway.tool_schemas import get_avatar_state

        state = get_avatar_state("nonexistent.event.type")
        assert isinstance(state, str)
        assert len(state) > 0


# ============================================================================
# 多 run_id 隔离
# ============================================================================


class TestMultipleRunIds:
    """测试不同 run_id 的隔离。"""

    def test_different_runs_have_separate_events(self, router_with_store: ToolRouter, run_store: RunStore) -> None:
        """不同工具调用应产生不同的 run_id。"""
        result1 = router_with_store.route(
            "stableagent.context.build",
            {"task_input": "任务A"},
        )
        result2 = router_with_store.route(
            "stableagent.memory.retrieve",
            {"task_input": "任务B"},
        )

        assert result1.run_id != result2.run_id

        events1 = run_store.get_events(result1.run_id)
        events2 = run_store.get_events(result2.run_id)

        assert len(events1) > 0
        assert len(events2) > 0
        # 事件不应混杂
        assert all(e["run_id"] == result1.run_id for e in events1)
        assert all(e["run_id"] == result2.run_id for e in events2)


# ============================================================================
# RunStore 基础操作
# ============================================================================


class TestRunStoreBasic:
    """测试 RunStore 的基础 CRUD 操作。"""

    def test_create_and_get_run(self, run_store: RunStore) -> None:
        """创建 run 后应能从 store 中获取。"""
        run_store.create_run("test-run")
        status = run_store.get_run_status("test-run")
        assert status is not None
        assert status["run_id"] == "test-run"
        assert status["status"] == "running"

    def test_append_event_auto_creates_run(self, run_store: RunStore) -> None:
        """追加事件应自动创建不存在的 run。"""
        run_store.append_event("new-run", {"event_type": "test", "payload": {}})
        events = run_store.get_events("new-run")
        assert len(events) == 1
        assert events[0]["event_type"] == "test"

    def test_mark_completed(self, run_store: RunStore) -> None:
        """标记完成后状态应变更为 completed。"""
        run_store.create_run("run-x")
        run_store.mark_completed("run-x")
        status = run_store.get_run_status("run-x")
        assert status["status"] == "completed"

    def test_mark_failed(self, run_store: RunStore) -> None:
        """标记失败后状态应变更为 failed。"""
        run_store.create_run("run-y")
        run_store.mark_failed("run-y")
        status = run_store.get_run_status("run-y")
        assert status["status"] == "failed"

    def test_get_nonexistent_run(self, run_store: RunStore) -> None:
        """获取不存在的 run 应返回 None。"""
        assert run_store.get_run_status("nonexistent") is None

    def test_get_nonexistent_events_returns_empty(self, run_store: RunStore) -> None:
        """获取不存在 run 的事件应返回空列表。"""
        assert run_store.get_events("nonexistent") == []
