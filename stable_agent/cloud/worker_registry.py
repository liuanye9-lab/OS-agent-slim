"""stable_agent.cloud.worker_registry — Worker 注册与状态管理。

SQLite 后端，管理 Worker 的注册、心跳、状态。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkerRecord:
    """Worker 记录。"""

    worker_id: str = ""
    name: str = ""
    machine_type: str = "linux"
    status: str = "offline"
    capabilities: list[str] = field(default_factory=list)
    last_heartbeat: float = 0.0
    current_task_id: Optional[str] = None
    registered_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "machine_type": self.machine_type,
            "status": self.status,
            "capabilities": self.capabilities,
            "last_heartbeat": self.last_heartbeat,
            "current_task_id": self.current_task_id,
            "registered_at": self.registered_at,
            "metadata": self.metadata,
        }


class WorkerRegistry:
    """Worker 注册表，SQLite 后端。"""

    def __init__(self, db_path: str = ".stableagent-capsule/cloud/cloud.sqlite",
                 worker_timeout: int = 60) -> None:
        self.db_path = db_path
        self.worker_timeout = worker_timeout
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
            CREATE TABLE IF NOT EXISTS cloud_workers (
                worker_id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                machine_type TEXT NOT NULL DEFAULT 'linux',
                status TEXT NOT NULL DEFAULT 'offline',
                capabilities TEXT NOT NULL DEFAULT '[]',
                last_heartbeat REAL NOT NULL DEFAULT 0,
                current_task_id TEXT,
                registered_at REAL NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}'
            );
        """)
        self._conn.commit()

    def register(self, worker_id: str, name: str = "",
                 machine_type: str = "linux",
                 capabilities: list[str] | None = None) -> WorkerRecord:
        """注册或更新 Worker。"""
        import time as _time
        now = _time.time()
        conn = self._get_conn()
        caps = capabilities or []
        conn.execute(
            """INSERT OR REPLACE INTO cloud_workers
               (worker_id, name, machine_type, status, capabilities,
                last_heartbeat, registered_at, metadata)
               VALUES (?, ?, ?, 'online', ?, ?, ?, '{}')""",
            (worker_id, name or worker_id, machine_type,
             json.dumps(caps), now, now),
        )
        conn.commit()
        logger.info("Worker registered: %s (%s)", worker_id, name)
        return WorkerRecord(
            worker_id=worker_id, name=name or worker_id,
            machine_type=machine_type, status="online",
            capabilities=caps, last_heartbeat=now, registered_at=now,
        )

    def heartbeat(self, worker_id: str) -> bool:
        """更新心跳。"""
        conn = self._get_conn()
        now = time.time()
        result = conn.execute(
            "UPDATE cloud_workers SET last_heartbeat=?, status='online' "
            "WHERE worker_id=?",
            (now, worker_id),
        )
        conn.commit()
        return result.rowcount > 0

    def get_worker(self, worker_id: str) -> Optional[WorkerRecord]:
        """获取 Worker。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM cloud_workers WHERE worker_id = ?", (worker_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_worker(row)

    def list_workers(self, status: Optional[str] = None) -> list[WorkerRecord]:
        """列出 Workers。"""
        conn = self._get_conn()
        query = "SELECT * FROM cloud_workers WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY last_heartbeat DESC"
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_worker(r) for r in rows]

    def get_online_workers(self) -> list[WorkerRecord]:
        """获取在线 Workers。"""
        self._refresh_status()
        return self.list_workers(status="online")

    def set_busy(self, worker_id: str, task_id: str) -> bool:
        """设置 Worker 为忙碌状态。"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE cloud_workers SET status='busy', current_task_id=? "
            "WHERE worker_id=?",
            (task_id, worker_id),
        )
        conn.commit()
        return True

    def set_idle(self, worker_id: str) -> bool:
        """设置 Worker 为空闲状态。"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE cloud_workers SET status='online', current_task_id=NULL "
            "WHERE worker_id=?",
            (worker_id,),
        )
        conn.commit()
        return True

    def _refresh_status(self) -> None:
        """将超时未心跳的 Worker 标记为 offline。"""
        conn = self._get_conn()
        threshold = time.time() - self.worker_timeout
        conn.execute(
            "UPDATE cloud_workers SET status='offline' "
            "WHERE last_heartbeat < ? AND status IN ('online', 'busy')",
            (threshold,),
        )
        conn.commit()

    def online_count(self) -> int:
        self._refresh_status()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM cloud_workers WHERE status IN ('online', 'busy')"
        ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_worker(row: sqlite3.Row) -> WorkerRecord:
        return WorkerRecord(
            worker_id=row["worker_id"],
            name=row["name"],
            machine_type=row["machine_type"],
            status=row["status"],
            capabilities=json.loads(row["capabilities"]),
            last_heartbeat=row["last_heartbeat"],
            current_task_id=row["current_task_id"],
            registered_at=row["registered_at"],
            metadata=json.loads(row["metadata"]),
        )
