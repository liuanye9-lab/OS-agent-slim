"""V4 Skill Optimizer data models.

This module defines the core data structures for the Skill Optimization system,
including skill documents, skill edits (patches), rollout trajectories, and
validation results. All types use @dataclass for immutability and StrEnum for
type-safe enumeration values.

Module responsibilities:
- Define skill document lifecycle states and edit operations
- Model rollout trajectories and user feedback signals
- Represent validation results for candidate skill versions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from enum import StrEnum


# ============================================================================
# Enumerations
# ============================================================================


class SkillEditOp(StrEnum):
    """Operations that can be performed when editing a skill document."""

    APPEND = "append"
    INSERT_AFTER = "insert_after"
    REPLACE = "replace"
    DELETE = "delete"


class EditSourceType(StrEnum):
    """The source signal that triggered a skill edit."""

    FAILURE = "failure"
    SUCCESS = "success"
    SLOW_UPDATE = "slow_update"
    MANUAL = "manual"


class SkillStatus(StrEnum):
    """Lifecycle status of a skill document version."""

    DRAFT = "draft"
    CURRENT = "current"
    BEST = "best"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class RiskLevel(StrEnum):
    """Risk level for skill edits (Skill Optimizer scope).

    This is scoped to the skill_optimizer module and has fewer values
    than the main stable_agent.models.RiskLevel enum which includes FORBIDDEN.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SkillDocument:
    """A versioned skill document.

    Represents one version of a skill file, tracking its content,
    provenance, and lifecycle status.

    Attributes:
        id: Unique identifier for this document version.
        version: Semantic version string (e.g., "v1.2.3").
        content: The full markdown/text content of the skill.
        created_at: When this version was created.
        updated_at: When this version was last updated.
        source: Provenance label (e.g., "manual", "auto-optimize").
        score: Quality score assigned by evaluator, None if unranked.
        parent_version: Version string this was derived from, None if original.
        status: Lifecycle status ("draft"/"current"/"best"/"rejected"/"archived").
    """

    id: str
    version: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source: str = ""
    score: float | None = None
    parent_version: str | None = None
    status: Literal["draft", "current", "best", "rejected", "archived"] = "draft"


@dataclass
class SkillEdit:
    """A single atomic edit operation on a skill document.

    Each edit targets a specific location in the skill document and
    carries metadata about why it was generated and how confident
    the system is about it.

    Attributes:
        id: Unique identifier for this edit.
        op: The edit operation type (append/insert_after/replace/delete).
        target: For insert_after/replace: anchor text to locate. None for append.
        content: New content to insert/replace. None for delete.
        reason: Human-readable explanation of why this edit was generated.
        source_type: What signal triggered this edit.
        support_count: Number of rollouts that support this edit.
        risk_level: Estimated risk of applying this edit.
        created_at: When this edit was generated.
    """

    id: str
    op: Literal["append", "insert_after", "replace", "delete"]
    target: str | None = None
    content: str | None = None
    reason: str = ""
    source_type: Literal["failure", "success", "slow_update", "manual"] = "failure"
    support_count: int = 0
    risk_level: Literal["low", "medium", "high"] = "medium"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SkillPatch:
    """A collection of SkillEdits bundled as a candidate improvement.

    Groups related edits together with reasoning and estimated impact
    metrics. Used as the unit of evaluation during the validation gate.

    Attributes:
        id: Unique identifier for this patch.
        edits: Ordered list of SkillEdit operations.
        reasoning: Chain-of-thought explanation for the whole patch.
        source_rollout_ids: IDs of rollouts that informed this patch.
        estimated_impact: Predicted score improvement (can be negative).
        estimated_risk: Predicted risk of regression.
        created_at: When this patch was created.
    """

    id: str
    edits: list[SkillEdit] = field(default_factory=list)
    reasoning: str = ""
    source_rollout_ids: list[str] = field(default_factory=list)
    estimated_impact: float = 0.0
    estimated_risk: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RolloutTrajectory:
    """A complete rollout record capturing one task execution.

    Captures the full lifecycle: task input, model output, user feedback,
    evaluation scores, and token usage. Rollouts are the raw material
    for failure analysis and success pattern extraction.

    Attributes:
        id: Unique identifier for this rollout.
        task_input: The user's original task text.
        task_type: Classification label for the task.
        user_intent_guess: System's inferred user intent.
        context_pack: Serialized context pack used during execution.
        skill_version: Version of the skill used in this rollout.
        model_output: The model's full response text.
        user_feedback: "accepted", "edited", "rejected", or "unknown".
        eval_scores: Dimension-level evaluation scores.
        trace_events: Raw trace event data from the execution.
        token_usage: Token consumption breakdown.
        created_at: When this rollout was recorded.
    """

    id: str
    task_input: str
    task_type: str = ""
    user_intent_guess: str = ""
    context_pack: str = ""
    skill_version: str = ""
    model_output: str = ""
    user_feedback: Literal["accepted", "edited", "rejected", "unknown"] = "unknown"
    eval_scores: dict[str, float] = field(default_factory=dict)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    """Result of comparing a candidate skill against a baseline.

    Used by the validation gate (Phase 4) to decide whether a candidate
    skill version should be promoted to BEST.

    Attributes:
        candidate_skill_version: Version string of the candidate.
        baseline_skill_version: Version string of the baseline (current BEST).
        baseline_score: Aggregate score of the baseline.
        candidate_score: Aggregate score of the candidate.
        passed: True if candidate meets or exceeds baseline.
        score_delta: candidate_score - baseline_score.
        regression_cases: List of eval case IDs where candidate regressed.
        explanation: Human-readable explanation of the result.
    """

    candidate_skill_version: str
    baseline_skill_version: str
    baseline_score: float = 0.0
    candidate_score: float = 0.0
    passed: bool = False
    score_delta: float = 0.0
    regression_cases: list[str] = field(default_factory=list)
    explanation: str = ""
