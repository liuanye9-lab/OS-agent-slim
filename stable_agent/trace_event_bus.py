"""追踪事件总线 — 事件发布订阅与持久化存储。

本模块是 StableAgent OS 的"神经系统"，提供：
- EventBus: 线程安全的事件发布/订阅机制，是系统中唯一可跨模块共享的单例
- TraceStorage: 事件的 JSONL 持久化存储，支持写入和回读

V3 升级：
- EventBus: 新增 start_span / end_span / get_spans_by_run
- TraceStorage: 新增 save_span / load_spans

事件命名规范：
  task:<action>, workflow:<action>, memory:<action>, eval:<action>, execute:<action>

模块职责：
- 注册/注销事件监听器
- 发布事件并路由到所有订阅者（捕获异常避免级联失败）
- 记录事件历史供查询
- JSONL 持久化事件追踪数据
- TraceSpan 创建/结束/持久化
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Callable

logger = logging.getLogger(__name__)

from stable_agent.models import Event, TraceSpan


# ============================================================================
# EventBus — 事件发布订阅总线（单例语义）
# ============================================================================


class EventBus:
    """事件发布订阅总线。

    支持多个监听器订阅事件，发布时遍历所有监听器并调用。
    每个监听器的异常会被独立捕获，不会影响其他监听器。
    同时将事件记录到内部历史列表中。

    Attributes:
        _listeners: 已注册的事件监听器列表。
        _events: 事件历史记录列表（按时间正序）。
        _spans: Span 记录（按 run_id 分组）。
    """

    def __init__(self) -> None:
        """初始化 EventBus。

        创建空的 listeners 列表、events 历史列表和 spans 字典。
        """
        self._listeners: list[Callable[[Event], None]] = []
        self._events: list[Event] = []
        self._spans: dict[str, list[TraceSpan]] = {}  # run_id → spans

    # ------------------------------------------------------------------
    # 订阅管理
    # ------------------------------------------------------------------

    def subscribe(self, listener: Callable[[Event], None]) -> None:
        """注册事件监听器。

        将 listener 追加到内部监听器列表。同一个 listener 可以被
        多次注册（调用方需自行管理去重）。

        Args:
            listener: 接收 Event 的回调函数，签名为 (Event) -> None。
        """
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[Event], None]) -> None:
        """移除事件监听器。

        从内部监听器列表中移除指定的 listener。若 listener 不存在，
        静默忽略（不抛异常）。

        Args:
            listener: 要移除的回调函数。
        """
        try:
            self._listeners.remove(listener)
        except ValueError:
            # listener 不在列表中，静默忽略
            pass

    # ------------------------------------------------------------------
    # 事件发布
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """发布事件到所有订阅者并记录历史。

        遍历所有已注册的 listener 并调用 listener(event)。
        每个 listener 的异常被独立捕获（try/except），确保一个
        监听器失败不会影响其他监听器。最后调用 record 存储事件。

        Args:
            event: 要发布的 Event 实例。
        """
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                # 捕获所有异常，避免一个 listener 失败影响其他
                logger.debug("事件监听器执行失败: %s", e)

        # 记录事件到历史
        self.record(event)

    def record(self, event: Event) -> None:
        """将事件记录到内部历史列表。

        Args:
            event: 要记录的 Event 实例。
        """
        self._events.append(event)

    # ------------------------------------------------------------------
    # 历史查询
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 100) -> list[Event]:
        """返回最近 limit 条事件（按时间倒序）。

        Args:
            limit: 返回的最大事件数，默认 100。

        Returns:
            按时间戳降序排列的 Event 列表。
        """
        if limit <= 0:
            return []
        # 复制列表避免外部修改，按时间戳降序
        sorted_events: list[Event] = sorted(
            self._events,
            key=lambda e: e.timestamp,
            reverse=True,
        )
        return sorted_events[:limit]

    def clear_history(self) -> None:
        """清空事件历史列表。"""
        self._events.clear()

    # ------------------------------------------------------------------
    # V3 新增: Span API
    # ------------------------------------------------------------------

    def start_span(
        self,
        run_id: str,
        name: str,
        span_type: str,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """创建并开始 TraceSpan，返回 span 对象（started_at 已设置）。

        Args:
            run_id: 运行 ID。
            name: Span 名称。
            span_type: Span 类型（SpanType 枚举值）。
            parent_span_id: 父 Span ID，None 表示根 Span。

        Returns:
            创建的 TraceSpan 实例。

        Examples:
            >>> bus = EventBus()
            >>> span = bus.start_span("run-1", "memory_retrieval", "memory_retrieval")
            >>> span.span_id != ""
            True
            >>> span.status
            'started'
            >>> span.started_at > 0
            True
        """
        span: TraceSpan = TraceSpan(
            span_id=str(uuid.uuid4()),
            run_id=run_id,
            parent_span_id=parent_span_id,
            name=name,
            type=span_type,
            status="started",
            started_at=time.time(),
            ended_at=None,
            latency_ms=None,
        )

        if run_id not in self._spans:
            self._spans[run_id] = []
        self._spans[run_id].append(span)

        return span

    def end_span(
        self,
        span: TraceSpan,
        status: str = "success",
        payload: dict | None = None,
    ) -> None:
        """结束 TraceSpan：设置 ended_at, latency_ms, status, payload。

        Args:
            span: 要结束的 TraceSpan 实例。
            status: 结束状态（SpanStatus 枚举值），默认 "success"。
            payload: 附加数据负载，None 表示不更新。

        Examples:
            >>> bus = EventBus()
            >>> span = bus.start_span("run-1", "test", "execute")
            >>> bus.end_span(span)
            >>> span.status
            'success'
            >>> span.latency_ms is not None
            True
        """
        now: float = time.time()
        span.ended_at = now
        span.status = status
        span.latency_ms = int((now - span.started_at) * 1000)

        if payload is not None:
            span.payload = payload

    # ------------------------------------------------------------------
    # V4 新增: SkillOpt 事件快捷发布
    # ------------------------------------------------------------------

    def publish_skillopt_event(
        self,
        event_type: str,
        detail: dict | None = None,
    ) -> None:
        """发布 V4 SkillOpt 事件的快捷方法。

        event_type 不需要加 skillopt. 前缀，方法自动添加。

        Args:
            event_type: 事件类型（不含 "skillopt." 前缀）。
            detail: 事件负载数据，None 时使用空字典。

        Examples:
            >>> bus = EventBus()
            >>> bus.publish_skillopt_event("epoch_started", {"rollout_count": 12})
        """
        from stable_agent.models import Event

        full_type: str = f"skillopt.{event_type}"
        self.publish(Event(type=full_type, payload=detail or {}))

    def get_spans_by_run(self, run_id: str) -> list[TraceSpan]:
        """按 run_id 查询所有 spans。

        Args:
            run_id: 运行 ID。

        Returns:
            TraceSpan 列表。若无匹配，返回空列表。

        Examples:
            >>> bus = EventBus()
            >>> span = bus.start_span("run-1", "test", "execute")
            >>> spans = bus.get_spans_by_run("run-1")
            >>> len(spans)
            1
        """
        return list(self._spans.get(run_id, []))


# ============================================================================
# TraceStorage — 事件持久化存储
# ============================================================================


class TraceStorage:
    """事件持久化存储。

    使用 JSONL 格式将事件追加写入文件，支持从文件回读。

    Attributes:
        storage_path: JSONL 文件存储路径。
    """

    def __init__(self, storage_path: str = "data/traces.jsonl") -> None:
        """初始化 TraceStorage。

        Args:
            storage_path: JSONL 文件存储路径，默认 "data/traces.jsonl"。
        """
        self.storage_path: str = storage_path

    def save_event(self, event: Event) -> None:
        """将事件以 JSONL 格式追加写入文件。

        实现时用 try/except 包裹全部操作，失败时静默忽略（不中断
        主流程）。自动创建父目录（若不存在）。

        # STUB: 当前为 JSONL 文件追加。未来可迁移到专用时序数据库
        #   如 InfluxDB 或 ClickHouse 以获得更好的查询性能。

        Args:
            event: 要持久化的 Event 实例。
        """
        try:
            # 确保目录存在
            parent_dir: str = os.path.dirname(self.storage_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # 序列化 Event 为 dict
            event_dict: dict = {
                "timestamp": event.timestamp,
                "type": event.type,
                "payload": event.payload,
            }

            # 以追加模式写入 JSONL
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("持久化操作失败，不中断主流程: %s", e)

    def load_events(self, limit: int = 100) -> list[Event]:
        """从文件读取最近 limit 条事件。

        如果文件不存在或读取失败，返回空列表。

        # STUB: 当前按行扫描整个文件，大文件场景应使用索引或
        #   分块读取策略。仅适用于开发和小规模数据。

        Args:
            limit: 返回的最大事件数，默认 100。

        Returns:
            按时间戳降序排列的 Event 列表。
        """
        events: list[Event] = []

        try:
            if not os.path.exists(self.storage_path):
                return events

            with open(self.storage_path, "r", encoding="utf-8") as f:
                lines: list[str] = f.readlines()

            # 取最后 limit 行（最近的事件在文件末尾）
            recent_lines: list[str] = lines[-limit:] if len(lines) > limit else lines

            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data: dict = json.loads(line)
                    event: Event = Event(
                        timestamp=data.get("timestamp", time.time()),
                        type=data.get("type", ""),
                        payload=data.get("payload", {}),
                    )
                    events.append(event)
                except (json.JSONDecodeError, TypeError):
                    # 跳过损坏的行
                    continue

            # 按时间戳降序排序
            events.sort(key=lambda e: e.timestamp, reverse=True)

        except Exception as e:
            # 读取失败返回空列表
            logger.warning("事件加载失败，返回空列表: %s", e)
            return []

        return events

    # ------------------------------------------------------------------
    # V3 新增: Span 持久化
    # ------------------------------------------------------------------

    def save_span(self, span: TraceSpan) -> None:
        """持久化 span 到 JSONL。

        将 TraceSpan 序列化为 JSON 并追加写入 spans JSONL 文件。
        文件名基于 storage_path 生成：data/traces.jsonl → data/spans.jsonl。

        Args:
            span: 要持久化的 TraceSpan 实例。

        Examples:
            >>> storage = TraceStorage("/tmp/test_traces.jsonl")
            >>> span = TraceSpan(span_id="s1", run_id="r1", name="test", type="execute")
            >>> storage.save_span(span)  # 不会抛异常
        """
        try:
            # 生成 spans 文件路径
            spans_dir: str = os.path.dirname(self.storage_path)
            spans_path: str = os.path.join(
                spans_dir if spans_dir else "data",
                "spans.jsonl",
            )

            # 确保目录存在
            if spans_dir and not os.path.exists(spans_dir):
                os.makedirs(spans_dir, exist_ok=True)

            # 序列化
            span_dict: dict = {
                "span_id": span.span_id,
                "run_id": span.run_id,
                "parent_span_id": span.parent_span_id,
                "name": span.name,
                "type": span.type,
                "status": span.status,
                "started_at": span.started_at,
                "ended_at": span.ended_at,
                "latency_ms": span.latency_ms,
                "input_tokens": span.input_tokens,
                "output_tokens": span.output_tokens,
                "cost_estimate": span.cost_estimate,
                "payload": span.payload,
                "plain_text": span.plain_text,
            }

            with open(spans_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(span_dict, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("持久化操作失败，不中断主流程: %s", e)

    def load_spans(
        self, run_id: str, limit: int = 100
    ) -> list[TraceSpan]:
        """从 JSONL 加载指定 run 的 spans。

        读取 spans JSONL 文件，筛选出匹配 run_id 的 spans。

        Args:
            run_id: 运行 ID。
            limit: 返回的最大 span 数，默认 100。

        Returns:
            TraceSpan 列表。文件不存在或读取失败时返回空列表。

        Examples:
            >>> storage = TraceStorage("/tmp/test_traces.jsonl")
            >>> spans = storage.load_spans("nonexistent")
            >>> len(spans)
            0
        """
        spans: list[TraceSpan] = []

        try:
            spans_dir: str = os.path.dirname(self.storage_path)
            spans_path: str = os.path.join(
                spans_dir if spans_dir else "data",
                "spans.jsonl",
            )

            if not os.path.exists(spans_path):
                return spans

            with open(spans_path, "r", encoding="utf-8") as f:
                lines: list[str] = f.readlines()

            # 从后往前读取（最近的 span 在文件末尾）
            recent_lines: list[str] = lines[-limit:] if len(lines) > limit else lines

            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data: dict = json.loads(line)
                    if data.get("run_id", "") != run_id:
                        continue

                    span: TraceSpan = TraceSpan(
                        span_id=data.get("span_id", ""),
                        run_id=data.get("run_id", ""),
                        parent_span_id=data.get("parent_span_id"),
                        name=data.get("name", ""),
                        type=data.get("type", "execute"),
                        status=data.get("status", "started"),
                        started_at=data.get("started_at", time.time()),
                        ended_at=data.get("ended_at"),
                        latency_ms=data.get("latency_ms"),
                        input_tokens=data.get("input_tokens", 0),
                        output_tokens=data.get("output_tokens", 0),
                        cost_estimate=data.get("cost_estimate", 0.0),
                        payload=data.get("payload", {}),
                        plain_text=data.get("plain_text", ""),
                    )
                    spans.append(span)
                except (json.JSONDecodeError, TypeError):
                    continue

            # 按 started_at 降序
            spans.sort(key=lambda s: s.started_at, reverse=True)

        except Exception as e:
            logger.warning("Span 加载失败，返回空列表: %s", e)
            return []

        return spans
