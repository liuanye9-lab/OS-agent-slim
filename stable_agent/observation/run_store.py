"""RunStore — 按 run_id 索引的运行时存储。

提供内存中的运行存储，支持按 run_id 创建、追加事件、查询状态。
可从外部 TraceStorage 回放历史数据。

用法::

    store = RunStore()
    store.create_run("run-001")
    store.append_event("run-001", {"type": "task.started", "data": {}})
    events = store.get_events("run-001")
"""

from __future__ import annotations

import time
from typing import Any


class RunStore:
    """按 run_id 索引的运行时存储。

    在内存中维护所有活跃运行的事件流，支持从 TraceStorage 回放历史数据。
    每个 run 记录包含事件列表、开始时间戳和运行状态。

    Attributes:
        _runs: 内部存储字典，run_id → {events, started_at, status}。
    """

    def __init__(self, trace_storage: Any = None) -> None:
        """初始化 RunStore。

        Args:
            trace_storage: 可选的 TraceStorage 实例，用于回放历史 run 数据。
        """
        self._runs: dict[str, dict[str, Any]] = {}
        self._trace_storage = trace_storage

    def create_run(self, run_id: str) -> None:
        """注册一个新 run。

        如果 run_id 已存在，则不执行任何操作（幂等）。

        Args:
            run_id: 运行唯一标识。
        """
        if run_id not in self._runs:
            self._runs[run_id] = {
                "events": [],
                "started_at": time.time(),
                "status": "running",
            }

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        """追加事件到指定 run。

        如果 run_id 不存在，会自动创建该 run。

        Args:
            run_id: 运行唯一标识。
            event: 事件字典，应至少包含 type 和 timestamp 字段。
        """
        if run_id not in self._runs:
            self.create_run(run_id)
        # 确保事件有 timestamp
        if "timestamp" not in event:
            event = dict(event)  # 避免修改调用方传入的字典
            event["timestamp"] = time.time()
        self._runs[run_id]["events"].append(event)

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        """获取指定 run 的所有事件。

        Args:
            run_id: 运行唯一标识。

        Returns:
            事件列表。如果 run_id 不存在，返回空列表。
        """
        if run_id not in self._runs:
            return []
        return list(self._runs[run_id]["events"])

    def get_run_status(self, run_id: str) -> dict[str, Any] | None:
        """获取 run 状态摘要。

        Args:
            run_id: 运行唯一标识。

        Returns:
            包含 run_id、status、event_count、started_at 的字典。
            如果 run_id 不存在，返回 None。
        """
        if run_id not in self._runs:
            return None
        run = self._runs[run_id]
        return {
            "run_id": run_id,
            "status": run["status"],
            "event_count": len(run["events"]),
            "started_at": run["started_at"],
        }

    def list_active_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出活跃 runs。

        按 started_at 倒序排列，返回最近启动的 runs。

        Args:
            limit: 最大返回数量，默认 20。

        Returns:
            活跃 run 的状态摘要列表。
        """
        active = []
        for run_id, run in self._runs.items():
            if run["status"] == "running":
                active.append({
                    "run_id": run_id,
                    "status": run["status"],
                    "event_count": len(run["events"]),
                    "started_at": run["started_at"],
                })
        # 按 started_at 倒序
        active.sort(key=lambda r: r["started_at"], reverse=True)
        return active[:limit]

    def mark_completed(self, run_id: str) -> None:
        """将 run 标记为已完成。

        Args:
            run_id: 运行唯一标识。如果不存在则静默忽略。
        """
        if run_id in self._runs:
            self._runs[run_id]["status"] = "completed"

    def mark_failed(self, run_id: str) -> None:
        """将 run 标记为失败。

        Args:
            run_id: 运行唯一标识。如果不存在则静默忽略。
        """
        if run_id in self._runs:
            self._runs[run_id]["status"] = "failed"
