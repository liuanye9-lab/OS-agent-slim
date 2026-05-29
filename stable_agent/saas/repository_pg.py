"""PostgreSQL Repository — 生产级数据库访问层。

与 SaasRepository (SQLite) 接口兼容，通过 STABLE_AGENT_DB 环境变量自动切换。

用法:
    export STABLE_AGENT_DB=postgres
    export DATABASE_URL=postgresql://user:pass@localhost:5432/stableagent
    python web/server.py

切换逻辑:
    from stable_agent.saas.repository_pg import get_repository
    repo = get_repository()  # 自动根据 STABLE_AGENT_DB 选择 SQLite 或 PG
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from stable_agent.saas.models import (
    AgentRun, ApiKeyRecord, AuditLogRecord, BadCaseRecord,
    BillingPlanRecord, EvalResultRecord, HumanReviewRecord,
    Project, RegressionCaseRecord, SkillPatchRecord,
    SkillRecord, SkillVersionRecord, TraceEventRecord,
    UsageEventRecord, ValidationRunRecord, Workspace,
    WorkspaceMember,
)
from stable_agent.saas.errors import RepositoryError, NotFoundError

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://stableagent:stableagent@localhost:5432/stableagent",
)


class PostgresRepository:
    """PostgreSQL 数据访问层。

    与 SaasRepository 接口兼容，用于生产环境。
    使用 psycopg2 连接池管理连接。

    Attributes:
        dsn: PostgreSQL 连接字符串。
        pool: 连接池实例。
    """

    def __init__(self, dsn: str = "") -> None:
        self.dsn: str = dsn or DATABASE_URL
        self._pool = None

    def _get_conn(self):
        """获取数据库连接（懒初始化连接池）。"""
        if self._pool is None:
            try:
                import psycopg2.pool
                self._pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20, self.dsn,
                )
                logger.info("PostgreSQL 连接池已创建")
            except ImportError:
                raise RepositoryError(
                    "PostgreSQL 需要 psycopg2 库: pip install psycopg2-binary",
                    details={"dsn": self.dsn[:50] + "..."},
                )
            except Exception as e:
                raise RepositoryError(
                    f"PostgreSQL 连接失败: {e}",
                    details={"dsn": self.dsn[:50] + "..."},
                ) from e

        try:
            return self._pool.getconn()
        except Exception as e:
            raise RepositoryError(f"获取连接失败: {e}") from e

    def _put_conn(self, conn) -> None:
        """归还连接到池。"""
        if self._pool:
            self._pool.putconn(conn)

    def close(self) -> None:
        """关闭所有连接。"""
        if self._pool:
            self._pool.closeall()
            self._pool = None

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """创建所有表（幂等）。"""
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            # 使用 PostgreSQL 兼容的 SQL
            tables_sql = """
            CREATE TABLE IF NOT EXISTS workspaces (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(255) DEFAULT '',
                owner_user_id VARCHAR(64) DEFAULT '',
                billing_plan VARCHAR(32) DEFAULT 'free',
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION,
                settings JSONB DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT DEFAULT '',
                default_agent_id VARCHAR(64) DEFAULT '',
                environment VARCHAR(32) DEFAULT 'local',
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64) DEFAULT '',
                agent_id VARCHAR(64) DEFAULT '',
                user_task TEXT DEFAULT '',
                task_type VARCHAR(64) DEFAULT 'general_qa',
                status VARCHAR(32) DEFAULT 'created',
                progress_pct INTEGER DEFAULT 0,
                overall_score DOUBLE PRECISION,
                intent_alignment_score DOUBLE PRECISION,
                token_used INTEGER DEFAULT 0,
                cost_estimate DOUBLE PRECISION DEFAULT 0,
                learning_triggered BOOLEAN DEFAULT FALSE,
                skill_updated BOOLEAN DEFAULT FALSE,
                dashboard_url VARCHAR(512) DEFAULT '',
                trace_url VARCHAR(512) DEFAULT '',
                failure_attribution JSONB DEFAULT '{}',
                metadata JSONB DEFAULT '{}',
                started_at DOUBLE PRECISION,
                ended_at DOUBLE PRECISION
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64),
                name VARCHAR(255) DEFAULT '',
                key_hash VARCHAR(128) NOT NULL,
                key_prefix VARCHAR(8) DEFAULT 'sk_',
                scopes JSONB DEFAULT '[]',
                status VARCHAR(16) DEFAULT 'active',
                last_used_at DOUBLE PRECISION,
                created_at DOUBLE PRECISION NOT NULL,
                revoked_at DOUBLE PRECISION
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64) DEFAULT '',
                event_type VARCHAR(64) NOT NULL,
                actor VARCHAR(128) DEFAULT '',
                target VARCHAR(256) DEFAULT '',
                details JSONB DEFAULT '{}',
                ip_address VARCHAR(64) DEFAULT '',
                user_agent VARCHAR(512) DEFAULT '',
                severity VARCHAR(16) DEFAULT 'info',
                created_at DOUBLE PRECISION NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usage_events (
                id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64) DEFAULT '',
                run_id VARCHAR(64) DEFAULT '',
                event_type VARCHAR(64) DEFAULT '',
                tokens_used INTEGER DEFAULT 0,
                cost_estimate DOUBLE PRECISION DEFAULT 0,
                metadata JSONB DEFAULT '{}',
                created_at DOUBLE PRECISION NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skill_patches (
                id VARCHAR(64) PRIMARY KEY,
                skill_id VARCHAR(64) DEFAULT '',
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64) DEFAULT '',
                source_run_id VARCHAR(64) DEFAULT '',
                from_version VARCHAR(32) DEFAULT '',
                to_version VARCHAR(32) DEFAULT '',
                patch_type VARCHAR(32) DEFAULT 'prompt',
                patch_diff TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                old_score DOUBLE PRECISION DEFAULT 0,
                new_score DOUBLE PRECISION DEFAULT 0,
                delta DOUBLE PRECISION DEFAULT 0,
                status VARCHAR(32) DEFAULT 'candidate',
                validation_run_id VARCHAR(64) DEFAULT '',
                human_review_id VARCHAR(64) DEFAULT '',
                proposed_by VARCHAR(64) DEFAULT 'system',
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION
            );

            CREATE TABLE IF NOT EXISTS human_reviews (
                id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64) DEFAULT '',
                target_type VARCHAR(32) DEFAULT '',
                target_id VARCHAR(64) DEFAULT '',
                reviewer VARCHAR(128) DEFAULT '',
                status VARCHAR(16) DEFAULT 'pending',
                comment TEXT DEFAULT '',
                created_at DOUBLE PRECISION NOT NULL,
                resolved_at DOUBLE PRECISION
            );

            CREATE TABLE IF NOT EXISTS regression_cases (
                id VARCHAR(64) PRIMARY KEY,
                workspace_id VARCHAR(64) DEFAULT '',
                project_id VARCHAR(64) DEFAULT '',
                task_input TEXT DEFAULT '',
                expected_behavior TEXT DEFAULT '',
                failure_mode VARCHAR(64) DEFAULT 'unknown',
                source_run_id VARCHAR(64) DEFAULT '',
                source_bad_case_id VARCHAR(64) DEFAULT '',
                tags JSONB DEFAULT '[]',
                overall_score DOUBLE PRECISION DEFAULT 0,
                created_at DOUBLE PRECISION NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(64) PRIMARY KEY,
                applied_at DOUBLE PRECISION NOT NULL
            );
            """
            cur.execute(tables_sql)
            conn.commit()
            cur.close()
            logger.info("PostgreSQL 表初始化完成")
        except Exception as e:
            conn.rollback()
            logger.exception("init_db 失败: %s", e)
            raise RepositoryError(f"数据库初始化失败: {e}") from e
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def create_workspace(self, ws: Workspace) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO workspaces (id, name, slug, owner_user_id,
                   billing_plan, created_at, updated_at, settings)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (ws.id, ws.name, ws.slug, ws.owner_user_id,
                 ws.billing_plan, ws.created_at, ws.updated_at,
                 json.dumps(ws.settings)),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            conn.rollback()
            logger.exception("create_workspace 失败: %s", e)
            raise RepositoryError(f"创建工作空间失败: {e}") from e
        finally:
            self._put_conn(conn)

    def get_workspace(self, ws_id: str) -> Workspace | None:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM workspaces WHERE id=%s", (ws_id,))
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc[0] for desc in cur.description]
            d = dict(zip(cols, row))
            cur.close()
            return Workspace(
                id=d["id"], name=d["name"], slug=d.get("slug", ""),
                owner_user_id=d.get("owner_user_id", ""),
                billing_plan=d.get("billing_plan", "free"),
                created_at=d["created_at"],
                updated_at=d.get("updated_at") or d["created_at"],
                settings=d.get("settings") if isinstance(d.get("settings"), dict) else json.loads(d.get("settings", "{}")),
            )
        except Exception as e:
            logger.exception("get_workspace 失败: %s", e)
            return None
        finally:
            self._put_conn(conn)

    def list_workspaces(self) -> list[Workspace]:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            cur.close()
            return [
                Workspace(
                    id=dict(zip(cols, r))["id"],
                    name=dict(zip(cols, r))["name"],
                    slug=dict(zip(cols, r)).get("slug", ""),
                    owner_user_id=dict(zip(cols, r)).get("owner_user_id", ""),
                    billing_plan=dict(zip(cols, r)).get("billing_plan", "free"),
                    created_at=dict(zip(cols, r))["created_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.exception("list_workspaces 失败: %s", e)
            return []
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def create_project(self, proj: Project) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO projects (id, workspace_id, name, description,
                   default_agent_id, environment, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (proj.id, proj.workspace_id, proj.name, proj.description,
                 proj.default_agent_id, proj.environment,
                 proj.created_at, proj.updated_at),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            conn.rollback()
            raise RepositoryError(f"创建项目失败: {e}") from e
        finally:
            self._put_conn(conn)

    def get_project(self, proj_id: str) -> Project | None:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM projects WHERE id=%s", (proj_id,))
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc[0] for desc in cur.description]
            d = dict(zip(cols, row))
            cur.close()
            return Project(
                id=d["id"], workspace_id=d["workspace_id"],
                name=d["name"], description=d.get("description", ""),
                default_agent_id=d.get("default_agent_id", ""),
                environment=d.get("environment", "local"),
                created_at=d["created_at"],
                updated_at=d.get("updated_at") or d["created_at"],
            )
        except Exception as e:
            logger.exception("get_project 失败: %s", e)
            return None
        finally:
            self._put_conn(conn)

    def save_run(self, run: AgentRun) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO runs (run_id, workspace_id, project_id, agent_id,
                   user_task, task_type, status, progress_pct,
                   overall_score, token_used, cost_estimate,
                   learning_triggered, skill_updated,
                   dashboard_url, trace_url, failure_attribution, metadata,
                   started_at, ended_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (run_id) DO UPDATE SET
                   status=EXCLUDED.status, progress_pct=EXCLUDED.progress_pct,
                   overall_score=EXCLUDED.overall_score,
                   token_used=EXCLUDED.token_used,
                   ended_at=EXCLUDED.ended_at""",
                (run.run_id, run.workspace_id, run.project_id, run.agent_id,
                 run.user_task, run.task_type, run.status, run.progress_pct,
                 run.overall_score, run.token_used, run.cost_estimate,
                 run.learning_triggered, run.skill_updated,
                 run.dashboard_url, run.trace_url,
                 json.dumps(run.failure_attribution), json.dumps(run.metadata),
                 run.started_at, run.ended_at),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            conn.rollback()
            raise RepositoryError(f"保存 Run 失败: {e}") from e
        finally:
            self._put_conn(conn)

    def save_api_key(self, key: ApiKeyRecord) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO api_keys (id, workspace_id, project_id, name,
                   key_hash, key_prefix, scopes, status, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (key.id, key.workspace_id, key.project_id, key.name,
                 key.key_hash, key.key_prefix,
                 json.dumps(key.scopes), key.status, key.created_at),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            conn.rollback()
            raise RepositoryError(f"保存 API Key 失败: {e}") from e
        finally:
            self._put_conn(conn)

    def save_audit_log(self, log: AuditLogRecord) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO audit_logs (id, workspace_id, project_id,
                   event_type, actor, target, details, severity, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (log.id, log.workspace_id, log.project_id,
                 log.event_type, log.actor, log.target,
                 json.dumps(log.details), log.severity, log.created_at),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            conn.rollback()
            raise RepositoryError(f"保存审计日志失败: {e}") from e
        finally:
            self._put_conn(conn)

    def save_usage_event(self, evt: UsageEventRecord) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO usage_events (id, workspace_id, project_id,
                   run_id, event_type, tokens_used, cost_estimate,
                   metadata, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (evt.id, evt.workspace_id, evt.project_id, evt.run_id,
                 evt.event_type, evt.tokens_used, evt.cost_estimate,
                 json.dumps(evt.metadata), evt.created_at),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            conn.rollback()
            raise RepositoryError(f"保存用量事件失败: {e}") from e
        finally:
            self._put_conn(conn)


# ============================================================================
# Repository 工厂 — 自动切换 SQLite / PostgreSQL
# ============================================================================

def get_repository(db_path: str = "data/stable_agent.sqlite3") -> Any:
    """根据 STABLE_AGENT_DB 环境变量返回对应的 Repository 实例。

    Returns:
        SaasRepository (SQLite) 或 PostgresRepository (PostgreSQL)。
    """
    db_type = os.environ.get("STABLE_AGENT_DB", "sqlite").lower()

    if db_type == "postgres":
        from stable_agent.saas.repository_pg import PostgresRepository
        logger.info("使用 PostgreSQL Repository")
        return PostgresRepository()

    # 默认 SQLite
    from stable_agent.saas.repository import SaasRepository
    return SaasRepository(db_path=db_path)
