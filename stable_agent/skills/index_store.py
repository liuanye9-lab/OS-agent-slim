"""stable_agent/skills/index_store.py — SQLite 索引存储。

为 SkillRepository 提供 SQLite 索引层。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class SkillIndexStore:
    """SQLite 索引存储。"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表。"""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    skill_id TEXT PRIMARY KEY,
                    version INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'draft',
                    domain TEXT DEFAULT 'general',
                    owner TEXT DEFAULT '',
                    risk_level TEXT DEFAULT 'low',
                    path TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    validations INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    avg_token_delta REAL DEFAULT 0.0,
                    avg_latency_delta REAL DEFAULT 0.0,
                    last_validation_score REAL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_tags (
                    skill_id TEXT,
                    tag TEXT,
                    PRIMARY KEY (skill_id, tag)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_sources (
                    skill_id TEXT,
                    run_id TEXT,
                    PRIMARY KEY (skill_id, run_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS promotion_log (
                    id TEXT PRIMARY KEY,
                    skill_id TEXT,
                    from_status TEXT,
                    to_status TEXT,
                    reason TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def upsert_skill(self, record: Any) -> None:
        """插入或更新 skill 记录。"""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO skills (
                    skill_id, version, status, domain, owner, risk_level, path,
                    created_at, updated_at, validations, win_rate,
                    avg_token_delta, avg_latency_delta, last_validation_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.skill_id,
                record.version,
                record.status.value if hasattr(record.status, 'value') else str(record.status),
                record.domain,
                record.owner,
                record.risk_level,
                record.path,
                record.created_at,
                record.updated_at,
                record.metrics.get("validations", 0),
                record.metrics.get("win_rate", 0.0),
                record.metrics.get("avg_token_delta", 0.0),
                record.metrics.get("avg_latency_delta", 0.0),
                record.metrics.get("last_validation_score", 0.0),
            ))

            # 更新标签
            conn.execute("DELETE FROM skill_tags WHERE skill_id = ?", (record.skill_id,))
            for tag in record.retrieval_tags:
                conn.execute("INSERT OR IGNORE INTO skill_tags (skill_id, tag) VALUES (?, ?)",
                             (record.skill_id, tag))

            # 更新来源
            conn.execute("DELETE FROM skill_sources WHERE skill_id = ?", (record.skill_id,))
            for run_id in record.source_runs:
                conn.execute("INSERT OR IGNORE INTO skill_sources (skill_id, run_id) VALUES (?, ?)",
                             (record.skill_id, run_id))

            conn.commit()
        finally:
            conn.close()

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        """获取 skill 记录。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有 skills。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM skills ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        """按状态列出 skills。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM skills WHERE status = ? ORDER BY updated_at DESC",
                (status,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_skill(self, skill_id: str) -> bool:
        """删除 skill 记录。"""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("DELETE FROM skills WHERE skill_id = ?", (skill_id,))
            conn.execute("DELETE FROM skill_tags WHERE skill_id = ?", (skill_id,))
            conn.execute("DELETE FROM skill_sources WHERE skill_id = ?", (skill_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_skills_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """按标签检索 skills。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT s.* FROM skills s
                JOIN skill_tags t ON s.skill_id = t.skill_id
                WHERE t.tag = ?
                ORDER BY s.updated_at DESC
            """, (tag,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
