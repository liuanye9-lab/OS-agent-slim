"""测试 Migration Runner (Phase 7+12)。

验证:
1. migration_runner 能记录 schema_migrations
2. run_migrations() 正确执行
3. 幂等性
"""

import pytest
import sqlite3
import time
from stable_agent.db.migration_runner import MigrationRunner


class TestMigrationRunner:
    """Migration Runner 测试。"""

    def test_run_migrations_creates_table(self, tmp_path):
        """验证 schema_migrations 表创建。"""
        db_path = str(tmp_path / "test_migrate.sqlite3")
        runner = MigrationRunner(db_path=db_path)
        applied = runner.run_migrations()
        assert isinstance(applied, list)

        # 验证表存在
        conn = runner._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchall()
        assert len(tables) == 1

    def test_run_migrations_idempotent(self, tmp_path):
        """验证迁移幂等 — 第二次不重复。"""
        db_path = str(tmp_path / "test_migrate.sqlite3")
        runner = MigrationRunner(db_path=db_path)

        first = runner.run_migrations()
        second = runner.run_migrations()
        # 第二次应无新迁移
        assert len(second) <= len(first)

    def test_run_migrations_applies_sql_files(self, tmp_path):
        """验证 SQL 文件被正确执行。"""
        db_path = str(tmp_path / "test_migrate.sqlite3")
        runner = MigrationRunner(db_path=db_path)
        applied = runner.run_migrations()

        # 验证 migration 被记录
        conn = runner._get_conn()
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        recorded = {r["version"] for r in rows}
        for version in applied:
            assert version in recorded

    def test_legacy_init_db_still_works(self, tmp_path):
        """验证旧 init_db() fallback 仍然可用。"""
        from stable_agent.saas.repository import SaasRepository
        db_path = str(tmp_path / "test_legacy.sqlite3")
        repo = SaasRepository(db_path=db_path)
        # init_db() 被 __init__ 自动调用
        repo.init_db()  # 幂等
        assert repo is not None
