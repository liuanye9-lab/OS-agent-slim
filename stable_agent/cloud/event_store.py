"""stable_agent.cloud.event_store — 轻量事件存储。

使用 SQLite 存储 Cloud 级别事件，保留最近 N 条。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EventRecord:
    """Cloud 事件记录。"""

    event_id: str = ""
    run_id: str = ""
    task_id: str = ""
    worker_id: str = ""
    event_type: str = ""
    timestamp: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


class EventStore:
    """轻量事件存储，SQLite 后端。"""

    def __init__(self, db_path: str = ".stableagent-capsule/cloud/cloud.sqlite",
                 max_events: int = 1000) -> None:
        self.db_path = db_path
        self.max_events = max_events
        self._conn: Optional[sqlite3.Connection] = None
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._init_tables()
        return self._conn

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS cloud_events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                worker_id TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL DEFAULT '',
                timestamp REAL NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_events_task ON cloud_events(task_id);
            CREATE INDEX IF NOT EXISTS idx_events_run ON cloud_events(run_id);
            CREATE INDEX IF NOT EXISTS idx_events_type ON cloud_events(event_type);
        """)
        self._conn.commit()

    def append(self, event: EventRecord) -> str:
        """追加事件，超出 max_events 自动裁剪最旧条目。"""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO cloud_events
               (event_id, run_id, task_id, worker_id, event_type, timestamp, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id, event.run_id, event.task_id,
                event.worker_id, event.event_type, event.timestamp,
                json.dumps(event.payload, ensure_ascii=False),
            ),
        )
        # 裁剪旧事件
        conn.execute(
            """DELETE FROM cloud_events WHERE event_id NOT IN (
                   SELECT event_id FROM cloud_events ORDER BY timestamp DESC LIMIT ?
               )""",
            (self.max_events,),
        )
        conn.commit()
        return event.event_id

    def query(self, task_id: str = "", run_id: str = "",
              event_type: str = "", limit: int = 100) -> list[EventRecord]:
        """查询事件。"""
        conn = self._get_conn()
        query = "SELECT * FROM cloud_events WHERE 1=1"
        params: list[Any] = []
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM cloud_events").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            event_id=row["event_id"],
            run_id=row["run_id"],
            task_id=row["task_id"],
            worker_id=row["worker_id"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            payload=json.loads(row["payload"]),
        )
