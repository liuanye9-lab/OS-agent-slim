"""stable_agent.capsule.schemas — Agent Capsule 数据结构定义。

定义 CapsuleManifest、CapsuleStats、CapsuleDoctorReport、
MemoryRecord 等核心数据结构。所有字段支持 JSON 序列化。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def _new_id(prefix: str = "cap") -> str:
    """生成唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=False)
class CapsuleStats:
    """胶囊统计信息。

    Attributes:
        memory_count: 记忆条目总数。
        skill_count: 技能文档数量。
        bad_case_count: 失败案例数量。
        eval_case_count: 评测用例数量。
    """

    memory_count: int = 0
    skill_count: int = 0
    bad_case_count: int = 0
    eval_case_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_count": self.memory_count,
            "skill_count": self.skill_count,
            "bad_case_count": self.bad_case_count,
            "eval_case_count": self.eval_case_count,
        }


@dataclass(frozen=False)
class CapsuleManifest:
    """胶囊清单文件 schema。

    对应 capsule_manifest.json 的核心字段。

    Attributes:
        capsule_id: 胶囊唯一 ID。
        schema_version: 格式版本号。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
        owner_label: 所有者标签。
        project_scope: 项目范围（global 或 project）。
        default_project_id: 默认项目 ID（可选）。
        storage_mode: 存储模式（local-first）。
        encryption_enabled: 是否启用加密。
        encryption_method: 加密方法（可选）。
        stats: 统计信息。
    """

    capsule_id: str = ""
    schema_version: str = "v11"
    created_at: float = 0.0
    updated_at: float = 0.0
    owner_label: str = "local-user"
    project_scope: str = "global"
    default_project_id: str | None = None
    storage_mode: str = "local-first"
    encryption_enabled: bool = False
    encryption_method: str | None = None
    stats: CapsuleStats = field(default_factory=CapsuleStats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "owner_label": self.owner_label,
            "project_scope": self.project_scope,
            "default_project_id": self.default_project_id,
            "storage_mode": self.storage_mode,
            "encryption": {
                "enabled": self.encryption_enabled,
                "method": self.encryption_method,
            },
            "stats": self.stats.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapsuleManifest:
        """从字典创建 CapsuleManifest。"""
        enc = data.get("encryption", {})
        stats_data = data.get("stats", {})
        return cls(
            capsule_id=data.get("capsule_id", ""),
            schema_version=data.get("schema_version", "v11"),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            owner_label=data.get("owner_label", "local-user"),
            project_scope=data.get("project_scope", "global"),
            default_project_id=data.get("default_project_id"),
            storage_mode=data.get("storage_mode", "local-first"),
            encryption_enabled=enc.get("enabled", False),
            encryption_method=enc.get("method"),
            stats=CapsuleStats(
                memory_count=stats_data.get("memory_count", 0),
                skill_count=stats_data.get("skill_count", 0),
                bad_case_count=stats_data.get("bad_case_count", 0),
                eval_case_count=stats_data.get("eval_case_count", 0),
            ),
        )


@dataclass(frozen=False)
class CapsuleDoctorReport:
    """胶囊健康检查报告。

    Attributes:
        ok: 是否总体健康。
        health_score: 健康分数（0~1）。
        warnings: 警告列表。
        errors: 错误列表。
        suggestions: 建议列表。
        stats: 统计信息。
    """

    ok: bool = True
    health_score: float = 1.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "health_score": self.health_score,
            "warnings": self.warnings,
            "errors": self.errors,
            "suggestions": self.suggestions,
            "stats": self.stats,
        }


@dataclass(frozen=False)
class MemoryRecord:
    """记忆记录 schema。

    四层记忆结构的核心数据结构：
    raw_episode / episode_summary / semantic_memory / skill_rule / regression_case
    """

    memory_id: str = ""
    content: str = ""
    memory_type: str = "raw_episode"
    scope: str = "global"
    project_id: str | None = None
    source: str = "run_trace"
    source_run_id: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    valid_from: float = 0.0
    valid_until: float | None = None
    confidence: float = 0.5
    source_quality: float = 0.5
    reuse_count: int = 0
    last_used_at: float | None = None
    confirmed_by_user: bool = False
    conflict_count: int = 0
    superseded_by: str | None = None
    tags: list[str] = field(default_factory=list)
    risk_level: str = "low"
    sensitive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "scope": self.scope,
            "project_id": self.project_id,
            "source": self.source,
            "source_run_id": self.source_run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "confidence": self.confidence,
            "source_quality": self.source_quality,
            "reuse_count": self.reuse_count,
            "last_used_at": self.last_used_at,
            "confirmed_by_user": self.confirmed_by_user,
            "conflict_count": self.conflict_count,
            "superseded_by": self.superseded_by,
            "tags": self.tags,
            "risk_level": self.risk_level,
            "sensitive": self.sensitive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
