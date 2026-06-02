"""stable_agent.skills.schema — SkillOS 数据模型。

定义技能库核心数据结构：SkillMetadata, SkillPackage, CurationOp, SkillVersion。
使用 dataclass 保持轻量，支持 JSON 序列化，兼容 Python 3.11+。

不引入重型 ORM，不破坏 stable_agent.models。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Any, Optional


# ============================================================================
# 枚举定义
# ============================================================================


class SkillStatus(StrEnum):
    """技能状态枚举。"""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    DRAFT = "draft"


class CurationOpType(StrEnum):
    """策展操作类型枚举。"""

    INSERT_SKILL = "insert_skill"
    UPDATE_SKILL = "update_skill"
    DELETE_SKILL = "delete_skill"
    ARCHIVE_SKILL = "archive_skill"
    MERGE_SKILL = "merge_skill"


class SkillScope(StrEnum):
    """技能作用域枚举。"""

    GLOBAL = "global"
    PROJECT = "project"
    WORKER = "worker"


class RiskLevel(StrEnum):
    """风险等级枚举。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class SkillTags:
    """技能标签集合。"""

    topic: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    heuristics: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillTags:
        """从字典创建。"""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}
        return cls(
            topic=data.get("topic", []),
            capabilities=data.get("capabilities", []),
            concepts=data.get("concepts", []),
            heuristics=data.get("heuristics", []),
            pitfalls=data.get("pitfalls", []),
        )


@dataclass
class SkillMetadata:
    """技能元数据。

    Attributes:
        skill_id: 技能唯一标识。
        name: 技能名称 (slug 格式)。
        description: 技能描述。
        version: 当前版本号。
        status: 技能状态。
        scope: 作用域。
        tags: 标签集合。
        trigger_phrases: 触发短语列表。
        source_runs: 来源运行 ID 列表。
        quality_score: 质量分数 (0.0-1.0)。
        usage_count: 使用次数。
        success_count: 成功次数。
        failure_count: 失败次数。
        last_used_at: 最后使用时间。
        created_at: 创建时间。
        updated_at: 更新时间。
        created_by: 创建来源。
        risk_level: 风险等级。
        storage_path: 存储路径。
    """

    skill_id: str = ""
    name: str = ""
    description: str = ""
    version: int = 1
    status: SkillStatus = SkillStatus.ACTIVE
    scope: SkillScope = SkillScope.GLOBAL
    tags: SkillTags = field(default_factory=SkillTags)
    trigger_phrases: list[str] = field(default_factory=list)
    source_runs: list[str] = field(default_factory=list)
    quality_score: float = 0.5
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "curator"  # curator | user | seed
    risk_level: RiskLevel = RiskLevel.LOW
    storage_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为可 JSON 序列化的字典。"""
        d = asdict(self)
        d["status"] = self.status.value
        d["scope"] = self.scope.value
        d["risk_level"] = self.risk_level.value
        d["tags"] = self.tags.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillMetadata:
        """从字典创建。"""
        tags_data = data.get("tags", {})
        tags = SkillTags.from_dict(tags_data) if isinstance(tags_data, (dict, str)) else SkillTags()
        return cls(
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", 1),
            status=SkillStatus(data.get("status", "active")),
            scope=SkillScope(data.get("scope", "global")),
            tags=tags,
            trigger_phrases=data.get("trigger_phrases", []),
            source_runs=data.get("source_runs", []),
            quality_score=data.get("quality_score", 0.5),
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            last_used_at=data.get("last_used_at"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            created_by=data.get("created_by", "curator"),
            risk_level=RiskLevel(data.get("risk_level", "low")),
            storage_path=data.get("storage_path", ""),
        )

    def to_json(self) -> str:
        """JSON 序列化。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> SkillMetadata:
        """从 JSON 反序列化。"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SkillPackage:
    """技能包。

    Attributes:
        skill_id: 技能 ID。
        storage_path: 存储路径。
        entry_type: 入口类型。
        files: 文件列表。
        metadata: 技能元数据。
    """

    skill_id: str = ""
    storage_path: str = ""
    entry_type: str = "directory_skill"
    files: list[str] = field(default_factory=list)
    metadata: SkillMetadata = field(default_factory=SkillMetadata)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "skill_id": self.skill_id,
            "storage_path": self.storage_path,
            "entry_type": self.entry_type,
            "files": self.files,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillPackage:
        """从字典创建。"""
        return cls(
            skill_id=data.get("skill_id", ""),
            storage_path=data.get("storage_path", ""),
            entry_type=data.get("entry_type", "directory_skill"),
            files=data.get("files", []),
            metadata=SkillMetadata.from_dict(data.get("metadata", {})),
        )


@dataclass
class CurationOp:
    """策展操作。

    Attributes:
        op_id: 操作 ID。
        op: 操作类型。
        skill_id: 目标技能 ID。
        new_skill: 新技能数据 (insert 时使用)。
        patch: 补丁数据 (update 时使用)。
        reason: 操作原因。
        source_run: 来源运行 ID。
        confidence: 置信度。
        requires_human_review: 是否需要人工审核。
        created_at: 创建时间。
    """

    op_id: str = ""
    op: CurationOpType = CurationOpType.INSERT_SKILL
    skill_id: str = ""
    new_skill: Optional[SkillMetadata] = None
    patch: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    source_run: str = ""
    confidence: float = 0.0
    requires_human_review: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "op_id": self.op_id,
            "op": self.op.value,
            "skill_id": self.skill_id,
            "new_skill": self.new_skill.to_dict() if self.new_skill else None,
            "patch": self.patch,
            "reason": self.reason,
            "source_run": self.source_run,
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurationOp:
        """从字典创建。"""
        new_skill_data = data.get("new_skill")
        return cls(
            op_id=data.get("op_id", ""),
            op=CurationOpType(data.get("op", "insert_skill")),
            skill_id=data.get("skill_id", ""),
            new_skill=SkillMetadata.from_dict(new_skill_data) if new_skill_data else None,
            patch=data.get("patch", {}),
            reason=data.get("reason", ""),
            source_run=data.get("source_run", ""),
            confidence=data.get("confidence", 0.0),
            requires_human_review=data.get("requires_human_review", True),
            created_at=data.get("created_at", time.time()),
        )

    def to_json(self) -> str:
        """JSON 序列化。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> CurationOp:
        """从 JSON 反序列化。"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SkillVersion:
    """技能版本记录。

    Attributes:
        id: 版本记录 ID。
        skill_id: 技能 ID。
        version: 版本号。
        parent_version: 父版本号。
        op_id: 关联操作 ID。
        content_hash: 内容哈希。
        metadata_snapshot: 元数据快照。
        created_at: 创建时间。
    """

    id: str = ""
    skill_id: str = ""
    version: int = 1
    parent_version: Optional[int] = None
    op_id: str = ""
    content_hash: str = ""
    metadata_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillVersion:
        """从字典创建。"""
        return cls(
            id=data.get("id", ""),
            skill_id=data.get("skill_id", ""),
            version=data.get("version", 1),
            parent_version=data.get("parent_version"),
            op_id=data.get("op_id", ""),
            content_hash=data.get("content_hash", ""),
            metadata_snapshot=data.get("metadata_snapshot", {}),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class SkillSearchResult:
    """技能搜索结果。

    Attributes:
        skill_id: 技能 ID。
        name: 技能名称。
        description: 技能描述。
        score: 匹配分数。
        matched_terms: 匹配的词项。
        reason: 命中原因。
    """

    skill_id: str = ""
    name: str = ""
    description: str = ""
    score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillSearchResult:
        """从字典创建。"""
        return cls(
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            score=data.get("score", 0.0),
            matched_terms=data.get("matched_terms", []),
            reason=data.get("reason", ""),
        )


@dataclass
class SkillUsageRecord:
    """技能使用记录。

    Attributes:
        id: 记录 ID。
        run_id: 运行 ID。
        skill_id: 技能 ID。
        task_id: 任务 ID。
        used_at: 使用时间。
        outcome: 结果 (success/failure)。
        token_cost: Token 消耗。
        attribution_score: 归因分数。
    """

    id: str = ""
    run_id: str = ""
    skill_id: str = ""
    task_id: str = ""
    used_at: float = field(default_factory=time.time)
    outcome: str = ""
    token_cost: int = 0
    attribution_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillUsageRecord:
        """从字典创建。"""
        return cls(
            id=data.get("id", ""),
            run_id=data.get("run_id", ""),
            skill_id=data.get("skill_id", ""),
            task_id=data.get("task_id", ""),
            used_at=data.get("used_at", time.time()),
            outcome=data.get("outcome", ""),
            token_cost=data.get("token_cost", 0),
            attribution_score=data.get("attribution_score", 0.0),
        )


@dataclass
class ValidationReport:
    """验证报告。"""

    ok: bool = True
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApplyResult:
    """应用结果。"""

    ok: bool = True
    applied_ops: list[str] = field(default_factory=list)
    rejected_ops: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CuratorRunResult:
    """策展运行结果。"""

    ok: bool = True
    run_id: str = ""
    proposed_ops: list[CurationOp] = field(default_factory=list)
    applied_ops: list[str] = field(default_factory=list)
    rejected_ops: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "ok": self.ok,
            "run_id": self.run_id,
            "proposed_ops": [op.to_dict() for op in self.proposed_ops],
            "applied_ops": self.applied_ops,
            "rejected_ops": self.rejected_ops,
            "errors": self.errors,
        }
        return d


def generate_id(prefix: str = "") -> str:
    """生成唯一 ID。"""
    short = uuid.uuid4().hex[:12]
    return f"{prefix}{short}" if prefix else short
