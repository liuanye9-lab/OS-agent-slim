"""Data schemas for Effectiveness A/B testing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class EffectivenessTask:
    """A task definition for A/B comparison."""
    task_id: str
    description: str
    category: str = "general"  # general / architecture / refactoring / bugfix
    created_at: float = field(default_factory=time.time)
    runs: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "category": self.category,
            "created_at": self.created_at,
            "run_count": len(self.runs),
        }


@dataclass
class EffectivenessRun:
    """A single run of a task (baseline or stableagent mode)."""
    run_id: str
    task_id: str
    mode: str  # "baseline" | "stableagent"
    success: bool = True
    edits_made: int = 0
    files_changed: int = 0
    tokens_used: int = 0
    intent_drift: float = 0.0  # 0.0 = perfect alignment, 1.0 = completely drifted
    duration_sec: float = 0.0
    error_message: str = ""
    created_at: float = field(default_factory=time.time)

    # V11.3 新增字段
    model: str = ""  # LLM model used (e.g., "qwen-plus", "gpt-4")
    stableagent_run_id: str = ""  # linked stable agent run ID for traceability
    test_passed: bool = True  # whether automated tests passed after edits
    over_editing: bool = False  # whether over-editing was detected
    rework_count: int = 0  # number of rework iterations needed
    user_satisfaction: float = 3.0  # 1-5 scale user satisfaction rating
    constraint_preservation: float = 1.0  # 0-1 ratio of constraints preserved

    @property
    def edit_efficiency(self) -> float:
        """Edits per token used (higher = more efficient)."""
        if self.tokens_used == 0:
            return 0.0
        return self.edits_made / max(self.tokens_used, 1)

    @property
    def over_editing_ratio(self) -> float:
        """files_changed / edits_made — lower means more focused edits."""
        if self.edits_made == 0:
            return 0.0
        return self.files_changed / max(self.edits_made, 1)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "mode": self.mode,
            "success": self.success,
            "edits_made": self.edits_made,
            "files_changed": self.files_changed,
            "tokens_used": self.tokens_used,
            "intent_drift": round(self.intent_drift, 4),
            "duration_sec": round(self.duration_sec, 2),
            "error_message": self.error_message,
            "created_at": self.created_at,
            # V11.3 new fields
            "model": self.model,
            "stableagent_run_id": self.stableagent_run_id,
            "test_passed": self.test_passed,
            "over_editing": self.over_editing,
            "rework_count": self.rework_count,
            "user_satisfaction": round(self.user_satisfaction, 2),
            "constraint_preservation": round(self.constraint_preservation, 4),
        }


@dataclass
class EffectivenessSummary:
    """Aggregated comparison between baseline and stableagent."""
    task_id: str
    baseline_runs: list = field(default_factory=list)
    stableagent_runs: list = field(default_factory=list)

    # Computed deltas (stableagent - baseline)
    delta_success: float = 0.0
    delta_tokens: float = 0.0
    delta_intent_drift: float = 0.0
    delta_edit_efficiency: float = 0.0
    delta_over_editing: float = 0.0
    delta_constraint_preservation: float = 0.0

    verdict: str = "insufficient_data"  # insufficient_data / promising / effective / not_effective

    def compute_deltas(self) -> None:
        """Compute delta metrics from run lists."""
        b_avg = self._avg(self.baseline_runs)
        s_avg = self._avg(self.stableagent_runs)

        self.delta_success = s_avg.get("success", 0) - b_avg.get("success", 0)
        self.delta_tokens = s_avg.get("tokens_used", 0) - b_avg.get("tokens_used", 0)
        self.delta_intent_drift = s_avg.get("intent_drift", 0) - b_avg.get("intent_drift", 0)
        self.delta_edit_efficiency = s_avg.get("edit_efficiency", 0) - b_avg.get("edit_efficiency", 0)
        self.delta_over_editing = s_avg.get("over_editing", 0) - b_avg.get("over_editing", 0)
        self.delta_constraint_preservation = s_avg.get("constraint_preservation", 0) - b_avg.get("constraint_preservation", 0)

        # Verdict logic
        b_count = len(self.baseline_runs)
        s_count = len(self.stableagent_runs)
        if b_count < 2 or s_count < 2:
            self.verdict = "insufficient_data"
            return

        positive = 0
        if self.delta_success > 0.1:
            positive += 1
        if self.delta_intent_drift < -0.1:  # lower drift is better
            positive += 1
        if self.delta_edit_efficiency > 0.01:
            positive += 1
        if self.delta_constraint_preservation > 0.05:  # higher constraint preservation is better
            positive += 1

        if positive >= 3:
            self.verdict = "effective"
        elif positive >= 2:
            self.verdict = "promising"
        else:
            self.verdict = "not_effective"

    @staticmethod
    def _avg(runs: list) -> dict:
        if not runs:
            return {}
        keys = ["success", "tokens_used", "intent_drift", "edit_efficiency", "over_editing", "constraint_preservation"]
        totals = {k: 0.0 for k in keys}
        for r in runs:
            if isinstance(r, EffectivenessRun):
                totals["success"] += 1.0 if r.success else 0.0
                totals["tokens_used"] += r.tokens_used
                totals["intent_drift"] += r.intent_drift
                totals["edit_efficiency"] += r.edit_efficiency
                totals["over_editing"] += r.over_editing_ratio
                totals["constraint_preservation"] += r.constraint_preservation
            elif isinstance(r, dict):
                totals["success"] += 1.0 if r.get("success") else 0.0
                totals["tokens_used"] += r.get("tokens_used", 0)
                totals["intent_drift"] += r.get("intent_drift", 0)
                ee = r.get("edits_made", 0) / max(r.get("tokens_used", 1), 1)
                totals["edit_efficiency"] += ee
                fc = r.get("files_changed", 0)
                totals["over_editing"] += fc / max(r.get("edits_made", 1), 1)
                totals["constraint_preservation"] += r.get("constraint_preservation", 1.0)
        count = len(runs)
        return {k: v / count for k, v in totals.items()}

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "baseline_count": len(self.baseline_runs),
            "stableagent_count": len(self.stableagent_runs),
            "delta_success": round(self.delta_success, 4),
            "delta_tokens": round(self.delta_tokens, 2),
            "delta_intent_drift": round(self.delta_intent_drift, 4),
            "delta_edit_efficiency": round(self.delta_edit_efficiency, 6),
            "delta_over_editing": round(self.delta_over_editing, 4),
            "delta_constraint_preservation": round(self.delta_constraint_preservation, 4),
            "verdict": self.verdict,
        }
