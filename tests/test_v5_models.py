"""V5 基础设施与数据层测试。

覆盖 RunContext、StableAgentToolResult、Tool Schemas、
RunStore、EventStream 和 AVATAR_STATE_MAP 的核心功能。
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.tool_schemas import (
    AVATAR_STATE_MAP,
    TOOLS,
    get_avatar_state,
    get_risk_level,
    get_tool_by_name,
    get_tool_names,
)
from stable_agent.models import StableAgentToolResult
from stable_agent.observation.event_stream import EventStream
from stable_agent.observation.run_store import RunStore


# ============================================================================
# RunContext 测试
# ============================================================================


class TestRunContext:
    """RunContext 数据类测试套件。"""

    def test_run_context_defaults(self) -> None:
        """测试 RunContext 默认值初始化。"""
        ctx = RunContext()

        assert isinstance(ctx.run_id, str)
        assert len(ctx.run_id) > 0
        # 验证 UUID 格式
        uuid.UUID(ctx.run_id)

        assert isinstance(ctx.tool_call_id, str)
        uuid.UUID(ctx.tool_call_id)

        assert isinstance(ctx.trace_id, str)
        uuid.UUID(ctx.trace_id)

        assert isinstance(ctx.span_id, str)
        uuid.UUID(ctx.span_id)

        assert ctx.parent_span_id is None
        assert isinstance(ctx.started_at, float)
        assert ctx.started_at > 0

    def test_run_context_child_span(self) -> None:
        """测试 child_span() 继承 run_id + trace_id，生成新 span_id。"""
        parent = RunContext()
        child = parent.child_span()

        # 子 span 继承父的 run_id、tool_call_id、trace_id
        assert child.run_id == parent.run_id
        assert child.tool_call_id == parent.tool_call_id
        assert child.trace_id == parent.trace_id

        # 子 span 拥有新的 span_id
        assert child.span_id != parent.span_id

        # 子 span 的 parent_span_id 指向父
        assert child.parent_span_id == parent.span_id

        # 子 span 拥有新的 started_at
        assert child.started_at >= parent.started_at

    def test_run_context_unique_ids(self) -> None:
        """测试每次创建的 RunContext 拥有唯一 ID。"""
        ctx1 = RunContext()
        ctx2 = RunContext()

        assert ctx1.run_id != ctx2.run_id
        assert ctx1.span_id != ctx2.span_id
        assert ctx1.tool_call_id != ctx2.tool_call_id
        assert ctx1.trace_id != ctx2.trace_id

    def test_run_context_explicit_values(self) -> None:
        """测试显式指定字段值。"""
        now = time.time()
        ctx = RunContext(
            run_id="run-001",
            tool_call_id="tc-001",
            trace_id="trace-001",
            span_id="span-001",
            parent_span_id="span-000",
            started_at=now,
        )

        assert ctx.run_id == "run-001"
        assert ctx.tool_call_id == "tc-001"
        assert ctx.trace_id == "trace-001"
        assert ctx.span_id == "span-001"
        assert ctx.parent_span_id == "span-000"
        assert ctx.started_at == now

    def test_run_context_deep_nesting(self) -> None:
        """测试深层嵌套 child_span 的链路正确性。"""
        root = RunContext()
        l1 = root.child_span()
        l2 = l1.child_span()
        l3 = l2.child_span()

        # 所有层级共享 run_id 和 trace_id
        for span in (l1, l2, l3):
            assert span.run_id == root.run_id
            assert span.trace_id == root.trace_id

        # 父级关系链条
        assert l1.parent_span_id == root.span_id
        assert l2.parent_span_id == l1.span_id
        assert l3.parent_span_id == l2.span_id

        # 所有 span_id 互不相同
        span_ids = {root.span_id, l1.span_id, l2.span_id, l3.span_id}
        assert len(span_ids) == 4


# ============================================================================
# StableAgentToolResult 测试
# ============================================================================


class TestStableAgentToolResult:
    """StableAgentToolResult 数据类测试套件。"""

    def test_tool_result_defaults(self) -> None:
        """测试默认值初始化。"""
        result = StableAgentToolResult()

        assert result.ok is False
        assert result.run_id == ""
        assert result.tool_call_id == ""
        assert result.tool_name == ""
        assert result.data == {}
        assert result.plain_text == ""
        assert result.warnings == []
        assert result.next_actions == []
        assert result.trace_url == ""
        assert result.is_error is False

    def test_tool_result_full(self) -> None:
        """测试完整字段赋值。"""
        result = StableAgentToolResult(
            ok=True,
            run_id="run-001",
            tool_call_id="tc-001",
            tool_name="stableagent.memory.retrieve",
            data={"memories": [{"id": "m1", "content": "test"}]},
            plain_text="Found 1 memory item.",
            warnings=["Low confidence retrieval"],
            next_actions=["stableagent.context.build"],
            trace_url="https://trace.example.com/runs/run-001",
            is_error=False,
        )

        assert result.ok is True
        assert result.run_id == "run-001"
        assert result.tool_call_id == "tc-001"
        assert result.tool_name == "stableagent.memory.retrieve"
        assert len(result.data["memories"]) == 1
        assert result.plain_text == "Found 1 memory item."
        assert len(result.warnings) == 1
        assert "stableagent.context.build" in result.next_actions
        assert result.trace_url.startswith("https://")
        assert result.is_error is False

    def test_tool_result_error(self) -> None:
        """测试错误返回的 tool result。"""
        result = StableAgentToolResult(
            ok=False,
            run_id="run-err",
            tool_call_id="tc-err",
            tool_name="stableagent.task.process",
            plain_text="Task processing failed.",
            warnings=["Memory retrieval timeout", "RAG service unavailable"],
            is_error=True,
        )

        assert result.ok is False
        assert result.is_error is True
        assert len(result.warnings) == 2


# ============================================================================
# Tool Schemas 测试
# ============================================================================


class TestToolSchemas:
    """Tool Schema 测试套件。"""

    def test_all_14_tools_defined(self) -> None:
        """验证恰好定义了 14 个工具。"""
        assert len(TOOLS) == 14

    def test_each_tool_has_required_fields(self) -> None:
        """验证每个工具定义包含所有必要字段。"""
        required_fields = {"name", "title", "description", "input_schema", "risk_level"}

        for tool_name, tool_def in TOOLS.items():
            missing = required_fields - set(tool_def.keys())
            assert not missing, f"Tool '{tool_name}' missing fields: {missing}"

            # 验证 name 字段匹配 key
            assert tool_def["name"] == tool_name, (
                f"Tool '{tool_name}' has mismatched name: {tool_def['name']}"
            )

    def test_risk_levels_valid(self) -> None:
        """验证所有风险等级在合法范围内。"""
        valid_risks = {"low", "medium", "high", "forbidden"}

        for tool_name, tool_def in TOOLS.items():
            risk = tool_def["risk_level"]
            assert risk in valid_risks, (
                f"Tool '{tool_name}' has invalid risk_level: {risk}"
            )

    def test_input_schemas_valid(self) -> None:
        """验证所有工具的 input_schema 是合法的 JSON Schema。"""
        for tool_name, tool_def in TOOLS.items():
            schema = tool_def["input_schema"]
            assert schema["type"] == "object", (
                f"Tool '{tool_name}' input_schema type is not 'object'"
            )
            # properties 应为 dict
            assert isinstance(schema.get("properties", {}), dict), (
                f"Tool '{tool_name}' properties is not a dict"
            )

    def test_get_tool_names(self) -> None:
        """测试 get_tool_names 返回完整列表。"""
        names = get_tool_names()
        assert len(names) == 14
        assert "stableagent.task.process" in names
        assert "stableagent.approval.respond" in names

    def test_get_tool_by_name_found(self) -> None:
        """测试按名称查找已注册工具。"""
        tool = get_tool_by_name("stableagent.memory.retrieve")
        assert tool is not None
        assert tool["name"] == "stableagent.memory.retrieve"
        assert tool["risk_level"] == "low"

    def test_get_tool_by_name_not_found(self) -> None:
        """测试查找不存在的工具返回 None。"""
        tool = get_tool_by_name("stableagent.nonexistent.tool")
        assert tool is None

    def test_get_risk_level(self) -> None:
        """测试获取工具风险等级。"""
        assert get_risk_level("stableagent.approval.respond") == "high"
        assert get_risk_level("stableagent.skillopt.run_epoch") == "medium"
        assert get_risk_level("stableagent.memory.retrieve") == "low"

    def test_get_risk_level_unknown_tool(self) -> None:
        """测试未知工具的风险等级默认为 low。"""
        assert get_risk_level("unknown.tool") == "low"


# ============================================================================
# RunStore 测试
# ============================================================================


class TestRunStore:
    """RunStore 测试套件。"""

    def test_create_and_append_run(self) -> None:
        """测试创建 run 和追加事件。"""
        store = RunStore()
        store.create_run("run-001")
        store.append_event("run-001", {"type": "task.started", "data": {"task": "hello"}})

        events = store.get_events("run-001")
        assert len(events) == 1
        assert events[0]["type"] == "task.started"
        assert events[0]["data"]["task"] == "hello"

    def test_get_events_by_run(self) -> None:
        """测试按 run_id 获取事件，隔离性正确。"""
        store = RunStore()

        store.append_event("run-A", {"type": "event.a.1"})
        store.append_event("run-A", {"type": "event.a.2"})
        store.append_event("run-B", {"type": "event.b.1"})

        events_a = store.get_events("run-A")
        events_b = store.get_events("run-B")

        assert len(events_a) == 2
        assert len(events_b) == 1
        assert events_a[0]["type"] == "event.a.1"
        assert events_a[1]["type"] == "event.a.2"
        assert events_b[0]["type"] == "event.b.1"

    def test_list_active_runs(self) -> None:
        """测试列出活跃 runs。"""
        store = RunStore()
        store.create_run("run-001")
        store.create_run("run-002")
        store.mark_completed("run-002")
        store.create_run("run-003")

        active = store.list_active_runs()
        active_ids = {r["run_id"] for r in active}

        assert "run-001" in active_ids
        assert "run-002" not in active_ids  # 已完成
        assert "run-003" in active_ids

    def test_append_event_auto_creates_run(self) -> None:
        """测试追加事件到不存在的 run 时自动创建。"""
        store = RunStore()
        store.append_event("auto-run", {"type": "auto.created"})

        events = store.get_events("auto-run")
        assert len(events) == 1
        assert events[0]["type"] == "auto.created"

    def test_get_events_nonexistent_run(self) -> None:
        """测试获取不存在 run 的事件返回空列表。"""
        store = RunStore()
        events = store.get_events("nonexistent")
        assert events == []

    def test_get_run_status(self) -> None:
        """测试获取 run 状态。"""
        store = RunStore()
        store.create_run("run-001")
        store.append_event("run-001", {"type": "e1"})
        store.append_event("run-001", {"type": "e2"})

        status = store.get_run_status("run-001")
        assert status is not None
        assert status["run_id"] == "run-001"
        assert status["status"] == "running"
        assert status["event_count"] == 2
        assert isinstance(status["started_at"], float)

    def test_get_run_status_nonexistent(self) -> None:
        """测试获取不存在 run 的状态返回 None。"""
        store = RunStore()
        assert store.get_run_status("nonexistent") is None

    def test_mark_completed(self) -> None:
        """测试将 run 标记为已完成。"""
        store = RunStore()
        store.create_run("run-001")
        store.mark_completed("run-001")

        status = store.get_run_status("run-001")
        assert status["status"] == "completed"

    def test_mark_failed(self) -> None:
        """测试将 run 标记为失败。"""
        store = RunStore()
        store.create_run("run-001")
        store.mark_failed("run-001")

        status = store.get_run_status("run-001")
        assert status["status"] == "failed"

    def test_list_active_runs_limit(self) -> None:
        """测试 list_active_runs 的 limit 参数。"""
        store = RunStore()
        for i in range(5):
            store.create_run(f"run-{i:03d}")

        active = store.list_active_runs(limit=3)
        assert len(active) == 3

    def test_events_have_timestamps(self) -> None:
        """测试追加的事件自动获得 timestamp。"""
        store = RunStore()
        store.append_event("run-001", {"type": "no_timestamp"})

        events = store.get_events("run-001")
        assert "timestamp" in events[0]
        assert isinstance(events[0]["timestamp"], float)

    def test_create_run_is_idempotent(self) -> None:
        """测试重复创建同一 run 不会重置数据。"""
        store = RunStore()
        store.create_run("run-001")
        store.append_event("run-001", {"type": "first"})
        # 再次 create 不应清空事件
        store.create_run("run-001")
        store.append_event("run-001", {"type": "second"})

        events = store.get_events("run-001")
        assert len(events) == 2


# ============================================================================
# AVATAR_STATE_MAP 测试
# ============================================================================


class TestAvatarStateMap:
    """AVATAR_STATE_MAP 测试套件。"""

    def test_all_events_have_avatar_state(self) -> None:
        """验证常见事件类型都有对应的头像状态。"""
        expected_events = [
            "mcp.call.received",
            "task.classified",
            "context.budgeted",
            "memory.retrieved",
            "rag.retrieved",
            "tool.risk_checked",
            "approval.required",
            "workflow.step.started",
            "eval.completed",
            "skillopt.patch.proposed",
            "skillopt.validation.running",
            "skillopt.exported",
            "tool.failed",
            "task.completed",
        ]
        for event_type in expected_events:
            assert event_type in AVATAR_STATE_MAP, (
                f"Event '{event_type}' missing from AVATAR_STATE_MAP"
            )

    def test_default_state_exists(self) -> None:
        """验证默认状态 "default" 存在。"""
        assert "default" in AVATAR_STATE_MAP
        assert AVATAR_STATE_MAP["default"] == "listening"  # V5.6: 语义场景升级

    def test_get_avatar_state_known(self) -> None:
        """测试已知事件返回正确的头像状态。"""
        assert get_avatar_state("mcp.call.received") == "listening"
        assert get_avatar_state("task.completed") == "done"  # V5.6: 语义场景升级
        assert get_avatar_state("tool.failed") == "failed"  # V5.6: 语义场景升级

    def test_get_avatar_state_unknown(self) -> None:
        """测试未知事件返回默认状态。"""
        assert get_avatar_state("unknown.event.type") == "listening"  # V5.6: 语义场景默认值


# ============================================================================
# EventStream 异步测试
# ============================================================================


class TestEventStream:
    """EventStream 异步事件流测试套件。"""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        """测试订阅后能收到发布的事件。"""
        stream = EventStream()
        queue = await stream.subscribe("run-001")
        await stream.publish("run-001", {"type": "test.event", "payload": "hello"})

        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["type"] == "test.event"
        assert event["payload"] == "hello"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        """测试多个订阅者同时接收同一 run 的事件。"""
        stream = EventStream()
        q1 = await stream.subscribe("run-001")
        q2 = await stream.subscribe("run-001")

        await stream.publish("run-001", {"type": "broadcast"})

        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)

        assert e1["type"] == "broadcast"
        assert e2["type"] == "broadcast"

    @pytest.mark.asyncio
    async def test_run_isolation(self) -> None:
        """测试不同 run 的事件隔离性。"""
        stream = EventStream()
        q_a = await stream.subscribe("run-A")
        q_b = await stream.subscribe("run-B")

        await stream.publish("run-A", {"type": "for.a"})
        await stream.publish("run-B", {"type": "for.b"})

        e_a = await asyncio.wait_for(q_a.get(), timeout=1.0)
        e_b = await asyncio.wait_for(q_b.get(), timeout=1.0)

        assert e_a["type"] == "for.a"
        assert e_b["type"] == "for.b"

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        """测试取消订阅后不再收到事件。"""
        stream = EventStream()
        queue = await stream.subscribe("run-001")
        stream.unsubscribe("run-001", queue)

        await stream.publish("run-001", {"type": "should.not.arrive"})

        # 队列应该为空
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_event_auto_timestamp(self) -> None:
        """测试发布的事件自动获得 timestamp。"""
        stream = EventStream()
        queue = await stream.subscribe("run-001")
        await stream.publish("run-001", {"type": "no_ts"})

        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert "timestamp" in event
        assert isinstance(event["timestamp"], float)

    @pytest.mark.asyncio
    async def test_publish_global(self) -> None:
        """测试全局发布到所有 run。"""
        stream = EventStream()
        q1 = await stream.subscribe("run-A")
        q2 = await stream.subscribe("run-B")

        await stream.publish_global({"type": "global.event"})

        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)

        assert e1["type"] == "global.event"
        assert e2["type"] == "global.event"

    @pytest.mark.asyncio
    async def test_preserves_existing_timestamp(self) -> None:
        """测试如果事件已有 timestamp，发布时不覆盖。"""
        stream = EventStream()
        queue = await stream.subscribe("run-001")
        custom_ts = 12345.6789
        await stream.publish("run-001", {"type": "custom_ts", "timestamp": custom_ts})

        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["timestamp"] == custom_ts
