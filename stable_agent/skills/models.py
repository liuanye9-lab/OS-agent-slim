"""stable_agent/skills/models.py — Skill 数据模型。

定义 Skill 生命周期状态和数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SkillStatus(StrEnum):
    """Skill 生命周期状态。"""
    DRAFT = "draft"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


# 状态转换规则
VALID_TRANSITIONS: dict[SkillStatus, set[SkillStatus]] = {
    SkillStatus.DRAFT: {SkillStatus.CANDIDATE, SkillStatus.ARCHIVED},
    SkillStatus.CANDIDATE: {SkillStatus.VALIDATED, SkillStatus.ARCHIVED},
    SkillStatus.VALIDATED: {SkillStatus.PROMOTED, SkillStatus.DEPRECATED, SkillStatus.ARCHIVED},
    SkillStatus.PROMOTED: {SkillStatus.DEPRECATED, SkillStatus.ARCHIVED},
    SkillStatus.DEPRECATED: {SkillStatus.ARCHIVED},
    SkillStatus.ARCHIVED: set(),  # 终态
}


@dataclass
class SkillRecord:
    """Skill 记录。"""
    skill_id: str
    version: int = 1
    status: SkillStatus = SkillStatus.DRAFT
    domain: str = "general"
    owner: str = "curator_v1"
    created_at: str = ""
    updated_at: str = ""
    retrieval_tags: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    triggers: dict[str, list[str]] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    source_runs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risk_level: str = "low"
    # 内容
    intent: str = ""
    procedure: str = ""
    guardrails: str = ""
    positive_examples: str = ""
    negative_examples: str = ""
    patch_history: str = ""
    # 文件路径
    path: str = ""

    @property
    def is_retrievable(self) -> bool:
        """是否可被检索 (只有 promoted 才进入默认检索)。"""
        return self.status == SkillStatus.PROMOTED

    @property
    def is_candidate(self) -> bool:
        """是否为候选。"""
        return self.status == SkillStatus.CANDIDATE

    @property
    def is_promoted(self) -> bool:
        """是否已晋升。"""
        return self.status == SkillStatus.PROMOTED


@dataclass
class PromotionLogEntry:
    """晋升日志条目。"""
    id: str
    skill_id: str
    from_status: str
    to_status: str
    reason: str
    created_at: str
