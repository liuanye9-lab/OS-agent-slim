"""Approval PendingToolStore — 高风险工具等待审批时的持久化存储。

保存被阻断的工具调用，待审批后恢复执行。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingToolCall:
    """等待审批的工具调用。"""

    approval_id: str
    run_id: str
    tool_name: str
    args: dict[str, Any]
    workspace_id: str = ""
    project_id: str = ""
    created_at: float = field(default_factory=time.time)
    status: str = "waiting_approval"  # waiting_approval | approved | rejected


class PendingToolStore:
    """内存 + SQLite 双层存储的高风险工具待审批队列。"""

    def __init__(self, db_path: str = "data/stable_agent.sqlite3") -> None:
        self._db_path: str = db_path
        self._memory: dict[str, PendingToolCall] = {}
        self._init_table()

    def _init_table(self) -> None:
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_pending_calls (
                    approval_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL DEFAULT '{}',
                    workspace_id TEXT DEFAULT '',
                    project_id TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'waiting_approval'
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_apc_run_id ON approval_pending_calls(run_id)"
            )
            conn.commit()
            conn.close()
        except Exception:
            import logging
            logging.getLogger(__name__).debug("PendingToolStore._init_table failed (non-critical)")

    def save(self, call: PendingToolCall) -> None:
        self._memory[call.approval_id] = call
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO approval_pending_calls "
                "(approval_id, run_id, tool_name, args_json, workspace_id, project_id, created_at, status) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    call.approval_id,
                    call.run_id,
                    call.tool_name,
                    json.dumps(call.args, ensure_ascii=False),
                    call.workspace_id,
                    call.project_id,
                    call.created_at,
                    call.status,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("PendingToolStore.save failed: %s", e)

    def get(self, approval_id: str) -> PendingToolCall | None:
        if approval_id in self._memory:
            return self._memory[approval_id]
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM approval_pending_calls WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            conn.close()
            if row is None:
                return None
            call = PendingToolCall(
                approval_id=row["approval_id"],
                run_id=row["run_id"],
                tool_name=row["tool_name"],
                args=json.loads(row["args_json"]),
                workspace_id=row["workspace_id"] or "",
                project_id=row["project_id"] or "",
                created_at=row["created_at"],
                status=row["status"],
            )
            self._memory[approval_id] = call
            return call
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("PendingToolStore.get failed: %s", e)
            return None

    def mark_approved(self, approval_id: str) -> bool:
        call = self.get(approval_id)
        if call is None:
            return False
        call.status = "approved"
        self._update_status(approval_id, "approved")
        return True

    def mark_rejected(self, approval_id: str) -> bool:
        call = self.get(approval_id)
        if call is None:
            return False
        call.status = "rejected"
        self._update_status(approval_id, "rejected")
        return True

    def _update_status(self, approval_id: str, status: str) -> None:
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE approval_pending_calls SET status=? WHERE approval_id=?",
                (status, approval_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("PendingToolStore._update_status failed: %s", e)

    def list_by_run(self, run_id: str) -> list[PendingToolCall]:
        results: list[PendingToolCall] = []
        for call in self._memory.values():
            if call.run_id == run_id:
                results.append(call)
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM approval_pending_calls WHERE run_id=? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
            conn.close()
            for row in rows:
                if row["approval_id"] not in self._memory:
                    results.append(PendingToolCall(
                        approval_id=row["approval_id"],
                        run_id=row["run_id"],
                        tool_name=row["tool_name"],
                        args=json.loads(row["args_json"]),
                        workspace_id=row["workspace_id"] or "",
                        project_id=row["project_id"] or "",
                        created_at=row["created_at"],
                        status=row["status"],
                    ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("PendingToolStore.list_by_run failed: %s", e)
        return results

    def list_all(self) -> list[PendingToolCall]:
        """列出所有等待审批的调用（最近 50 条）。"""
        results: list[PendingToolCall] = list(self._memory.values())
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM approval_pending_calls WHERE status='waiting_approval' "
                "ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            conn.close()
            known = {c.approval_id for c in results}
            for row in rows:
                if row["approval_id"] not in known:
                    results.append(PendingToolCall(
                        approval_id=row["approval_id"],
                        run_id=row["run_id"],
                        tool_name=row["tool_name"],
                        args=json.loads(row["args_json"]),
                        workspace_id=row["workspace_id"] or "",
                        project_id=row["project_id"] or "",
                        created_at=row["created_at"],
                        status=row["status"],
                    ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("PendingToolStore.list_all failed: %s", e)
        return results
