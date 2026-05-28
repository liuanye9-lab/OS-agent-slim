"""SaaS 数据访问层。

复用现有 StableAgentStorage 的 SQLite 连接模式，新增 SaaS 表的 CRUD 操作。

约定：
- 所有方法返回 bool 表示操作成功/失败
- 使用 JSON 序列化复杂字段
- 写操作自动 commit
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from stable_agent.saas.models import (
    AgentProfile,
    AgentRun,
    ApiKeyRecord,
    AuditLogRecord,
    BadCaseRecord,
    BillingPlanRecord,
    EvalResultRecord,
    HumanReviewRecord,
    Project,
    RegressionCaseRecord,
    SkillPatchRecord,
    SkillRecord,
    SkillVersionRecord,
    TraceEventRecord,
    UsageEventRecord,
    ValidationRunRecord,
    Workspace,
    WorkspaceMember,
)

logger = logging.getLogger(__name__)


class SaasRepository:
    """SaaS 数据访问层。

    管理 SaaS 相关表的 CRUD。与现有 StableAgentStorage 共享同一个
    SQLite 数据库文件，通过表名前缀区分。

    Attributes:
        db_path: 数据库文件路径。
        conn: sqlite3 连接对象（延迟初始化）。
    """

    def __init__(self, db_path: str = "data/stable_agent.sqlite3") -> None:
        self.db_path: str = db_path
        self.conn: sqlite3.Connection | None = None

        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # SaaS v1.3: 自动初始化（幂等），确保所有 API 路由可用
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
        return self.conn

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """创建所有 SaaS 表（幂等）。"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT DEFAULT '',
                owner_user_id TEXT DEFAULT '',
                billing_plan TEXT DEFAULT 'free',
                created_at REAL NOT NULL,
                updated_at REAL,
                settings TEXT DEFAULT '{}'
            );

            -- 基础 runs 表（与 StableAgentStorage 兼容 + SaaS 扩展）
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                user_task TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL DEFAULT 'general_qa',
                status TEXT NOT NULL DEFAULT 'init',
                started_at REAL NOT NULL DEFAULT 0,
                ended_at REAL,
                total_input_tokens INTEGER NOT NULL DEFAULT 0,
                total_output_tokens INTEGER NOT NULL DEFAULT 0,
                total_cost_estimate REAL NOT NULL DEFAULT 0.0,
                overall_score REAL,
                progress_pct INTEGER DEFAULT 0,
                intent_alignment_score REAL,
                token_used INTEGER DEFAULT 0,
                cost_estimate REAL DEFAULT 0.0,
                learning_triggered INTEGER DEFAULT 0,
                skill_updated INTEGER DEFAULT 0,
                dashboard_url TEXT DEFAULT '',
                trace_url TEXT DEFAULT '',
                failure_attribution TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                workspace_id TEXT,
                project_id TEXT,
                agent_id TEXT
            );

            CREATE TABLE IF NOT EXISTS workspace_members (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                email TEXT DEFAULT '',
                role TEXT NOT NULL DEFAULT 'developer',
                joined_at REAL NOT NULL,
                created_at REAL,
                updated_at REAL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                default_agent_id TEXT DEFAULT '',
                environment TEXT DEFAULT 'local',
                created_at REAL NOT NULL,
                updated_at REAL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS agent_profiles (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                agent_type TEXT DEFAULT 'general',
                default_skill_id TEXT DEFAULT '',
                default_model TEXT DEFAULT '',
                mcp_endpoint TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL DEFAULT 'sk_',
                scopes TEXT DEFAULT '[]',
                status TEXT DEFAULT 'active',
                last_used_at REAL,
                created_at REAL NOT NULL,
                revoked_at REAL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS usage_events (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                run_id TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                cost_estimate REAL DEFAULT 0.0,
                metadata TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS regression_cases (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                task_input TEXT NOT NULL,
                expected_behavior TEXT DEFAULT '',
                failure_mode TEXT DEFAULT 'unknown',
                source_run_id TEXT DEFAULT '',
                source_bad_case_id TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                overall_score REAL DEFAULT 0.0,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skill_records (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                current_version TEXT DEFAULT 'v1.0',
                content TEXT NOT NULL,
                score REAL DEFAULT 0.0,
                created_at REAL NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS skill_versions (
                id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                score REAL DEFAULT 0.0,
                created_at REAL NOT NULL,
                FOREIGN KEY (skill_id) REFERENCES skill_records(id)
            );

            CREATE TABLE IF NOT EXISTS skill_patches (
                id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                workspace_id TEXT DEFAULT '',
                project_id TEXT DEFAULT '',
                source_run_id TEXT DEFAULT '',
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                patch_type TEXT DEFAULT 'prompt',
                patch_content TEXT NOT NULL DEFAULT '',
                patch_diff TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                old_score REAL DEFAULT 0.0,
                new_score REAL DEFAULT 0.0,
                delta REAL DEFAULT 0.0,
                status TEXT DEFAULT 'candidate',
                validation_run_id TEXT DEFAULT '',
                human_review_id TEXT DEFAULT '',
                proposed_by TEXT DEFAULT 'system',
                created_at REAL NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS validation_runs (
                id TEXT PRIMARY KEY,
                patch_id TEXT NOT NULL,
                baseline_score REAL DEFAULT 0.0,
                candidate_score REAL DEFAULT 0.0,
                score_delta REAL DEFAULT 0.0,
                passed INTEGER DEFAULT 0,
                regression_cases TEXT DEFAULT '[]',
                explanation TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS human_reviews (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                reviewer TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                comment TEXT DEFAULT '',
                created_at REAL NOT NULL,
                resolved_at REAL
            );

            CREATE TABLE IF NOT EXISTS billing_plans (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL UNIQUE,
                tier TEXT NOT NULL DEFAULT 'free',
                max_projects INTEGER DEFAULT 1,
                max_runs_per_month INTEGER DEFAULT 100,
                max_members INTEGER DEFAULT 1,
                trace_retention_days INTEGER DEFAULT 7,
                features TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                actor TEXT DEFAULT '',
                target TEXT DEFAULT '',
                details TEXT DEFAULT '{}',
                ip_address TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                severity TEXT DEFAULT 'info',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace ON audit_logs(workspace_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
            CREATE INDEX IF NOT EXISTS idx_usage_events_project ON usage_events(project_id, created_at);

            -- SaaS v1.5: 用户认证表
            CREATE TABLE IF NOT EXISTS saas_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_saas_users_email ON saas_users(email);

        """)
        conn.commit()

        # 为 runs 表添加 SaaS 列和索引（幂等，忽略不存在的表）
        try:
            for col, col_def in [
                ("workspace_id", "TEXT"),
                ("project_id", "TEXT"),
                ("agent_id", "TEXT"),
                ("progress_pct", "INTEGER DEFAULT 0"),
                ("intent_alignment_score", "REAL"),
                ("token_used", "INTEGER DEFAULT 0"),
                ("cost_estimate", "REAL DEFAULT 0.0"),
                ("learning_triggered", "INTEGER DEFAULT 0"),
                ("skill_updated", "INTEGER DEFAULT 0"),
                ("dashboard_url", "TEXT DEFAULT ''"),
                ("trace_url", "TEXT DEFAULT ''"),
                ("failure_attribution", "TEXT DEFAULT '{}'"),
                ("metadata", "TEXT DEFAULT '{}'"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass  # 列已存在或表不存在
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_workspace ON runs(workspace_id)"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass  # runs 表可能不存在（新数据库）

        # 为 workspaces 表添加商业字段（幂等）
        try:
            for col, col_def in [
                ("slug", "TEXT DEFAULT ''"),
                ("owner_user_id", "TEXT DEFAULT ''"),
                ("billing_plan", "TEXT DEFAULT 'free'"),
                ("updated_at", "REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE workspaces ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # 为 skill_patches 表添加新字段（幂等）
        try:
            for col, col_def in [
                ("workspace_id", "TEXT DEFAULT ''"),
                ("project_id", "TEXT DEFAULT ''"),
                ("source_run_id", "TEXT DEFAULT ''"),
                ("patch_type", "TEXT DEFAULT 'prompt'"),
                ("patch_diff", "TEXT DEFAULT ''"),
                ("reason", "TEXT DEFAULT ''"),
                ("old_score", "REAL DEFAULT 0.0"),
                ("new_score", "REAL DEFAULT 0.0"),
                ("delta", "REAL DEFAULT 0.0"),
                ("validation_run_id", "TEXT DEFAULT ''"),
                ("human_review_id", "TEXT DEFAULT ''"),
                ("updated_at", "REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE skill_patches ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # 为 projects 表添加新字段（幂等）
        try:
            for col, col_def in [
                ("default_agent_id", "TEXT DEFAULT ''"),
                ("environment", "TEXT DEFAULT 'local'"),
                ("updated_at", "REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE projects ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def create_workspace(self, ws: Workspace) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO workspaces (id, name, slug, owner_user_id, billing_plan, created_at, updated_at, settings) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (ws.id, ws.name, ws.slug, ws.owner_user_id, ws.billing_plan,
                 ws.created_at, ws.updated_at, json.dumps(ws.settings)),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("create_workspace failed: %s", e)
            return False

    def get_workspace(self, ws_id: str) -> Workspace | None:
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM workspaces WHERE id=?", (ws_id,)).fetchone()
            if row is None:
                return None
            return Workspace(
                id=row["id"], name=row["name"], slug=row["slug"] or "",
                owner_user_id=row["owner_user_id"] or "",
                billing_plan=row["billing_plan"] or "free",
                created_at=row["created_at"], updated_at=row["updated_at"] or row["created_at"],
                settings=json.loads(row["settings"]),
            )
        except Exception as e:
            logger.warning("get_workspace failed: %s", e)
            return None

    def list_workspaces(self) -> list[Workspace]:
        try:
            conn = self._get_conn()
            rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC").fetchall()
            return [
                Workspace(
                    id=r["id"], name=r["name"],
                    slug=r["slug"] if "slug" in r.keys() else "",
                    owner_user_id=r["owner_user_id"] if "owner_user_id" in r.keys() else "",
                    billing_plan=r["billing_plan"] if "billing_plan" in r.keys() else "free",
                    created_at=r["created_at"],
                    updated_at=r["updated_at"] if "updated_at" in r.keys() and r["updated_at"] else r["created_at"],
                    settings=json.loads(r["settings"]),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_workspaces failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def create_project(self, proj: Project) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO projects (id, workspace_id, name, description, default_agent_id, environment, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (proj.id, proj.workspace_id, proj.name, proj.description,
                 proj.default_agent_id, proj.environment, proj.created_at, proj.updated_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("create_project failed: %s", e)
            return False

    def get_project(self, proj_id: str) -> Project | None:
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM projects WHERE id=?", (proj_id,)).fetchone()
            if row is None:
                return None
            return Project(
                id=row["id"], workspace_id=row["workspace_id"],
                name=row["name"], description=row["description"],
                default_agent_id=row["default_agent_id"] if "default_agent_id" in row.keys() else "",
                environment=row["environment"] if "environment" in row.keys() else "local",
                created_at=row["created_at"],
                updated_at=row["updated_at"] if "updated_at" in row.keys() and row["updated_at"] else row["created_at"],
            )
        except Exception as e:
            logger.warning("get_project failed: %s", e)
            return None

    def list_projects(self, workspace_id: str) -> list[Project]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM projects WHERE workspace_id=? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
            return [
                Project(
                    id=r["id"], workspace_id=r["workspace_id"],
                    name=r["name"], description=r["description"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_projects failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # AgentRun
    # ------------------------------------------------------------------

    def save_run(self, run: AgentRun) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO runs
                   (run_id, workspace_id, project_id, agent_id, user_task, task_type, status,
                    progress_pct, overall_score, intent_alignment_score,
                    token_used, cost_estimate, learning_triggered, skill_updated,
                    dashboard_url, trace_url,
                    failure_attribution, metadata,
                    started_at, ended_at,
                    total_input_tokens, total_output_tokens, total_cost_estimate)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run.run_id, run.workspace_id, run.project_id, run.agent_id,
                 run.user_task, run.task_type, run.status,
                 run.progress_pct, run.overall_score, run.intent_alignment_score,
                 run.token_used, run.cost_estimate,
                 int(run.learning_triggered), int(run.skill_updated),
                 run.dashboard_url, run.trace_url,
                 json.dumps(run.failure_attribution), json.dumps(run.metadata),
                 run.started_at, run.ended_at,
                 run.token_used, 0, run.cost_estimate),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_run failed: %s", e)
            return False

    def get_run(self, run_id: str) -> AgentRun | None:
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                return None
            return AgentRun(
                run_id=row["run_id"],
                workspace_id=row["workspace_id"] or "",
                project_id=row["project_id"] or "",
                agent_id=row["agent_id"] or "",
                status=row["status"] or "created",
                user_task=row["user_task"] or "",
                task_type=row["task_type"] or "general_qa",
                progress_pct=row["progress_pct"] if "progress_pct" in row.keys() else 0,
                overall_score=row["overall_score"],
                intent_alignment_score=(
                    row["intent_alignment_score"]
                    if "intent_alignment_score" in row.keys() else None
                ),
                token_used=row["token_used"] if "token_used" in row.keys() else 0,
                cost_estimate=row["cost_estimate"] if "cost_estimate" in row.keys() else 0.0,
                learning_triggered=bool(
                    row["learning_triggered"] if "learning_triggered" in row.keys() else False
                ),
                skill_updated=bool(
                    row["skill_updated"] if "skill_updated" in row.keys() else False
                ),
                dashboard_url=row["dashboard_url"] if "dashboard_url" in row.keys() else "",
                trace_url=row["trace_url"] if "trace_url" in row.keys() else "",
                failure_attribution=json.loads(
                    row["failure_attribution"] if "failure_attribution" in row.keys() else "{}"
                ),
                metadata=json.loads(
                    row["metadata"] if "metadata" in row.keys() else "{}"
                ),
                started_at=row["started_at"],
                ended_at=row["ended_at"],
            )
        except Exception as e:
            logger.warning("get_run failed: %s", e)
            return None

    def list_runs_by_project(self, project_id: str, limit: int = 50) -> list[AgentRun]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
            return [
                AgentRun(
                    run_id=r["run_id"],
                    workspace_id=r["workspace_id"] or "",
                    project_id=r["project_id"] or "",
                    agent_id=r["agent_id"] or "",
                    status=r["status"],
                    user_task=r["user_task"],
                    overall_score=r["overall_score"],
                    started_at=r["started_at"],
                    ended_at=r["ended_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_runs_by_project failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # UsageEvent
    # ------------------------------------------------------------------

    def save_usage_event(self, evt: UsageEventRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO usage_events
                   (id, workspace_id, project_id, run_id, event_type,
                    tokens_used, cost_estimate, metadata, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (evt.id, evt.workspace_id, evt.project_id, evt.run_id,
                 evt.event_type, evt.tokens_used, evt.cost_estimate,
                 json.dumps(evt.metadata), evt.created_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_usage_event failed: %s", e)
            return False

    def list_usage_events(self, project_id: str, limit: int = 100) -> list[UsageEventRecord]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM usage_events WHERE project_id=? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
            return [
                UsageEventRecord(
                    id=r["id"], workspace_id=r["workspace_id"],
                    project_id=r["project_id"], run_id=r["run_id"],
                    event_type=r["event_type"], tokens_used=r["tokens_used"],
                    cost_estimate=r["cost_estimate"],
                    metadata=json.loads(r["metadata"]), created_at=r["created_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_usage_events failed: %s", e)
            return []

    def get_project_usage_summary(self, project_id: str) -> dict[str, Any]:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT COUNT(*) as total_events, SUM(tokens_used) as total_tokens, "
                "SUM(cost_estimate) as total_cost FROM usage_events WHERE project_id=?",
                (project_id,),
            ).fetchone()
            return {
                "total_events": row["total_events"] or 0,
                "total_tokens": row["total_tokens"] or 0,
                "total_cost": round(row["total_cost"] or 0.0, 6),
            }
        except Exception as e:
            logger.warning("get_project_usage_summary failed: %s", e)
            return {"total_events": 0, "total_tokens": 0, "total_cost": 0.0}

    # ------------------------------------------------------------------
    # RegressionCase
    # ------------------------------------------------------------------

    def save_regression_case(self, case: RegressionCaseRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO regression_cases
                   (id, workspace_id, project_id, task_input, expected_behavior,
                    failure_mode, source_run_id, source_bad_case_id, tags,
                    overall_score, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (case.id, case.workspace_id, case.project_id, case.task_input,
                 case.expected_behavior, case.failure_mode, case.source_run_id,
                 case.source_bad_case_id, json.dumps(case.tags),
                 case.overall_score, case.created_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_regression_case failed: %s", e)
            return False

    def list_regression_cases(self, project_id: str) -> list[RegressionCaseRecord]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM regression_cases WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            return [
                RegressionCaseRecord(
                    id=r["id"], workspace_id=r["workspace_id"],
                    project_id=r["project_id"], task_input=r["task_input"],
                    expected_behavior=r["expected_behavior"],
                    failure_mode=r["failure_mode"],
                    source_run_id=r["source_run_id"],
                    source_bad_case_id=r["source_bad_case_id"],
                    tags=json.loads(r["tags"]), overall_score=r["overall_score"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_regression_cases failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # HumanReview
    # ------------------------------------------------------------------

    def create_human_review(self, review: HumanReviewRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO human_reviews
                   (id, workspace_id, project_id, target_type, target_id,
                    reviewer, status, comment, created_at, resolved_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (review.id, review.workspace_id, review.project_id,
                 review.target_type, review.target_id, review.reviewer,
                 review.status, review.comment, review.created_at, review.resolved_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("create_human_review failed: %s", e)
            return False

    def get_human_review(self, review_id: str) -> HumanReviewRecord | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM human_reviews WHERE id=?", (review_id,)
            ).fetchone()
            if row is None:
                return None
            return HumanReviewRecord(
                id=row["id"], workspace_id=row["workspace_id"],
                project_id=row["project_id"], target_type=row["target_type"],
                target_id=row["target_id"], reviewer=row["reviewer"],
                status=row["status"], comment=row["comment"],
                created_at=row["created_at"], resolved_at=row["resolved_at"],
            )
        except Exception as e:
            logger.warning("get_human_review failed: %s", e)
            return None

    def update_human_review(self, review_id: str, status: str, comment: str = "") -> bool:
        try:
            conn = self._get_conn()
            import time
            conn.execute(
                "UPDATE human_reviews SET status=?, comment=?, resolved_at=? WHERE id=?",
                (status, comment, time.time(), review_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("update_human_review failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # ApiKey
    # ------------------------------------------------------------------

    def create_api_key(self, key: ApiKeyRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO api_keys (id, workspace_id, key_hash, key_prefix, name, created_at, revoked_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (key.id, key.workspace_id, key.key_hash, key.key_prefix,
                 key.name, key.created_at, key.revoked_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("create_api_key failed: %s", e)
            return False

    def get_api_key_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash=?", (key_hash,)
            ).fetchone()
            if row is None:
                return None
            return ApiKeyRecord(
                id=row["id"], workspace_id=row["workspace_id"],
                key_hash=row["key_hash"], key_prefix=row["key_prefix"],
                name=row["name"], created_at=row["created_at"],
                revoked_at=row["revoked_at"],
            )
        except Exception as e:
            logger.warning("get_api_key_by_hash failed: %s", e)
            return None

    def revoke_api_key(self, key_id: str) -> bool:
        try:
            conn = self._get_conn()
            import time
            conn.execute(
                "UPDATE api_keys SET revoked_at=? WHERE id=?",
                (time.time(), key_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("revoke_api_key failed: %s", e)
            return False

    def list_api_keys(self, workspace_id: str) -> list[ApiKeyRecord]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM api_keys WHERE workspace_id=? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
            return [
                ApiKeyRecord(
                    id=r["id"], workspace_id=r["workspace_id"],
                    key_hash=r["key_hash"], key_prefix=r["key_prefix"],
                    name=r["name"], created_at=r["created_at"],
                    revoked_at=r["revoked_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_api_keys failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Skill
    # ------------------------------------------------------------------

    def save_skill(self, skill: SkillRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO skill_records
                   (id, workspace_id, project_id, name, current_version,
                    content, score, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (skill.id, skill.workspace_id, skill.project_id, skill.name,
                 skill.current_version, skill.content, skill.score,
                 skill.created_at, skill.updated_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_skill failed: %s", e)
            return False

    def get_skill(self, skill_id: str) -> SkillRecord | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM skill_records WHERE id=?", (skill_id,)
            ).fetchone()
            if row is None:
                return None
            return SkillRecord(
                id=row["id"], workspace_id=row["workspace_id"],
                project_id=row["project_id"], name=row["name"],
                current_version=row["current_version"], content=row["content"],
                score=row["score"], created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except Exception as e:
            logger.warning("get_skill failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # SkillPatch
    # ------------------------------------------------------------------

    def save_skill_patch(self, patch: SkillPatchRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                    """INSERT OR REPLACE INTO skill_patches
                       (id, skill_id, workspace_id, project_id, source_run_id,
                        from_version, to_version, patch_type, patch_diff, reason,
                        old_score, new_score, delta,
                        status, validation_run_id, human_review_id,
                        proposed_by, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (patch.id, patch.skill_id, patch.workspace_id, patch.project_id,
                     patch.source_run_id,
                     patch.from_version, patch.to_version, patch.patch_type,
                     patch.patch_diff, patch.reason,
                     patch.old_score, patch.new_score, patch.delta,
                     patch.status, patch.validation_run_id, patch.human_review_id,
                     patch.proposed_by, patch.created_at, patch.updated_at),
                )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_skill_patch failed: %s", e)
            return False

    def get_skill_patch(self, patch_id: str) -> SkillPatchRecord | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM skill_patches WHERE id=?", (patch_id,)
            ).fetchone()
            if row is None:
                return None
            return SkillPatchRecord(
                id=row["id"], skill_id=row["skill_id"],
                workspace_id=(row["workspace_id"] if "workspace_id" in row.keys() else "") or "",
                project_id=(row["project_id"] if "project_id" in row.keys() else "") or "",
                source_run_id=(row["source_run_id"] if "source_run_id" in row.keys() else "") or "",
                from_version=row["from_version"], to_version=row["to_version"],
                patch_type=(row["patch_type"] if "patch_type" in row.keys() else "prompt") or "prompt",
                patch_diff=row["patch_content"] or (row["patch_diff"] if "patch_diff" in row.keys() else ""),
                reason=(row["reason"] if "reason" in row.keys() else "") or "",
                old_score=(row["old_score"] if "old_score" in row.keys() else 0.0) or 0.0,
                new_score=(row["new_score"] if "new_score" in row.keys() else 0.0) or 0.0,
                delta=(row["delta"] if "delta" in row.keys() else 0.0) or 0.0,
                status=row["status"],
                validation_run_id=(row["validation_run_id"] if "validation_run_id" in row.keys() else "") or "",
                human_review_id=(row["human_review_id"] if "human_review_id" in row.keys() else "") or "",
                proposed_by=row["proposed_by"] or "system",
                created_at=row["created_at"],
                updated_at=((row["updated_at"] if "updated_at" in row.keys() else None) or row["created_at"]),
            )
        except Exception as e:
            logger.warning("get_skill_patch failed: %s", e)
            return None

    def update_skill_patch_status(self, patch_id: str, status: str) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                "UPDATE skill_patches SET status=? WHERE id=?",
                (status, patch_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("update_skill_patch_status failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # ValidationRun
    # ------------------------------------------------------------------

    def save_validation_run(self, vr: ValidationRunRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO validation_runs
                   (id, patch_id, baseline_score, candidate_score, score_delta,
                    passed, regression_cases, explanation, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (vr.id, vr.patch_id, vr.baseline_score, vr.candidate_score,
                 vr.score_delta, int(vr.passed), json.dumps(vr.regression_cases),
                 vr.explanation, vr.created_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_validation_run failed: %s", e)
            return False

    def get_validation_run(self, patch_id: str) -> ValidationRunRecord | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM validation_runs WHERE patch_id=? ORDER BY created_at DESC LIMIT 1",
                (patch_id,),
            ).fetchone()
            if row is None:
                return None
            return ValidationRunRecord(
                id=row["id"], patch_id=row["patch_id"],
                baseline_score=row["baseline_score"],
                candidate_score=row["candidate_score"],
                score_delta=row["score_delta"],
                passed=bool(row["passed"]),
                regression_cases=json.loads(row["regression_cases"]),
                explanation=row["explanation"],
                created_at=row["created_at"],
            )
        except Exception as e:
            logger.warning("get_validation_run failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # BillingPlan
    # ------------------------------------------------------------------

    def save_billing_plan(self, plan: BillingPlanRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO billing_plans
                   (id, workspace_id, tier, max_projects, max_runs_per_month,
                    max_members, trace_retention_days, features, is_active,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (plan.id, plan.workspace_id, plan.tier,
                 plan.max_projects, plan.max_runs_per_month,
                 plan.max_members, plan.trace_retention_days,
                 json.dumps(plan.features), int(plan.is_active),
                 plan.created_at, plan.updated_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_billing_plan failed: %s", e)
            return False

    def get_billing_plan(self, workspace_id: str) -> BillingPlanRecord | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM billing_plans WHERE workspace_id=?",
                (workspace_id,),
            ).fetchone()
            if row is None:
                return None
            return BillingPlanRecord(
                id=row["id"], workspace_id=row["workspace_id"],
                tier=row["tier"], max_projects=row["max_projects"],
                max_runs_per_month=row["max_runs_per_month"],
                max_members=row["max_members"],
                trace_retention_days=row["trace_retention_days"],
                features=json.loads(row["features"]),
                is_active=bool(row["is_active"]),
                created_at=row["created_at"], updated_at=row["updated_at"],
            )
        except Exception as e:
            logger.warning("get_billing_plan failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # AuditLog
    # ------------------------------------------------------------------

    def save_audit_log(self, record: AuditLogRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO audit_logs
                   (id, workspace_id, project_id, event_type, actor, target,
                    details, ip_address, user_agent, severity, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (record.id, record.workspace_id, record.project_id,
                 record.event_type, record.actor, record.target,
                 json.dumps(record.details), record.ip_address,
                 record.user_agent, record.severity, record.created_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_audit_log failed: %s", e)
            return False

    def list_audit_logs(
        self, workspace_id: str, limit: int = 50,
    ) -> list[AuditLogRecord]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE workspace_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (workspace_id, limit),
            ).fetchall()
            return [
                AuditLogRecord(
                    id=r["id"], workspace_id=r["workspace_id"],
                    project_id=r["project_id"] or "",
                    event_type=r["event_type"], actor=r["actor"],
                    target=r["target"], details=json.loads(r["details"]),
                    ip_address=r["ip_address"], user_agent=r["user_agent"],
                    severity=r["severity"], created_at=r["created_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_audit_logs failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # WorkspaceMember 扩展
    # ------------------------------------------------------------------

    def save_workspace_member(self, member: WorkspaceMember) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO workspace_members
                   (id, workspace_id, user_id, email, role, joined_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (member.id, member.workspace_id, member.user_id, member.email,
                 member.role, member.joined_at, member.created_at, member.updated_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_workspace_member failed: %s", e)
            return False

    def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMember]:
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM workspace_members WHERE workspace_id=? ORDER BY joined_at",
                (workspace_id,),
            ).fetchall()
            return [
                WorkspaceMember(
                    id=r["id"], workspace_id=r["workspace_id"],
                    user_id=r["user_id"], email=r["email"] or "",
                    role=r["role"], joined_at=r["joined_at"],
                    created_at=r["created_at"] or r["joined_at"],
                    updated_at=r["updated_at"] or r["joined_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("list_workspace_members failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # EvalResult
    # ------------------------------------------------------------------

    def save_eval_result(self, eval_record: EvalResultRecord) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO eval_results
                   (id, run_id, workspace_id, project_id, scores,
                    overall_score, failure_attribution, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (eval_record.id, eval_record.run_id,
                 eval_record.workspace_id, eval_record.project_id,
                 json.dumps(eval_record.scores),
                 eval_record.overall_score,
                 json.dumps(eval_record.failure_attribution),
                 eval_record.created_at),
            )
            # Create eval_results table if not exists
            return True
        except Exception:
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS eval_results (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        scores TEXT DEFAULT '{}',
                        overall_score REAL DEFAULT 0.0,
                        failure_attribution TEXT DEFAULT '{}',
                        created_at REAL NOT NULL
                    )
                """)
                conn.execute(
                    """INSERT OR REPLACE INTO eval_results
                       (id, run_id, workspace_id, project_id, scores,
                        overall_score, failure_attribution, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (eval_record.id, eval_record.run_id,
                     eval_record.workspace_id, eval_record.project_id,
                     json.dumps(eval_record.scores),
                     eval_record.overall_score,
                     json.dumps(eval_record.failure_attribution),
                     eval_record.created_at),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.warning("save_eval_result failed: %s", e)
                return False

    # ------------------------------------------------------------------
    # SaaS v1.5: User 认证
    # ------------------------------------------------------------------

    def save_user(self, user_data: Any) -> bool:
        """保存用户记录。user_data 为 SaaSUser dataclass。"""
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO saas_users (id, email, password_hash, name, created_at) VALUES (?,?,?,?,?)",
                (user_data.id, user_data.email, user_data.password_hash, user_data.name, user_data.created_at),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("save_user failed: %s", e)
            return False

    def get_user_by_email(self, email: str) -> Any | None:
        """按邮箱查找用户。"""
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM saas_users WHERE email=?", (email,)).fetchone()
            if row is None:
                return None
            from stable_agent.saas.auth import SaaSUser
            return SaaSUser(id=row["id"], email=row["email"], password_hash=row["password_hash"],
                           name=row["name"] or "", created_at=row["created_at"])
        except Exception as e:
            logger.warning("get_user_by_email failed: %s", e)
            return None

    def get_user_by_id(self, user_id: str) -> Any | None:
        """按 ID 查找用户。"""
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM saas_users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                return None
            from stable_agent.saas.auth import SaaSUser
            return SaaSUser(id=row["id"], email=row["email"], password_hash=row["password_hash"],
                           name=row["name"] or "", created_at=row["created_at"])
        except Exception as e:
            logger.warning("get_user_by_id failed: %s", e)
            return None
