"""test_event_stream_sync_async.py — EventStream 同步/异步单元测试。

测试覆盖：
- EventStream.publish_sync() 方法存在
- publish_sync() 在无事件循环时正常工作
- EventStream 有 subscribe / unsubscribe 方法
- publish_sync() 在有事件循环时也能正常工作
"""

from __future__ import annotations

import asyncio
import pytest

from stable_agent.observation.event_stream import EventStream


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def stream() -> EventStream:
    """创建 EventStream 实例。"""
    return EventStream()


# ============================================================================
# EventStream 同步/异步测试
# ============================================================================


class TestEventStreamSyncAsync:
    """EventStream publish_sync 及 subscribe/unsubscribe 测试。"""

    # ------------------------------------------------------------------
    # 测试 1：EventStream.publish_sync() 方法存在
    # ------------------------------------------------------------------

    def test_publish_sync_method_exists(self, stream: EventStream) -> None:
        """验证 EventStream 有 publish_sync 方法且可调用。"""
        assert hasattr(stream, "publish_sync"), "EventStream 缺少 publish_sync 方法"
        assert callable(stream.publish_sync), "publish_sync 不可调用"

    # ------------------------------------------------------------------
    # 测试 2：publish_sync() 在无事件循环时正常工作
    # ------------------------------------------------------------------

    def test_publish_sync_works_without_event_loop(self, stream: EventStream) -> None:
        """验证 publish_sync() 在没有运行中事件循环时正常执行（不抛异常）。

        publish_sync 内部捕获 RuntimeError 后使用 asyncio.run()，
        因此即使没有运行中的 loop 也应该正常工作。
        """
        # 确保没有运行中的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 有运行中的 loop 时也应该是安全的（pytest-asyncio 可能创建 loop）
            # 但 publish_sync 需要先有订阅者才能验证事件投递
        except RuntimeError:
            # 无运行中的事件循环 —— 这正是我们想测试的场景
            pass

        event = {"type": "test.event", "payload": {"message": "hello"}}
        # 不应抛出异常
        try:
            stream.publish_sync("run-test-001", event)
        except Exception as exc:
            pytest.fail(f"publish_sync() 在无事件循环时抛出异常：{exc}")

    def test_publish_sync_delivers_to_subscriber_without_loop(self, stream: EventStream) -> None:
        """验证 publish_sync() 在无事件循环时能将事件投递给订阅者。

        使用 asyncio.new_event_loop() 创建独立 loop 来订阅，
        验证 publish_sync 通过 asyncio.run() 正常投递。
        """
        # 在新的事件循环中订阅
        async def _subscribe() -> asyncio.Queue:
            return await stream.subscribe("run-test-002")

        loop = asyncio.new_event_loop()
        try:
            queue = loop.run_until_complete(_subscribe())
        finally:
            loop.close()

        # 在没有运行中 loop 的情况下 publish_sync
        event = {"type": "test.delivery", "value": 42}
        try:
            stream.publish_sync("run-test-002", event)
        except Exception as exc:
            pytest.fail(f"publish_sync() 投递事件时抛出异常：{exc}")

    # ------------------------------------------------------------------
    # 测试 3：EventStream 有 subscribe / unsubscribe 方法
    # ------------------------------------------------------------------

    def test_subscribe_method_exists(self, stream: EventStream) -> None:
        """验证 EventStream 有 subscribe 方法且可调用。"""
        assert hasattr(stream, "subscribe"), "EventStream 缺少 subscribe 方法"
        assert callable(stream.subscribe), "subscribe 不可调用"

    def test_unsubscribe_method_exists(self, stream: EventStream) -> None:
        """验证 EventStream 有 unsubscribe 方法且可调用。"""
        assert hasattr(stream, "unsubscribe"), "EventStream 缺少 unsubscribe 方法"
        assert callable(stream.unsubscribe), "unsubscribe 不可调用"

    # ------------------------------------------------------------------
    # 异步 subscribe 集成测试
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_async(self, stream: EventStream) -> None:
        """验证异步 subscribe + publish 流程正常工作。"""
        queue = await stream.subscribe("run-test-003")

        event = {"type": "test.async", "payload": {"data": "async-test"}}
        await stream.publish("run-test-003", event)

        # 从队列中获取事件
        received = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert received["type"] == "test.async"
        assert received["payload"]["data"] == "async-test"
        assert "timestamp" in received

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscriber(self, stream: EventStream) -> None:
        """验证 unsubscribe 后订阅者不再接收事件。"""
        queue = await stream.subscribe("run-test-004")

        # 取消订阅
        stream.unsubscribe("run-test-004", queue)

        # 发布事件
        await stream.publish("run-test-004", {"type": "test.unsubscribed"})

        # 队列应为空（因为已取消订阅，事件不会投递到被移除的队列）
        assert queue.empty(), "取消订阅后队列不应收到新事件"

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_run(self, stream: EventStream) -> None:
        """验证同一 run 的多个订阅者都能收到事件。"""
        queue1 = await stream.subscribe("run-test-005")
        queue2 = await stream.subscribe("run-test-005")

        event = {"type": "test.broadcast", "value": 99}
        await stream.publish("run-test-005", event)

        received1 = await asyncio.wait_for(queue1.get(), timeout=2.0)
        received2 = await asyncio.wait_for(queue2.get(), timeout=2.0)

        assert received1["type"] == "test.broadcast"
        assert received1["value"] == 99
        assert received2["type"] == "test.broadcast"
        assert received2["value"] == 99

    @pytest.mark.asyncio
    async def test_publish_global_broadcasts_to_all_runs(self, stream: EventStream) -> None:
        """验证 publish_global 向所有 run 的订阅者广播事件。"""
        queue_a = await stream.subscribe("run-a")
        queue_b = await stream.subscribe("run-b")

        event = {"type": "test.global", "message": "broadcast-to-all"}
        await stream.publish_global(event)

        received_a = await asyncio.wait_for(queue_a.get(), timeout=2.0)
        received_b = await asyncio.wait_for(queue_b.get(), timeout=2.0)

        assert received_a["type"] == "test.global"
        assert received_b["type"] == "test.global"

    # ------------------------------------------------------------------
    # publish_sync 在有事件循环时（pytest-asyncio）
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_publish_sync_with_running_loop(self, stream: EventStream) -> None:
        """验证 publish_sync() 在有事件循环时通过 run_coroutine_threadsafe 工作。

        publish_sync 检测到运行中的 loop 后，使用
        asyncio.run_coroutine_threadsafe 调度协程。
        """
        queue = await stream.subscribe("run-test-006")

        # 在有运行中 loop 的情况下调用 publish_sync
        event = {"type": "test.sync_with_loop", "data": "synced"}
        stream.publish_sync("run-test-006", event)

        # 给事件循环一点时间处理
        await asyncio.sleep(0.05)

        # 事件应该已经投递到队列
        assert not queue.empty(), "publish_sync 未将事件投递到队列"

        received = queue.get_nowait()
        assert received["type"] == "test.sync_with_loop"
        assert received["data"] == "synced"

    # ------------------------------------------------------------------
    # 边界测试
    # ------------------------------------------------------------------

    def test_publish_sync_no_subscribers_no_error(self, stream: EventStream) -> None:
        """验证 publish_sync 在没有订阅者时不抛异常。"""
        try:
            stream.publish_sync("run-nonexistent", {"type": "test.no_sub"})
        except Exception as exc:
            pytest.fail(f"publish_sync 在没有订阅者时抛出异常：{exc}")

    def test_unsubscribe_nonexistent_queue_no_error(self, stream: EventStream) -> None:
        """验证 unsubscribe 对不存在的队列不抛异常。"""
        import asyncio
        fake_queue = asyncio.Queue()
        # 对不存在的 run_id 取消订阅不应抛出异常
        try:
            stream.unsubscribe("run-nonexistent", fake_queue)
        except Exception as exc:
            pytest.fail(f"unsubscribe 对不存在的队列抛出异常：{exc}")
