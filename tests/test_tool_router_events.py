"""test_tool_router_events.py — ToolRouter 事件链单元测试。

测试覆盖：
- route() 调用后发布 mcp.call.received 事件
- route() 调用后发布 tool.risk_checked 事件
- 成功调用发布 tool.completed 事件
- forbidden 工具调用发布 tool.failed 事件
"""

from __future__ import annotations

import pytest

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.gateway.tool_router import ToolRouter
from stable_agent.security_policy import SecurityPolicy


# ============================================================================
# Mock EventStream —— 捕获所有通过 publish_sync 发布的事件
# ============================================================================


class MockEventStream:
    """模拟 EventStream，用于捕获事件而不依赖真实事件循环。"""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish_sync(self, run_id: str, event: dict) -> None:
        """捕获发布的事件并存储到列表。"""
        self.events.append(event)

    def subscribe(self, run_id: str):
        """占位 subscribe 方法。"""
        pass  # pragma: no cover — 不在此测试中使用

    def unsubscribe(self, run_id: str, queue) -> None:
        """占位 unsubscribe 方法。"""
        pass  # pragma: no cover — 不在此测试中使用


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def registry() -> UnifiedToolRegistry:
    """创建无 orchestrator 的注册中心。"""
    return UnifiedToolRegistry(orchestrator=None)


@pytest.fixture
def event_stream() -> MockEventStream:
    """创建 MockEventStream 用于捕获事件。"""
    return MockEventStream()


@pytest.fixture
def router_with_stream(
    registry: UnifiedToolRegistry, event_stream: MockEventStream
) -> ToolRouter:
    """创建带 MockEventStream 的 ToolRouter。"""
    return ToolRouter(registry=registry, event_stream=event_stream)


# ============================================================================
# 事件链测试
# ============================================================================


class TestToolRouterEvents:
    """ToolRouter 事件发布测试。"""

    # ------------------------------------------------------------------
    # 测试 1：route() 调用后发布 mcp.call.received
    # ------------------------------------------------------------------

    def test_route_publishes_mcp_call_received(
        self, router_with_stream: ToolRouter, event_stream: MockEventStream
    ) -> None:
        """验证 route() 调用后发布 mcp.call.received 事件。"""
        result = router_with_stream.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试任务"},
        )

        received_events = [
            e for e in event_stream.events
            if e.get("event_type") == "mcp.call.received"
        ]
        assert len(received_events) >= 1, (
            f"应至少发布 1 个 mcp.call.received 事件，"
            f"实际事件类型：{[e.get('event_type') for e in event_stream.events]}"
        )
        # 验证事件包含预期字段
        evt = received_events[0]
        assert evt["run_id"] == result.run_id
        assert evt["payload"]["tool_name"] == "stableagent.memory.retrieve"

    # ------------------------------------------------------------------
    # 测试 2：route() 调用后发布 tool.risk_checked
    # ------------------------------------------------------------------

    def test_route_publishes_tool_risk_checked(
        self, router_with_stream: ToolRouter, event_stream: MockEventStream
    ) -> None:
        """验证 route() 调用后发布 tool.risk_checked 事件。"""
        router_with_stream.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试任务"},
        )

        risk_events = [
            e for e in event_stream.events
            if e.get("event_type") == "tool.risk_checked"
        ]
        assert len(risk_events) >= 1, (
            f"应至少发布 1 个 tool.risk_checked 事件，"
            f"实际事件类型：{[e.get('event_type') for e in event_stream.events]}"
        )
        evt = risk_events[0]
        assert evt["payload"]["tool_name"] == "stableagent.memory.retrieve"
        assert "risk_level" in evt["payload"]

    # ------------------------------------------------------------------
    # 测试 3：成功调用发布 tool.completed
    # ------------------------------------------------------------------

    def test_successful_call_publishes_tool_completed(
        self, router_with_stream: ToolRouter, event_stream: MockEventStream
    ) -> None:
        """验证成功调用（handler 不抛异常）发布 tool.completed 事件。

        注意：因 orchestrator 未注入，handler 返回 is_error=True，
        但 router 仍将其视为正常完成（非异常），发布 tool.completed。
        """
        result = router_with_stream.route(
            "stableagent.skillopt.status",
            {},
        )

        completed_events = [
            e for e in event_stream.events
            if e.get("event_type") == "tool.completed"
        ]
        assert len(completed_events) >= 1, (
            f"应至少发布 1 个 tool.completed 事件，"
            f"实际事件类型：{[e.get('event_type') for e in event_stream.events]}"
        )
        evt = completed_events[0]
        assert evt["run_id"] == result.run_id
        assert evt["payload"]["tool_name"] == "stableagent.skillopt.status"

    # ------------------------------------------------------------------
    # 测试 4：forbidden 工具调用发布 tool.failed
    # ------------------------------------------------------------------

    def test_forbidden_tool_publishes_tool_failed(
        self, registry: UnifiedToolRegistry
    ) -> None:
        """验证 forbidden 工具调用发布 tool.failed 事件。

        使用 SecurityPolicy + 包含 forbidden 模式的参数
        （如 "rm -rf"），触发 forbidden 风险等级，
        验证 router 发布 tool.failed 事件。
        """
        event_stream = MockEventStream()
        security = SecurityPolicy()
        router = ToolRouter(
            registry=registry,
            security_policy=security,
            event_stream=event_stream,
        )

        # 使用包含 "rm -rf" 的参数触发 forbidden
        result = router.route(
            "stableagent.memory.retrieve",
            {"task_input": "rm -rf /"},
        )

        # 验证结果标记为错误
        assert result.is_error is True, "forbidden 工具应返回 is_error=True"
        assert "禁止执行" in result.plain_text

        # 验证 tool.failed 事件已发布
        failed_events = [
            e for e in event_stream.events
            if e.get("event_type") == "tool.failed"
        ]
        assert len(failed_events) >= 1, (
            f"应至少发布 1 个 tool.failed 事件，"
            f"实际事件类型：{[e.get('event_type') for e in event_stream.events]}"
        )
        evt = failed_events[0]
        assert evt["payload"]["reason"] == "forbidden"

    def test_forbidden_tool_does_not_publish_completed(
        self, registry: UnifiedToolRegistry
    ) -> None:
        """验证 forbidden 工具不发布 tool.completed 事件。"""
        event_stream = MockEventStream()
        security = SecurityPolicy()
        router = ToolRouter(
            registry=registry,
            security_policy=security,
            event_stream=event_stream,
        )

        router.route(
            "stableagent.memory.retrieve",
            {"task_input": "rm -rf /"},
        )

        completed_events = [
            e for e in event_stream.events
            if e.get("event_type") == "tool.completed"
        ]
        assert len(completed_events) == 0, (
            "forbidden 工具不应发布 tool.completed 事件"
        )

    # ------------------------------------------------------------------
    # 事件顺序验证（bonus）
    # ------------------------------------------------------------------

    def test_events_published_in_correct_order(
        self, router_with_stream: ToolRouter, event_stream: MockEventStream
    ) -> None:
        """验证事件按正确顺序发布：received → risk_checked → started → completed。"""
        router_with_stream.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试"},
        )

        event_types = [e["event_type"] for e in event_stream.events]
        # 过滤出核心事件类型
        core_events = [
            t for t in event_types
            if t in {"mcp.call.received", "tool.risk_checked", "tool.started", "tool.completed"}
        ]

        # 验证顺序
        expected_order = ["mcp.call.received", "tool.risk_checked", "tool.started", "tool.completed"]
        # 提取 core_events 中在 expected_order 中的位置
        core_order = [t for t in core_events if t in expected_order]
        assert core_order == expected_order, (
            f"事件顺序不正确，期望 {expected_order}，实际 {core_order}"
        )

    def test_events_have_run_id_consistency(
        self, router_with_stream: ToolRouter, event_stream: MockEventStream
    ) -> None:
        """验证同一 route() 调用产生的所有事件共享相同 run_id。"""
        result = router_with_stream.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试"},
        )

        for evt in event_stream.events:
            assert evt["run_id"] == result.run_id, (
                f"事件 run_id 不一致：event={evt['event_type']}, "
                f"event.run_id={evt['run_id']}, result.run_id={result.run_id}"
            )
