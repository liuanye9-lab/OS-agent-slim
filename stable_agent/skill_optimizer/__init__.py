"""Skill Optimizer package (V4).

Provides the core data models and utilities for the skill optimization loop:
rollout collection, failure/success analysis, patch generation, candidate
evaluation, and validation gating.
"""

from .models import (
    EditSourceType,
    RiskLevel,
    RolloutTrajectory,
    SkillDocument,
    SkillEdit,
    SkillEditOp,
    SkillPatch,
    SkillStatus,
    ValidationResult,
)

__all__ = [
    "SkillDocument",
    "SkillEdit",
    "SkillPatch",
    "RolloutTrajectory",
    "ValidationResult",
    "SkillEditOp",
    "EditSourceType",
    "SkillStatus",
    "RiskLevel",
]
