"""EventStream — 按 run_id 管理的异步事件流。

每个 run 拥有独立的异步队列，支持多订阅者并发订阅。
发布者通过 publish() 向指定 run 推送事件，所有订阅者都能接收到。

用法::

    stream = EventStream()
    queue = await stream.subscribe("run-001")
    await stream.publish("run-001", {"type": "task.started"})
    event = await queue.get()
"""

from __future__ import annotations

import asyncio
import time
from typing import Any


class EventStream:
    """按 run_id 管理的异步事件流。

    每个 run_id 维护独立的订阅者队列列表。发布事件时广播到该 run 的所有订阅者。
    支持全局广播事件到所有活跃 run。

    线程安全：所有操作均为协程，应在同一个事件循环中使用。
    """

    def __init__(self) -> None:
        """初始化 EventStream。

        创建空的订阅者字典，key 为 run_id，value 为异步队列列表。
        """
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    async def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        """订阅指定 run 的事件流。

        为调用者创建一个新的异步队列并注册到该 run 的订阅者列表中。
        调用者通过 await queue.get() 消费事件。

        Args:
            run_id: 要订阅的运行标识。

        Returns:
            一个 asyncio.Queue 实例，用于接收该 run 的事件。
        """
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """取消订阅指定 run 的事件流。

        从该 run 的订阅者列表中移除指定的队列。如果移除后该 run
        没有订阅者，则清理其条目。

        Args:
            run_id: 运行标识。
            queue: 要移除的异步队列实例。
        """
        if run_id in self._subscribers:
            queues = self._subscribers[run_id]
            if queue in queues:
                queues.remove(queue)
            if not queues:
                del self._subscribers[run_id]

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """向指定 run 的所有订阅者发布事件。

        事件会自动添加 timestamp（如果未提供）。对于已关闭的订阅者
        队列，将静默跳过（防止 BrokenPipeError）。

        Args:
            run_id: 目标运行标识。
            event: 事件字典，至少应包含 type 字段。
        """
        if "timestamp" not in event:
            event = dict(event)
            event["timestamp"] = time.time()
        if run_id in self._subscribers:
            for queue in self._subscribers[run_id]:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # 队列已满时跳过，避免阻塞发布者
                    pass

    async def publish_global(self, event: dict[str, Any]) -> None:
        """向所有 run 的所有订阅者发布事件。

        用于全局广播（如系统通知、关闭信号等）。

        Args:
            event: 事件字典。
        """
        for run_id in list(self._subscribers.keys()):
            await self.publish(run_id, event)
