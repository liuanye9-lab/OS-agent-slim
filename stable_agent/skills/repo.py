"""stable_agent.skills.repo — SkillRepo 技能库。

轻量、可回滚、可检索的技能库，基于 SQLite 存储。
支持 MCP / CLI / Dashboard 共用同一套 SkillRepo。
2 核 2GB 可运行。

存储位置: .stableagent-capsule/skills/
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from stable_agent.skills.schema import (
    CurationOp,
    CurationOpType,
    RiskLevel,
    SkillMetadata,
    SkillPackage,
    SkillScope,
    SkillStatus,
    SkillTags,
    SkillUsageRecord,
    SkillVersion,
    generate_id,
)

logger = logging.getLogger(__name__)

# 默认存储路径
DEFAULT_SKILLS_DIR = ".stableagent-capsule/skills"
DEFAULT_DB_NAME = "skills.sqlite"

# Slim profile 配置
MAX_ACTIVE_SKILLS = int(os.environ.get("STABLEAGENT_MAX_ACTIVE_SKILLS", "200"))
MAX_SKILL_VERSIONS = int(os.environ.get("STABLEAGENT_MAX_SKILL_VERSIONS", "20"))


class SkillRepo:
    """技能库。

    实现轻量、可回滚、可检索的技能库。
    所有变更 append-only 记录 curation event。
    delete 不做物理删除，改 status=deleted。
    每次变更必须生成 version。

    Attributes:
        db_path: SQLite 数据库路径。
        packages_dir: 技能包目录。
        events_dir: 事件日志目录。
    """

    def __init__(
        self,
        skills_dir: str | None = None,
        db_name: str = DEFAULT_DB_NAME,
    ) -> None:
        """初始化 SkillRepo。

        Args:
            skills_dir: 技能库根目录，默认 .stableagent-capsule/skills。
            db_name: SQLite 数据库文件名。
        """
        if skills_dir is None:
            skills_dir = os.environ.get(
                "STABLEAGENT_SKILLS_DIR",
                DEFAULT_SKILLS_DIR,
            )
        self.skills_dir = Path(skills_dir).resolve()
        self.packages_dir = self.skills_dir / "packages"
        self.events_dir = self.skills_dir / "events"
        self.db_path = self.skills_dir / db_name

        # 创建目录
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_db()

    def _init_db(self) -> None:
        """初始化 SQLite 数据库表。"""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS skills (
                    skill_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    version INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active',
                    scope TEXT DEFAULT 'global',
                    tags_json TEXT DEFAULT '{}',
                    trigger_phrases_json TEXT DEFAULT '[]',
                    quality_score REAL DEFAULT 0.5,
                    usage_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    source_runs_json TEXT DEFAULT '[]',
                    storage_path TEXT DEFAULT '',
                    risk_level TEXT DEFAULT 'low',
                    created_by TEXT DEFAULT 'curator',
                    last_used_at REAL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS skill_versions (
                    id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    parent_version INTEGER,
                    op_id TEXT DEFAULT '',
                    content_hash TEXT DEFAULT '',
                    metadata_snapshot_json TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
                );

                CREATE TABLE IF NOT EXISTS curation_events (
                    op_id TEXT PRIMARY KEY,
                    op TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    source_run TEXT DEFAULT '',
                    reason TEXT DEFAULT '',
                    confidence REAL DEFAULT 0.0,
                    requires_human_review INTEGER DEFAULT 1,
                    payload_json TEXT DEFAULT '{}',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS skill_usage (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    task_id TEXT DEFAULT '',
                    used_at REAL NOT NULL,
                    outcome TEXT DEFAULT '',
                    token_cost INTEGER DEFAULT 0,
                    attribution_score REAL DEFAULT 0.0
                );

                CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
                CREATE INDEX IF NOT EXISTS idx_skill_versions_skill_id ON skill_versions(skill_id);
                CREATE INDEX IF NOT EXISTS idx_curation_events_skill_id ON curation_events(skill_id);
                CREATE INDEX IF NOT EXISTS idx_skill_usage_skill_id ON skill_usage(skill_id);
                CREATE INDEX IF NOT EXISTS idx_skill_usage_run_id ON skill_usage(run_id);
            """)

    def _conn(self) -> sqlite3.Connection:
        """获取 SQLite 连接。"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------------
    # CRUD 操作
    # ------------------------------------------------------------------

    def insert_skill(
        self,
        metadata: SkillMetadata,
        source_run: str = "",
        reason: str = "",
    ) -> SkillMetadata:
        """插入新技能。

        Args:
            metadata: 技能元数据。
            source_run: 来源运行 ID。
            reason: 操作原因。

        Returns:
            插入后的技能元数据。
        """
        now = time.time()
        if not metadata.skill_id:
            metadata.skill_id = generate_id("skill_")
        if not metadata.name:
            metadata.name = metadata.skill_id
        metadata.created_at = now
        metadata.updated_at = now
        metadata.version = 1
        metadata.status = SkillStatus.ACTIVE

        # 创建存储目录
        skill_dir = self.packages_dir / metadata.skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        metadata.storage_path = str(skill_dir)

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO skills (
                    skill_id, name, description, version, status, scope,
                    tags_json, trigger_phrases_json, quality_score,
                    usage_count, success_count, failure_count,
                    source_runs_json, storage_path, risk_level, created_by,
                    last_used_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    metadata.skill_id,
                    metadata.name,
                    metadata.description,
                    metadata.version,
                    metadata.status.value,
                    metadata.scope.value,
                    json.dumps(metadata.tags.to_dict(), ensure_ascii=False),
                    json.dumps(metadata.trigger_phrases, ensure_ascii=False),
                    metadata.quality_score,
                    metadata.usage_count,
                    metadata.success_count,
                    metadata.failure_count,
                    json.dumps(metadata.source_runs, ensure_ascii=False),
                    metadata.storage_path,
                    metadata.risk_level.value,
                    metadata.created_by,
                    metadata.last_used_at,
                    metadata.created_at,
                    metadata.updated_at,
                ),
            )

        # 创建版本记录
        self._create_version(metadata.skill_id, 1, None, "", metadata)

        # 记录 curation event
        self._record_curation_event(
            op_type=CurationOpType.INSERT_SKILL,
            skill_id=metadata.skill_id,
            source_run=source_run,
            reason=reason,
            confidence=1.0,
            requires_human_review=False,
            payload=metadata.to_dict(),
        )

        logger.info("Inserted skill: %s (%s)", metadata.skill_id, metadata.name)
        return metadata

    def update_skill(
        self,
        skill_id: str,
        patch: dict[str, Any],
        source_run: str = "",
        reason: str = "",
        requires_human_review: bool = True,
    ) -> Optional[SkillMetadata]:
        """更新技能。

        Args:
            skill_id: 技能 ID。
            patch: 补丁数据。
            source_run: 来源运行 ID。
            reason: 操作原因。
            requires_human_review: 是否需要人工审核。

        Returns:
            更新后的技能元数据，如果技能不存在返回 None。
        """
        metadata = self.get_skill(skill_id)
        if metadata is None:
            logger.warning("Skill not found: %s", skill_id)
            return None

        now = time.time()
        old_version = metadata.version

        # 应用补丁
        for key, value in patch.items():
            if hasattr(metadata, key):
                if key == "tags" and isinstance(value, dict):
                    metadata.tags = SkillTags.from_dict(value)
                elif key == "status" and isinstance(value, str):
                    metadata.status = SkillStatus(value)
                elif key == "scope" and isinstance(value, str):
                    metadata.scope = SkillScope(value)
                elif key == "risk_level" and isinstance(value, str):
                    metadata.risk_level = RiskLevel(value)
                else:
                    setattr(metadata, key, value)

        metadata.version = old_version + 1
        metadata.updated_at = now

        with self._conn() as conn:
            conn.execute(
                """UPDATE skills SET
                    name=?, description=?, version=?, status=?, scope=?,
                    tags_json=?, trigger_phrases_json=?, quality_score=?,
                    usage_count=?, success_count=?, failure_count=?,
                    source_runs_json=?, storage_path=?, risk_level=?, created_by=?,
                    last_used_at=?, updated_at=?
                WHERE skill_id=?""",
                (
                    metadata.name,
                    metadata.description,
                    metadata.version,
                    metadata.status.value,
                    metadata.scope.value,
                    json.dumps(metadata.tags.to_dict(), ensure_ascii=False),
                    json.dumps(metadata.trigger_phrases, ensure_ascii=False),
                    metadata.quality_score,
                    metadata.usage_count,
                    metadata.success_count,
                    metadata.failure_count,
                    json.dumps(metadata.source_runs, ensure_ascii=False),
                    metadata.storage_path,
                    metadata.risk_level.value,
                    metadata.created_by,
                    metadata.last_used_at,
                    metadata.updated_at,
                    skill_id,
                ),
            )

        # 创建版本记录
        op_id = generate_id("op_")
        self._create_version(skill_id, metadata.version, old_version, op_id, metadata)

        # 记录 curation event
        self._record_curation_event(
            op_type=CurationOpType.UPDATE_SKILL,
            skill_id=skill_id,
            source_run=source_run,
            reason=reason,
            confidence=0.8,
            requires_human_review=requires_human_review,
            payload={"patch": patch, "old_version": old_version, "new_version": metadata.version},
        )

        logger.info("Updated skill: %s (v%d -> v%d)", skill_id, old_version, metadata.version)
        return metadata

    def delete_skill(
        self,
        skill_id: str,
        source_run: str = "",
        reason: str = "",
    ) -> bool:
        """软删除技能。

        Args:
            skill_id: 技能 ID。
            source_run: 来源运行 ID。
            reason: 操作原因。

        Returns:
            是否删除成功。
        """
        metadata = self.get_skill(skill_id)
        if metadata is None:
            return False

        metadata.status = SkillStatus.DELETED
        metadata.updated_at = time.time()

        with self._conn() as conn:
            conn.execute(
                "UPDATE skills SET status=?, updated_at=? WHERE skill_id=?",
                (metadata.status.value, metadata.updated_at, skill_id),
            )

        # 记录 curation event
        self._record_curation_event(
            op_type=CurationOpType.DELETE_SKILL,
            skill_id=skill_id,
            source_run=source_run,
            reason=reason,
            confidence=1.0,
            requires_human_review=True,
            payload={},
        )

        logger.info("Deleted skill: %s", skill_id)
        return True

    def archive_skill(
        self,
        skill_id: str,
        source_run: str = "",
        reason: str = "",
    ) -> bool:
        """归档技能。

        Args:
            skill_id: 技能 ID。
            source_run: 来源运行 ID。
            reason: 操作原因。

        Returns:
            是否归档成功。
        """
        metadata = self.get_skill(skill_id)
        if metadata is None:
            return False

        metadata.status = SkillStatus.ARCHIVED
        metadata.updated_at = time.time()

        with self._conn() as conn:
            conn.execute(
                "UPDATE skills SET status=?, updated_at=? WHERE skill_id=?",
                (metadata.status.value, metadata.updated_at, skill_id),
            )

        # 记录 curation event
        self._record_curation_event(
            op_type=CurationOpType.ARCHIVE_SKILL,
            skill_id=skill_id,
            source_run=source_run,
            reason=reason,
            confidence=1.0,
            requires_human_review=True,
            payload={},
        )

        logger.info("Archived skill: %s", skill_id)
        return True

    def get_skill(self, skill_id: str) -> Optional[SkillMetadata]:
        """获取技能。

        Args:
            skill_id: 技能 ID。

        Returns:
            技能元数据，不存在返回 None。
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM skills WHERE skill_id=?", (skill_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_metadata(row)

    def list_skills(
        self,
        status: str | SkillStatus = "active",
        scope: str | SkillScope | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SkillMetadata]:
        """列出技能。

        Args:
            status: 过滤状态。
            scope: 过滤作用域。
            limit: 返回数量限制。
            offset: 偏移量。

        Returns:
            技能元数据列表。
        """
        status_val = status.value if isinstance(status, SkillStatus) else status
        scope_val = scope.value if isinstance(scope, SkillScope) else scope

        query = "SELECT * FROM skills WHERE status=?"
        params: list[Any] = [status_val]

        if scope_val:
            query += " AND scope=?"
            params.append(scope_val)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_metadata(row) for row in rows]

    def search_metadata(
        self,
        query: str,
        top_k: int = 5,
        status: str = "active",
    ) -> list[dict[str, Any]]:
        """搜索技能元数据。

        简单关键词匹配，用于轻量检索。

        Args:
            query: 搜索查询。
            top_k: 返回数量。
            status: 过滤状态。

        Returns:
            匹配结果列表。
        """
        query_lower = query.lower()
        terms = query_lower.split()

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skills WHERE status=?", (status,)
            ).fetchall()

        results = []
        for row in rows:
            meta = self._row_to_metadata(row)
            score = 0.0
            matched_terms = []

            # name 匹配
            name_lower = meta.name.lower()
            for term in terms:
                if term in name_lower:
                    score += 3.0
                    matched_terms.append(f"name:{term}")

            # description 匹配
            desc_lower = meta.description.lower()
            for term in terms:
                if term in desc_lower:
                    score += 2.0
                    matched_terms.append(f"desc:{term}")

            # trigger_phrases 匹配
            for phrase in meta.trigger_phrases:
                phrase_lower = phrase.lower()
                for term in terms:
                    if term in phrase_lower:
                        score += 5.0
                        matched_terms.append(f"trigger:{term}")

            # tags 匹配
            all_tags = (
                meta.tags.topic
                + meta.tags.capabilities
                + meta.tags.concepts
                + meta.tags.heuristics
                + meta.tags.pitfalls
            )
            for tag in all_tags:
                tag_lower = tag.lower()
                for term in terms:
                    if term in tag_lower:
                        score += 2.0
                        matched_terms.append(f"tag:{term}")

            if score > 0:
                # 最近成功使用过的 skill 加小权重
                if meta.success_count > meta.failure_count:
                    score += 0.5
                # 最近失败或回滚过的 skill 降权
                if meta.failure_count > meta.success_count * 2:
                    score -= 1.0

                results.append({
                    "skill_id": meta.skill_id,
                    "name": meta.name,
                    "description": meta.description,
                    "score": max(0.0, score),
                    "matched_terms": list(set(matched_terms)),
                    "reason": f"matched {len(matched_terms)} terms",
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # 使用记录
    # ------------------------------------------------------------------

    def record_usage(
        self,
        run_id: str,
        skill_id: str,
        outcome: str = "",
        token_cost: int = 0,
        attribution_score: float = 0.0,
        task_id: str = "",
    ) -> SkillUsageRecord:
        """记录技能使用。

        Args:
            run_id: 运行 ID。
            skill_id: 技能 ID。
            outcome: 结果 (success/failure)。
            token_cost: Token 消耗。
            attribution_score: 归因分数。
            task_id: 任务 ID。

        Returns:
            使用记录。
        """
        record = SkillUsageRecord(
            id=generate_id("usage_"),
            run_id=run_id,
            skill_id=skill_id,
            task_id=task_id,
            used_at=time.time(),
            outcome=outcome,
            token_cost=token_cost,
            attribution_score=attribution_score,
        )

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO skill_usage (
                    id, run_id, skill_id, task_id, used_at,
                    outcome, token_cost, attribution_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.run_id,
                    record.skill_id,
                    record.task_id,
                    record.used_at,
                    record.outcome,
                    record.token_cost,
                    record.attribution_score,
                ),
            )

            # 更新 skill 统计
            if outcome == "success":
                conn.execute(
                    "UPDATE skills SET usage_count=usage_count+1, success_count=success_count+1, last_used_at=? WHERE skill_id=?",
                    (record.used_at, skill_id),
                )
            elif outcome == "failure":
                conn.execute(
                    "UPDATE skills SET usage_count=usage_count+1, failure_count=failure_count+1, last_used_at=? WHERE skill_id=?",
                    (record.used_at, skill_id),
                )
            else:
                conn.execute(
                    "UPDATE skills SET usage_count=usage_count+1, last_used_at=? WHERE skill_id=?",
                    (record.used_at, skill_id),
                )

        return record

    # ------------------------------------------------------------------
    # 版本管理
    # ------------------------------------------------------------------

    def get_versions(self, skill_id: str) -> list[SkillVersion]:
        """获取技能版本历史。

        Args:
            skill_id: 技能 ID。

        Returns:
            版本列表，按版本号降序。
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_versions WHERE skill_id=? ORDER BY version DESC",
                (skill_id,),
            ).fetchall()

        return [
            SkillVersion(
                id=row["id"],
                skill_id=row["skill_id"],
                version=row["version"],
                parent_version=row["parent_version"],
                op_id=row["op_id"],
                content_hash=row["content_hash"],
                metadata_snapshot=json.loads(row["metadata_snapshot_json"] or "{}"),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def rollback(
        self,
        skill_id: str,
        target_version: int,
        source_run: str = "",
        reason: str = "",
    ) -> Optional[SkillMetadata]:
        """回滚技能到指定版本。

        Args:
            skill_id: 技能 ID。
            target_version: 目标版本号。
            source_run: 来源运行 ID。
            reason: 回滚原因。

        Returns:
            回滚后的技能元数据，失败返回 None。
        """
        versions = self.get_versions(skill_id)
        target = None
        for v in versions:
            if v.version == target_version:
                target = v
                break

        if target is None:
            logger.warning("Version %d not found for skill %s", target_version, skill_id)
            return None

        # 从快照恢复元数据
        snapshot = target.metadata_snapshot
        if not snapshot:
            logger.warning("No metadata snapshot for version %d", target_version)
            return None

        metadata = SkillMetadata.from_dict(snapshot)
        metadata.version = max(v.version for v in versions) + 1
        metadata.updated_at = time.time()

        with self._conn() as conn:
            conn.execute(
                """UPDATE skills SET
                    name=?, description=?, version=?, status=?, scope=?,
                    tags_json=?, trigger_phrases_json=?, quality_score=?,
                    usage_count=?, success_count=?, failure_count=?,
                    source_runs_json=?, storage_path=?, risk_level=?, created_by=?,
                    last_used_at=?, updated_at=?
                WHERE skill_id=?""",
                (
                    metadata.name,
                    metadata.description,
                    metadata.version,
                    metadata.status.value,
                    metadata.scope.value,
                    json.dumps(metadata.tags.to_dict(), ensure_ascii=False),
                    json.dumps(metadata.trigger_phrases, ensure_ascii=False),
                    metadata.quality_score,
                    metadata.usage_count,
                    metadata.success_count,
                    metadata.failure_count,
                    json.dumps(metadata.source_runs, ensure_ascii=False),
                    metadata.storage_path,
                    metadata.risk_level.value,
                    metadata.created_by,
                    metadata.last_used_at,
                    metadata.updated_at,
                    skill_id,
                ),
            )

        # 创建新版本记录
        op_id = generate_id("op_")
        self._create_version(skill_id, metadata.version, target_version, op_id, metadata)

        # 记录 curation event
        self._record_curation_event(
            op_type=CurationOpType.UPDATE_SKILL,
            skill_id=skill_id,
            source_run=source_run,
            reason=f"rollback to v{target_version}: {reason}",
            confidence=1.0,
            requires_human_review=False,
            payload={"target_version": target_version, "new_version": metadata.version},
        )

        logger.info("Rolled back skill %s to v%d (new version: v%d)", skill_id, target_version, metadata.version)
        return metadata

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """技能库健康检查。

        Returns:
            健康报告。
        """
        with self._conn() as conn:
            active_count = conn.execute(
                "SELECT COUNT(*) FROM skills WHERE status='active'"
            ).fetchone()[0]
            archived_count = conn.execute(
                "SELECT COUNT(*) FROM skills WHERE status='archived'"
            ).fetchone()[0]
            deleted_count = conn.execute(
                "SELECT COUNT(*) FROM skills WHERE status='deleted'"
            ).fetchone()[0]
            total_versions = conn.execute(
                "SELECT COUNT(*) FROM skill_versions"
            ).fetchone()[0]
            total_ops = conn.execute(
                "SELECT COUNT(*) FROM curation_events"
            ).fetchone()[0]
            total_usage = conn.execute(
                "SELECT COUNT(*) FROM skill_usage"
            ).fetchone()[0]

        return {
            "ok": True,
            "active_skills": active_count,
            "archived_skills": archived_count,
            "deleted_skills": deleted_count,
            "total_versions": total_versions,
            "curation_ops_count": total_ops,
            "usage_records": total_usage,
            "db_path": str(self.db_path),
            "packages_dir": str(self.packages_dir),
            "max_active_skills": MAX_ACTIVE_SKILLS,
            "max_skill_versions": MAX_SKILL_VERSIONS,
        }

    # ------------------------------------------------------------------
    # 导入导出
    # ------------------------------------------------------------------

    def export_bundle(self, path: str) -> bool:
        """导出技能库为 JSON bundle。

        Args:
            path: 导出路径。

        Returns:
            是否成功。
        """
        skills = self.list_skills(status="active", limit=10000)
        bundle = {
            "version": 1,
            "exported_at": time.time(),
            "skills": [s.to_dict() for s in skills],
        }
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, ensure_ascii=False, indent=2)
            return True
        except Exception as exc:
            logger.error("Export failed: %s", exc)
            return False

    def import_bundle(self, path: str) -> int:
        """从 JSON bundle 导入技能。

        Args:
            path: bundle 路径。

        Returns:
            导入的技能数量。
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        except Exception as exc:
            logger.error("Import failed: %s", exc)
            return 0

        count = 0
        for skill_data in bundle.get("skills", []):
            metadata = SkillMetadata.from_dict(skill_data)
            existing = self.get_skill(metadata.skill_id)
            if existing is None:
                self.insert_skill(metadata, reason="import_bundle")
                count += 1
        return count

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _row_to_metadata(self, row: sqlite3.Row) -> SkillMetadata:
        """将数据库行转换为 SkillMetadata。"""
        tags_data = json.loads(row["tags_json"] or "{}")
        return SkillMetadata(
            skill_id=row["skill_id"],
            name=row["name"],
            description=row["description"],
            version=row["version"],
            status=SkillStatus(row["status"]),
            scope=SkillScope(row["scope"]),
            tags=SkillTags.from_dict(tags_data),
            trigger_phrases=json.loads(row["trigger_phrases_json"] or "[]"),
            source_runs=json.loads(row["source_runs_json"] or "[]"),
            quality_score=row["quality_score"],
            usage_count=row["usage_count"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            risk_level=RiskLevel(row["risk_level"]),
            storage_path=row["storage_path"],
        )

    def _create_version(
        self,
        skill_id: str,
        version: int,
        parent_version: Optional[int],
        op_id: str,
        metadata: SkillMetadata,
    ) -> SkillVersion:
        """创建版本记录。"""
        snapshot = metadata.to_dict()
        content_hash = hashlib.md5(
            json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

        sv = SkillVersion(
            id=generate_id("ver_"),
            skill_id=skill_id,
            version=version,
            parent_version=parent_version,
            op_id=op_id,
            content_hash=content_hash,
            metadata_snapshot=snapshot,
            created_at=time.time(),
        )

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO skill_versions (
                    id, skill_id, version, parent_version, op_id,
                    content_hash, metadata_snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sv.id,
                    sv.skill_id,
                    sv.version,
                    sv.parent_version,
                    sv.op_id,
                    sv.content_hash,
                    json.dumps(sv.metadata_snapshot, ensure_ascii=False),
                    sv.created_at,
                ),
            )

        return sv

    def _record_curation_event(
        self,
        op_type: CurationOpType,
        skill_id: str,
        source_run: str,
        reason: str,
        confidence: float,
        requires_human_review: bool,
        payload: dict[str, Any],
    ) -> None:
        """记录 curation event。"""
        op_id = generate_id("op_")
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO curation_events (
                    op_id, op, skill_id, source_run, reason,
                    confidence, requires_human_review, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    op_id,
                    op_type.value,
                    skill_id,
                    source_run,
                    reason,
                    confidence,
                    1 if requires_human_review else 0,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                ),
            )

    def get_curation_events(
        self,
        skill_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取 curation 事件。

        Args:
            skill_id: 过滤技能 ID。
            limit: 返回数量。

        Returns:
            事件列表。
        """
        with self._conn() as conn:
            if skill_id:
                rows = conn.execute(
                    "SELECT * FROM curation_events WHERE skill_id=? ORDER BY created_at DESC LIMIT ?",
                    (skill_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM curation_events ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [
            {
                "op_id": row["op_id"],
                "op": row["op"],
                "skill_id": row["skill_id"],
                "source_run": row["source_run"],
                "reason": row["reason"],
                "confidence": row["confidence"],
                "requires_human_review": bool(row["requires_human_review"]),
                "payload": json.loads(row["payload_json"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
