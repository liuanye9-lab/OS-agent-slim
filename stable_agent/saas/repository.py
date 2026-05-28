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
    BadCaseRecord,
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
                created_at REAL NOT NULL,
                settings TEXT DEFAULT '{}'
            );

            -- 基础 runs 表（如果不存在则创建，与 StableAgentStorage 兼容）
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
                workspace_id TEXT,
                project_id TEXT,
                agent_id TEXT
            );

            CREATE TABLE IF NOT EXISTS workspace_members (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at REAL NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at REAL NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS agent_profiles (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                config TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL DEFAULT 'sk_',
                name TEXT NOT NULL,
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
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                patch_content TEXT NOT NULL,
                proposed_by TEXT DEFAULT 'system',
                status TEXT DEFAULT 'proposed',
                created_at REAL NOT NULL
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

        """)
        conn.commit()

        # 为 runs 表添加 SaaS 列和索引（幂等，忽略不存在的表）
        try:
            for col, col_def in [
                ("workspace_id", "TEXT"),
                ("project_id", "TEXT"),
                ("agent_id", "TEXT"),
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

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def create_workspace(self, ws: Workspace) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO workspaces (id, name, created_at, settings) VALUES (?,?,?,?)",
                (ws.id, ws.name, ws.created_at, json.dumps(ws.settings)),
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
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
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
                    created_at=r["created_at"], settings=json.loads(r["settings"]),
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
                "INSERT INTO projects (id, workspace_id, name, description, created_at) VALUES (?,?,?,?,?)",
                (proj.id, proj.workspace_id, proj.name, proj.description, proj.created_at),
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
                created_at=row["created_at"],
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
                   (run_id, workspace_id, project_id, agent_id, user_task, status,
                    started_at, ended_at, overall_score)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (run.run_id, run.workspace_id, run.project_id, run.agent_id,
                 run.user_task, run.status, run.started_at, run.ended_at, run.overall_score),
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
                status=row["status"],
                user_task=row["user_task"],
                overall_score=row["overall_score"],
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
                   (id, skill_id, from_version, to_version, patch_content,
                    proposed_by, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (patch.id, patch.skill_id, patch.from_version, patch.to_version,
                 patch.patch_content, patch.proposed_by, patch.status, patch.created_at),
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
                from_version=row["from_version"], to_version=row["to_version"],
                patch_content=row["patch_content"],
                proposed_by=row["proposed_by"], status=row["status"],
                created_at=row["created_at"],
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
