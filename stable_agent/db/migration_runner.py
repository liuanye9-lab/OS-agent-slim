"""Database Migration Runner (Commercial SaaS P0)。

替代无限堆叠 ALTER TABLE，用版本号追踪迁移状态。
兼容旧 init_db() 作为 legacy fallback。

用法::

    runner = MigrationRunner(db_path="data/stable_agent.sqlite3")
    runner.run_migrations()
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR: str = os.path.join(os.path.dirname(__file__), "migrations")


class MigrationRunner:
    """数据库迁移执行器。

    按版本号顺序执行 SQL 迁移文件，记录 schema_migrations 表。
    迁移失败必须报错（不静默跳过）。

    Attributes:
        db_path: SQLite 数据库路径。
        conn: 数据库连接。
    """

    def __init__(self, db_path: str = "data/stable_agent.sqlite3") -> None:
        self.db_path: str = db_path
        self.conn: sqlite3.Connection | None = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
        return self.conn

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def run_migrations(self) -> list[str]:
        """执行全部未应用的迁移。

        Returns:
            已应用的迁移版本列表。

        Raises:
            RuntimeError: 迁移执行失败。
        """
        conn = self._get_conn()
        applied: list[str] = []

        try:
            # 确保 schema_migrations 表存在
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "    version TEXT PRIMARY KEY,"
                "    applied_at REAL NOT NULL"
                ")"
            )

            # 获取已应用的版本
            existing = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}

            # 按文件名排序查找迁移文件
            if not os.path.isdir(MIGRATIONS_DIR):
                logger.warning("迁移目录不存在: %s", MIGRATIONS_DIR)
                return applied

            migration_files = sorted(
                [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")]
            )

            for filename in migration_files:
                version = filename.replace(".sql", "")
                if version in existing:
                    continue

                # 执行迁移
                logger.info("应用迁移: %s", version)
                filepath = os.path.join(MIGRATIONS_DIR, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    sql = f.read()

                try:
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, time.time()),
                    )
                    conn.commit()
                    applied.append(version)
                    logger.info("迁移成功: %s", version)
                except Exception as exc:
                    conn.rollback()
                    raise RuntimeError(f"迁移失败 {version}: {exc}") from exc

        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"迁移系统初始化失败: {exc}") from exc

        return applied

    def get_status(self) -> list[dict[str, object]]:
        """获取迁移状态列表。

        Returns:
            [{"version": "0001_initial_saas", "applied_at": 1234567890.0}, ...]
        """
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT version, applied_at FROM schema_migrations ORDER BY version"
            ).fetchall()
            return [{"version": r["version"], "applied_at": r["applied_at"]} for r in rows]
        except Exception:
            return []

    def is_migrated(self) -> bool:
        """检查是否至少执行过一次迁移。"""
        status = self.get_status()
        return len(status) > 0
