"""stable_agent.cloud.task_queue — 任务队列。

SQLite 后端，管理任务的完整生命周期。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

TaskStatus = Literal["queued", "assigned", "running", "completed", "failed", "cancelled"]


@dataclass
class TaskRecord:
    """任务记录。"""

    task_id: str = ""
    run_id: str = ""
    title: str = ""
    task_input: str = ""
    status: str = "queued"
    priority: int = 5
    assigned_worker_id: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    result: Optional[str] = None
    error: Optional[str] = None
    source: str = "mcp"
    logs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = f"task_{uuid.uuid4().hex[:12]}"
        if not self.run_id:
            self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.updated_at == 0.0:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "title": self.title,
            "task_input": self.task_input,
            "status": self.status,
            "priority": self.priority,
            "assigned_worker_id": self.assigned_worker_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
            "source": self.source,
            "log_count": len(self.logs),
        }


class TaskQueue:
    """任务队列，SQLite 后端。"""

    def __init__(self, db_path: str = ".stableagent-capsule/cloud/cloud.sqlite",
                 max_logs_per_task: int = 200) -> None:
        self.db_path = db_path
        self.max_logs = max_logs_per_task
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
            CREATE TABLE IF NOT EXISTS cloud_tasks (
                task_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                task_input TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 5,
                assigned_worker_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                result TEXT,
                error TEXT,
                source TEXT NOT NULL DEFAULT 'mcp'
            );
            CREATE TABLE IF NOT EXISTS cloud_task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                log_entry TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON cloud_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_worker ON cloud_tasks(assigned_worker_id);
            CREATE INDEX IF NOT EXISTS idx_logs_task ON cloud_task_logs(task_id);
        """)
        self._conn.commit()

    def create_task(self, task_input: str, title: str = "",
                    priority: int = 5, worker_id: Optional[str] = None,
                    source: str = "mcp", run_id: str = "") -> TaskRecord:
        """创建任务。"""
        task = TaskRecord(
            task_input=task_input,
            title=title or task_input[:80],
            priority=priority,
            assigned_worker_id=worker_id,
            source=source,
            run_id=run_id or f"run_{uuid.uuid4().hex[:12]}",
        )
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO cloud_tasks
               (task_id, run_id, title, task_input, status, priority,
                assigned_worker_id, created_at, updated_at, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task.task_id, task.run_id, task.title, task.task_input,
             task.status, task.priority, task.assigned_worker_id,
             task.created_at, task.updated_at, task.source),
        )
        conn.commit()
        logger.info("Task created: %s (priority=%d)", task.task_id, task.priority)
        return task

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """获取任务。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM cloud_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        task = self._row_to_task(row)
        task.logs = self._get_logs(task_id)
        return task

    def list_tasks(self, status: Optional[str] = None,
                   worker_id: Optional[str] = None,
                   limit: int = 50) -> list[TaskRecord]:
        """列出任务。"""
        conn = self._get_conn()
        query = "SELECT * FROM cloud_tasks WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if worker_id:
            query += " AND assigned_worker_id = ?"
            params.append(worker_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(r) for r in rows]

    def update_status(self, task_id: str, status: str,
                      result: Optional[str] = None,
                      error: Optional[str] = None) -> bool:
        """更新任务状态。"""
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            """UPDATE cloud_tasks SET status=?, result=?, error=?, updated_at=?
               WHERE task_id=?""",
            (status, result, error, now, task_id),
        )
        conn.commit()
        return True

    def assign_task(self, task_id: str, worker_id: str) -> bool:
        """分配任务给 worker。"""
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            """UPDATE cloud_tasks SET status='assigned', assigned_worker_id=?,
               updated_at=? WHERE task_id=? AND status='queued'""",
            (worker_id, now, task_id),
        )
        conn.commit()
        return True

    def append_log(self, task_id: str, message: str) -> None:
        """追加日志。"""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO cloud_task_logs (task_id, log_entry, timestamp) VALUES (?, ?, ?)",
            (task_id, message, time.time()),
        )
        # 裁剪旧日志
        conn.execute(
            """DELETE FROM cloud_task_logs WHERE id NOT IN (
                   SELECT id FROM cloud_task_logs WHERE task_id = ?
                   ORDER BY timestamp DESC LIMIT ?
               )""",
            (task_id, self.max_logs),
        )
        conn.commit()

    def get_queued_tasks(self, limit: int = 10) -> list[TaskRecord]:
        """获取待分配任务。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM cloud_tasks WHERE status='queued' "
            "ORDER BY priority ASC, created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_worker_tasks(self, worker_id: str) -> list[TaskRecord]:
        """获取 worker 当前活跃任务。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM cloud_tasks WHERE assigned_worker_id=? "
            "AND status IN ('assigned', 'running') ORDER BY created_at DESC",
            (worker_id,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def _get_logs(self, task_id: str) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT log_entry FROM cloud_task_logs WHERE task_id=? "
            "ORDER BY timestamp DESC LIMIT ?",
            (task_id, self.max_logs),
        ).fetchall()
        return [r["log_entry"] for r in reversed(rows)]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            run_id=row["run_id"],
            title=row["title"],
            task_input=row["task_input"],
            status=row["status"],
            priority=row["priority"],
            assigned_worker_id=row["assigned_worker_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            result=row["result"],
            error=row["error"],
            source=row["source"],
        )
