"""V4 Skill Optimizer data model unit tests.

Covers all V4 enumerations, data class defaults, field validation,
and SpanType extensions. Must run alongside existing 348 tests
without regressions.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from stable_agent.skill_optimizer.models import (
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
from stable_agent.models import SpanType


# ============================================================================
# SkillEditOp Enum
# ============================================================================


class TestSkillEditOp:
    """Tests for SkillEditOp enumeration."""

    def test_skill_edit_op_values(self) -> None:
        """Verify all SkillEditOp values are correctly defined."""
        assert SkillEditOp.APPEND.value == "append"
        assert SkillEditOp.INSERT_AFTER.value == "insert_after"
        assert SkillEditOp.REPLACE.value == "replace"
        assert SkillEditOp.DELETE.value == "delete"


# ============================================================================
# EditSourceType Enum
# ============================================================================


class TestEditSourceType:
    """Tests for EditSourceType enumeration."""

    def test_edit_source_type_values(self) -> None:
        """Verify all EditSourceType values are correctly defined."""
        assert EditSourceType.FAILURE.value == "failure"
        assert EditSourceType.SUCCESS.value == "success"
        assert EditSourceType.SLOW_UPDATE.value == "slow_update"
        assert EditSourceType.MANUAL.value == "manual"


# ============================================================================
# SkillStatus Enum
# ============================================================================


class TestSkillStatus:
    """Tests for SkillStatus enumeration."""

    def test_skill_status_values(self) -> None:
        """Verify all SkillStatus values are correctly defined."""
        assert SkillStatus.DRAFT.value == "draft"
        assert SkillStatus.CURRENT.value == "current"
        assert SkillStatus.BEST.value == "best"
        assert SkillStatus.REJECTED.value == "rejected"
        assert SkillStatus.ARCHIVED.value == "archived"


# ============================================================================
# RiskLevel Enum (Skill Optimizer scope)
# ============================================================================


class TestSkillOptRiskLevel:
    """Tests for skill_optimizer-scoped RiskLevel enumeration."""

    def test_risk_level_values(self) -> None:
        """Verify RiskLevel values in skill_optimizer scope."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"


# ============================================================================
# SkillDocument
# ============================================================================


class TestSkillDocument:
    """Tests for SkillDocument data class."""

    def test_skill_document_defaults(self) -> None:
        """Verify default field values are correct."""
        doc = SkillDocument(id="doc-1", version="v1.0.0", content="# Test")
        assert doc.id == "doc-1"
        assert doc.version == "v1.0.0"
        assert doc.content == "# Test"
        assert doc.source == ""
        assert doc.score is None
        assert doc.parent_version is None
        assert doc.status == "draft"
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)

    def test_skill_document_full_init(self) -> None:
        """Verify full initialization with all fields set."""
        now = datetime.now()
        doc = SkillDocument(
            id="doc-2",
            version="v2.1.0",
            content="## Updated",
            created_at=now,
            updated_at=now,
            source="auto-optimize",
            score=0.95,
            parent_version="v2.0.0",
            status="best",
        )
        assert doc.id == "doc-2"
        assert doc.version == "v2.1.0"
        assert doc.source == "auto-optimize"
        assert doc.score == 0.95
        assert doc.parent_version == "v2.0.0"
        assert doc.status == "best"

    def test_skill_status_values(self) -> None:
        """Verify SkillStatus enum integrates with SkillDocument."""
        doc = SkillDocument(id="d", version="v1", content="x")
        assert doc.status == "draft"  # default

        doc.status = "current"
        assert doc.status == SkillStatus.CURRENT.value

        doc.status = "best"
        assert doc.status == SkillStatus.BEST.value

        doc.status = "rejected"
        assert doc.status == SkillStatus.REJECTED.value

        doc.status = "archived"
        assert doc.status == SkillStatus.ARCHIVED.value


# ============================================================================
# SkillEdit
# ============================================================================


class TestSkillEdit:
    """Tests for SkillEdit data class."""

    def test_skill_edit_default_source_type(self) -> None:
        """Verify source_type defaults to 'failure'."""
        edit = SkillEdit(id="e-1", op="append")
        assert edit.source_type == "failure"

    def test_skill_edit_append_op(self) -> None:
        """Verify an append operation with content."""
        edit = SkillEdit(
            id="e-2",
            op="append",
            content="New section",
            reason="User requested this",
            source_type="manual",
        )
        assert edit.op == "append"
        assert edit.target is None
        assert edit.content == "New section"
        assert edit.reason == "User requested this"

    def test_skill_edit_replace_requires_target(self) -> None:
        """Verify replace op stores a target anchor."""
        edit = SkillEdit(
            id="e-3",
            op="replace",
            target="old text",
            content="new text",
            risk_level="high",
            support_count=5,
        )
        assert edit.op == "replace"
        assert edit.target == "old text"
        assert edit.content == "new text"
        assert edit.risk_level == "high"
        assert edit.support_count == 5

    def test_skill_edit_all_ops_valid(self) -> None:
        """Verify all four edit operations can be instantiated."""
        for op in ("append", "insert_after", "replace", "delete"):
            edit = SkillEdit(id=f"e-{op}", op=op)
            assert edit.op == op
            assert edit.source_type in ("failure", "success", "slow_update", "manual")

    def test_skill_edit_defaults(self) -> None:
        """Verify default values for optional fields."""
        edit = SkillEdit(id="e-default", op="delete")
        assert edit.target is None
        assert edit.content is None
        assert edit.reason == ""
        assert edit.source_type == "failure"
        assert edit.support_count == 0
        assert edit.risk_level == "medium"
        assert isinstance(edit.created_at, datetime)


# ============================================================================
# SkillPatch
# ============================================================================


class TestSkillPatch:
    """Tests for SkillPatch data class."""

    def test_skill_patch_defaults(self) -> None:
        """Verify default field values."""
        patch = SkillPatch(id="p-1")
        assert patch.id == "p-1"
        assert patch.edits == []
        assert patch.reasoning == ""
        assert patch.source_rollout_ids == []
        assert patch.estimated_impact == 0.0
        assert patch.estimated_risk == 0.0
        assert isinstance(patch.created_at, datetime)

    def test_skill_patch_with_edits(self) -> None:
        """Verify patch can hold multiple edits with reasoning."""
        edit1 = SkillEdit(id="e-a", op="append", content="step 1")
        edit2 = SkillEdit(id="e-b", op="replace", target="old", content="new")
        patch = SkillPatch(
            id="p-2",
            edits=[edit1, edit2],
            reasoning="These edits fix the root cause",
            source_rollout_ids=["r1", "r2", "r3"],
            estimated_impact=0.15,
            estimated_risk=0.05,
        )
        assert len(patch.edits) == 2
        assert patch.edits[0].id == "e-a"
        assert patch.edits[1].id == "e-b"
        assert patch.reasoning == "These edits fix the root cause"
        assert patch.source_rollout_ids == ["r1", "r2", "r3"]
        assert patch.estimated_impact == 0.15
        assert patch.estimated_risk == 0.05


# ============================================================================
# RolloutTrajectory
# ============================================================================


class TestRolloutTrajectory:
    """Tests for RolloutTrajectory data class."""

    def test_rollout_trajectory_defaults(self) -> None:
        """Verify default field values."""
        rt = RolloutTrajectory(id="rt-1", task_input="Fix bug in login")
        assert rt.id == "rt-1"
        assert rt.task_input == "Fix bug in login"
        assert rt.task_type == ""
        assert rt.user_intent_guess == ""
        assert rt.context_pack == ""
        assert rt.skill_version == ""
        assert rt.model_output == ""
        assert rt.user_feedback == "unknown"
        assert rt.eval_scores == {}
        assert rt.trace_events == []
        assert rt.token_usage == {}
        assert isinstance(rt.created_at, datetime)

    def test_rollout_trajectory_with_feedback(self) -> None:
        """Verify all user_feedback values are accepted."""
        rt = RolloutTrajectory(
            id="rt-2",
            task_input="Write docs",
            user_feedback="accepted",
            eval_scores={"overall": 0.92},
            token_usage={"input": 500, "output": 200},
        )
        assert rt.user_feedback == "accepted"
        assert rt.eval_scores["overall"] == 0.92
        assert rt.token_usage["input"] == 500

        rt2 = RolloutTrajectory(id="rt-3", task_input="x", user_feedback="edited")
        assert rt2.user_feedback == "edited"

        rt3 = RolloutTrajectory(id="rt-4", task_input="x", user_feedback="rejected")
        assert rt3.user_feedback == "rejected"


# ============================================================================
# ValidationResult
# ============================================================================


class TestValidationResult:
    """Tests for ValidationResult data class."""

    def test_validation_result_defaults(self) -> None:
        """Verify default field values."""
        vr = ValidationResult(
            candidate_skill_version="v2.0.0",
            baseline_skill_version="v1.0.0",
        )
        assert vr.candidate_skill_version == "v2.0.0"
        assert vr.baseline_skill_version == "v1.0.0"
        assert vr.baseline_score == 0.0
        assert vr.candidate_score == 0.0
        assert vr.passed is False
        assert vr.score_delta == 0.0
        assert vr.regression_cases == []
        assert vr.explanation == ""

    def test_validation_result_passed_true(self) -> None:
        """Verify passed=True when candidate beats baseline."""
        vr = ValidationResult(
            candidate_skill_version="v3.0.0",
            baseline_skill_version="v2.0.0",
            baseline_score=0.80,
            candidate_score=0.87,
            passed=True,
            score_delta=0.07,
            explanation="Candidate improved on 3 evals, no regressions.",
        )
        assert vr.passed is True
        assert vr.score_delta == 0.07
        assert vr.candidate_score > vr.baseline_score

    def test_validation_result_score_delta(self) -> None:
        """Verify score_delta = candidate - baseline."""
        vr = ValidationResult(
            candidate_skill_version="v1.1",
            baseline_skill_version="v1.0",
            baseline_score=0.75,
            candidate_score=0.65,
            score_delta=-0.10,
            regression_cases=["eval-42"],
        )
        assert vr.score_delta == -0.10
        assert vr.passed is False
        assert "eval-42" in vr.regression_cases

    def test_validation_result_regression_cases(self) -> None:
        """Verify regression_cases list tracks failing evals."""
        vr = ValidationResult(
            candidate_skill_version="v2",
            baseline_skill_version="v1",
            regression_cases=["eval-a", "eval-b", "eval-c"],
        )
        assert len(vr.regression_cases) == 3
        assert "eval-a" in vr.regression_cases


# ============================================================================
# SpanType Extensions (V4)
# ============================================================================


class TestSpanTypeSkillOpt:
    """Tests for V4 skill optimizer SpanType values."""

    def test_spantype_skillopt_values(self) -> None:
        """Verify all 12 V4 SpanType values are correctly defined."""
        assert SpanType.SKILLOPT_EPOCH_STARTED.value == "skillopt.epoch_started"
        assert SpanType.SKILLOPT_ROLLOUTS_COLLECTED.value == "skillopt.rollouts_collected"
        assert SpanType.SKILLOPT_FAILURES_ANALYZED.value == "skillopt.failures_analyzed"
        assert SpanType.SKILLOPT_SUCCESSES_ANALYZED.value == "skillopt.successes_analyzed"
        assert SpanType.SKILLOPT_PATCH_MERGED.value == "skillopt.patch_merged"
        assert SpanType.SKILLOPT_PATCH_RANKED.value == "skillopt.patch_ranked"
        assert SpanType.SKILLOPT_CANDIDATE_CREATED.value == "skillopt.candidate_created"
        assert SpanType.SKILLOPT_VALIDATION_PASSED.value == "skillopt.validation_passed"
        assert SpanType.SKILLOPT_VALIDATION_FAILED.value == "skillopt.validation_failed"
        assert SpanType.SKILLOPT_REJECTED_BUFFER_UPDATED.value == "skillopt.rejected_buffer_updated"
        assert SpanType.SKILLOPT_SLOW_UPDATE_CREATED.value == "skillopt.slow_update_created"
        assert SpanType.SKILLOPT_BEST_SKILL_EXPORTED.value == "skillopt.best_skill_exported"

    def test_spantype_total_count(self) -> None:
        """Verify total SpanType members = 9 (V3) + 12 (V4) = 21."""
        members = list(SpanType)
        assert len(members) == 21, (
            f"Expected 21 SpanType members (9 V3 + 12 V4), got {len(members)}"
        )

    def test_spantype_v3_values_preserved(self) -> None:
        """Verify V3 SpanType values are still present."""
        assert SpanType.MEMORY_RETRIEVAL.value == "memory_retrieval"
        assert SpanType.RAG_RETRIEVAL.value == "rag_retrieval"
        assert SpanType.LLM_CALL.value == "llm_call"
        assert SpanType.TOOL_CALL.value == "tool_call"
        assert SpanType.EVAL.value == "eval"
        assert SpanType.PLAN.value == "plan"
        assert SpanType.EXECUTE.value == "execute"
        assert SpanType.LEARN.value == "learn"
        assert SpanType.APPROVAL.value == "approval"


# ============================================================================
# Package Export Tests
# ============================================================================


class TestSkillOptimizerExports:
    """Tests for skill_optimizer package public API."""

    def test_skill_optimizer_exports(self) -> None:
        """Verify core types are importable from the package."""
        from stable_agent.skill_optimizer import (
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

        # Spot-check that these are the right types
        assert SkillEditOp.APPEND.value == "append"
        assert EditSourceType.FAILURE.value == "failure"
        assert SkillStatus.DRAFT.value == "draft"
        assert RiskLevel.LOW.value == "low"

        # Verify data classes are importable as types
        assert SkillDocument is not None
        assert SkillEdit is not None
        assert SkillPatch is not None
        assert RolloutTrajectory is not None
        assert ValidationResult is not None
