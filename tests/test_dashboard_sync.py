"""test_dashboard_sync.py — DashboardSync 单元测试。

测试覆盖：
- DashboardSync 创建 FastAPI 子应用
- /ws/runs/{run_id} 端点注册
- run_id 参数验证
- 订阅生命周期管理
"""

from __future__ import annotations

import asyncio
import json

import pytest

from stable_agent.observation.event_stream import EventStream
from stable_agent.observation.dashboard_sync import DashboardSync


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def event_stream() -> EventStream:
    """创建 EventStream 实例。"""
    return EventStream()


@pytest.fixture
def dashboard_sync(event_stream: EventStream) -> DashboardSync:
    """创建 DashboardSync 实例。"""
    return DashboardSync(event_stream)


# ============================================================================
# create_app — FastAPI 子应用
# ============================================================================


class TestDashboardSyncCreateApp:
    """测试 DashboardSync.create_app 创建的应用。"""

    def test_create_app_returns_fastapi_app(self, dashboard_sync: DashboardSync) -> None:
        """create_app 应返回 FastAPI 实例。"""
        app = dashboard_sync.create_app()
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_app_has_title(self, dashboard_sync: DashboardSync) -> None:
        """创建的应用应有标题。"""
        app = dashboard_sync.create_app()
        assert app.title != ""

    def test_ws_endpoint_registered(self, dashboard_sync: DashboardSync) -> None:
        """WebSocket 端点 /ws/runs/{run_id} 应已注册。"""
        app = dashboard_sync.create_app()
        routes = [r.path for r in app.routes]
        # FastAPI 的 WebSocket 路由路径格式为 /ws/runs/{run_id}
        ws_paths = [r for r in routes if "runs" in r]
        assert len(ws_paths) > 0, f"未找到 /ws/runs/ 路由，现有路由: {routes}"


# ============================================================================
# run_id 参数
# ============================================================================


class TestRunIdParameter:
    """测试 run_id 路径参数。"""

    def test_run_id_in_route_path(self, dashboard_sync: DashboardSync) -> None:
        """WebSocket 路由应接受 run_id 路径参数。"""
        app = dashboard_sync.create_app()
        routes = app.routes
        # 查找带有 run_id 参数的路由
        has_run_id = False
        for route in routes:
            if hasattr(route, "path") and "run_id" in route.path:
                has_run_id = True
                break
        assert has_run_id, "没有包含 run_id 的 WebSocket 路由"


# ============================================================================
# 订阅生命周期
# ============================================================================


class TestSubscriptionLifecycle:
    """测试订阅生命周期管理。"""

    def test_subscribe_creates_entry(self, event_stream: EventStream) -> None:
        """订阅应创建 subscriber 条目。"""
        async def _test():
            q = await event_stream.subscribe("lifecycle-test")
            assert "lifecycle-test" in event_stream._subscribers
            event_stream.unsubscribe("lifecycle-test", q)

        asyncio.run(_test())

    def test_unsubscribe_removes_entry(self, event_stream: EventStream) -> None:
        """取消订阅应移除 subscriber 条目。"""
        async def _test():
            q = await event_stream.subscribe("cleanup-test")
            assert "cleanup-test" in event_stream._subscribers
            event_stream.unsubscribe("cleanup-test", q)
            assert "cleanup-test" not in event_stream._subscribers

        asyncio.run(_test())

    def test_unsubscribe_only_removes_specific_queue(self, event_stream: EventStream) -> None:
        """取消订阅只移除指定的队列，不影响同 run 的其他订阅者。"""
        async def _test():
            q1 = await event_stream.subscribe("multi-sub")
            q2 = await event_stream.subscribe("multi-sub")
            assert len(event_stream._subscribers["multi-sub"]) == 2
            event_stream.unsubscribe("multi-sub", q1)
            assert len(event_stream._subscribers["multi-sub"]) == 1
            event_stream.unsubscribe("multi-sub", q2)
            assert "multi-sub" not in event_stream._subscribers

        asyncio.run(_test())

    def test_unsubscribe_nonexistent_does_not_raise(self, event_stream: EventStream) -> None:
        """取消不存在的订阅不应抛出异常。"""
        queue = asyncio.Queue()
        # 不应抛异常
        event_stream.unsubscribe("nonexistent", queue)

    def test_publish_global(self, event_stream: EventStream) -> None:
        """publish_global 应向所有订阅者广播。"""
        async def _test():
            q1 = await event_stream.subscribe("g1")
            q2 = await event_stream.subscribe("g2")
            await event_stream.publish_global({"event_type": "global", "payload": {}})
            e1 = await q1.get()
            e2 = await q2.get()
            assert e1["event_type"] == "global"
            assert e2["event_type"] == "global"
            event_stream.unsubscribe("g1", q1)
            event_stream.unsubscribe("g2", q2)

        asyncio.run(_test())


# ============================================================================
# DashboardSync 集成
# ============================================================================


class TestDashboardSyncIntegration:
    """测试 DashboardSync 与 EventStream 的集成。"""

    def test_event_stream_receives_dashboard_events(self, dashboard_sync: DashboardSync, event_stream: EventStream) -> None:
        """通过 EventStream 发布的事件应能被 DashboardSync 订阅者接收。"""
        async def _test():
            q = await event_stream.subscribe("dash-run-001")
            await event_stream.publish("dash-run-001", {
                "event_type": "tool.started",
                "payload": {"tool_name": "test.tool"},
                "plain_text": "工具启动",
                "avatar_state": "working",
            })
            event = await q.get()
            assert event["event_type"] == "tool.started"
            assert event["avatar_state"] == "working"
            assert event["plain_text"] == "工具启动"
            event_stream.unsubscribe("dash-run-001", q)

        asyncio.run(_test())

    def test_create_app_twice_returns_different_apps(self, dashboard_sync: DashboardSync) -> None:
        """两次调用 create_app 应返回不同的 FastAPI 实例。"""
        app1 = dashboard_sync.create_app()
        app2 = dashboard_sync.create_app()
        assert app1 is not app2

    def test_dashboard_sync_stores_event_stream(self, dashboard_sync: DashboardSync, event_stream: EventStream) -> None:
        """DashboardSync 应存储传入的 EventStream 引用。"""
        assert dashboard_sync.event_stream is event_stream
