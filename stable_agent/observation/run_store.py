"""RunStore — 按 run_id 索引的运行时存储。

提供内存 + SQLite 双层运行存储，支持按 run_id 创建、追加事件、查询状态。
V11.5: 新增 SQLite 持久化，解决 Observer 0% 问题。

用法::

    store = RunStore()
    store.create_run("run-001")
    store.append_event("run-001", {"type": "task.started", "data": {}})
    events = store.get_events("run-001")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RunStore:
    """按 run_id 索引的运行时存储。

    V11.5: 内存 + SQLite 双层存储。
    - 内存层: 快速读写，用于活跃 run
    - SQLite 层: 持久化，用于页面刷新后回放

    Attributes:
        _runs: 内部存储字典，run_id → {events, started_at, status}。
        _db_path: SQLite 数据库路径 (可选)。
    """

    def __init__(self, trace_storage: Any = None, db_path: str | None = None) -> None:
        """初始化 RunStore。

        Args:
            trace_storage: 可选的 TraceStorage 实例，用于回放历史 run 数据。
            db_path: SQLite 数据库路径 (可选，用于持久化)。
        """
        self._runs: dict[str, dict[str, Any]] = {}
        self._trace_storage = trace_storage
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化 SQLite 数据库 (如果配置了 db_path)。"""
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'running',
                    started_at REAL,
                    updated_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    event_type TEXT,
                    event_data TEXT,
                    timestamp REAL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id)")
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("RunStore SQLite init failed: %s", exc)

    def _persist_run(self, run_id: str) -> None:
        """持久化 run 元数据到 SQLite。"""
        if not self._db_path or run_id not in self._runs:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            run = self._runs[run_id]
            conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, status, started_at, updated_at) VALUES (?, ?, ?, ?)",
                (run_id, run["status"], run["started_at"], time.time())
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("RunStore persist run failed: %s", exc)

    def _persist_event(self, run_id: str, event: dict[str, Any]) -> None:
        """持久化事件到 SQLite。"""
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO events (run_id, event_type, event_data, timestamp) VALUES (?, ?, ?, ?)",
                (run_id, event.get("event_type", ""), json.dumps(event, default=str), event.get("timestamp", time.time()))
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("RunStore persist event failed: %s", exc)

    def _load_events_from_db(self, run_id: str) -> list[dict[str, Any]]:
        """从 SQLite 加载事件 (用于回放)。"""
        if not self._db_path:
            return []
        try:
            conn = sqlite3.connect(self._db_path)
            rows = conn.execute(
                "SELECT event_data FROM events WHERE run_id = ? ORDER BY id",
                (run_id,)
            ).fetchall()
            conn.close()
            events = []
            for row in rows:
                try:
                    events.append(json.loads(row[0]))
                except Exception:
                    pass
            return events
        except Exception:
            return []

    def _load_run_from_db(self, run_id: str) -> dict[str, Any] | None:
        """从 SQLite 加载 run 元数据。"""
        if not self._db_path:
            return None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            conn.close()
            if row:
                return {
                    "status": row["status"],
                    "started_at": row["started_at"],
                }
            return None
        except Exception:
            return None

    def create_run(self, run_id: str) -> None:
        """注册一个新 run。

        如果 run_id 已存在，则不执行任何操作（幂等）。
        V11.5: 同时持久化到 SQLite。

        Args:
            run_id: 运行唯一标识。
        """
        if run_id not in self._runs:
            self._runs[run_id] = {
                "events": [],
                "started_at": time.time(),
                "status": "running",
            }
            self._persist_run(run_id)

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        """追加事件到指定 run。

        如果 run_id 不存在，会自动创建该 run。
        V11.5: 同时持久化到 SQLite。

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
        self._persist_event(run_id, event)

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        """获取指定 run 的所有事件。

        V11.5: 先查内存，如果为空则从 SQLite 回放。

        Args:
            run_id: 运行唯一标识。

        Returns:
            事件列表。如果 run_id 不存在，返回空列表。
        """
        # 先查内存
        if run_id in self._runs and self._runs[run_id]["events"]:
            return list(self._runs[run_id]["events"])

        # 从 SQLite 回放
        db_events = self._load_events_from_db(run_id)
        if db_events:
            # 回放到内存
            if run_id not in self._runs:
                run_meta = self._load_run_from_db(run_id)
                self._runs[run_id] = {
                    "events": db_events,
                    "started_at": run_meta["started_at"] if run_meta else time.time(),
                    "status": run_meta["status"] if run_meta else "completed",
                }
            else:
                self._runs[run_id]["events"] = db_events
            return db_events

        return []

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

        V11.5: 同时持久化到 SQLite。

        Args:
            run_id: 运行唯一标识。如果不存在则静默忽略。
        """
        if run_id in self._runs:
            self._runs[run_id]["status"] = "completed"
            self._persist_run(run_id)

    def mark_failed(self, run_id: str) -> None:
        """将 run 标记为失败。

        V11.5: 同时持久化到 SQLite。

        Args:
            run_id: 运行唯一标识。如果不存在则静默忽略。
        """
        if run_id in self._runs:
            self._runs[run_id]["status"] = "failed"
            self._persist_run(run_id)
