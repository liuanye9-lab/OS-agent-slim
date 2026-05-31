"""Tests for effectiveness metrics calculation and formatting."""

import pytest
from stable_agent.effectiveness.metrics import calculate_summary, format_verdict, format_delta
from stable_agent.effectiveness.schemas import EffectivenessRun


# --- calculate_summary tests ---

class TestCalculateSummary:
    """Verify calculate_summary handles all edge cases."""

    def test_empty_runs(self):
        """Empty run list should return zero counts and insufficient_data."""
        result = calculate_summary([], "t1")
        assert result["task_id"] == "t1"
        assert result["baseline_count"] == 0
        assert result["stableagent_count"] == 0
        assert result["verdict"] == "insufficient_data"

    def test_only_baseline_runs(self):
        """Only baseline runs → insufficient_data."""
        runs = [
            EffectivenessRun(run_id="b1", task_id="t1", mode="baseline", success=True, tokens_used=1000),
            EffectivenessRun(run_id="b2", task_id="t1", mode="baseline", success=False, tokens_used=2000),
        ]
        result = calculate_summary(runs, "t1")
        assert result["baseline_count"] == 2
        assert result["stableagent_count"] == 0
        assert result["verdict"] == "insufficient_data"

    def test_single_each_insufficient(self):
        """One baseline + one stableagent → insufficient_data."""
        runs = [
            EffectivenessRun(run_id="b1", task_id="t1", mode="baseline"),
            EffectivenessRun(run_id="s1", task_id="t1", mode="stableagent"),
        ]
        result = calculate_summary(runs, "t1")
        assert result["baseline_count"] == 1
        assert result["stableagent_count"] == 1
        assert result["verdict"] == "insufficient_data"

    def test_dict_format_runs(self):
        """calculate_summary should accept dict-format runs."""
        runs = [
            {"run_id": "b1", "task_id": "t1", "mode": "baseline", "success": True, "tokens_used": 1000,
             "intent_drift": 0.1, "edits_made": 5, "files_changed": 2, "constraint_preservation": 0.9},
            {"run_id": "b2", "task_id": "t1", "mode": "baseline", "success": True, "tokens_used": 1000,
             "intent_drift": 0.1, "edits_made": 5, "files_changed": 2, "constraint_preservation": 0.9},
            {"run_id": "s1", "task_id": "t1", "mode": "stableagent", "success": True, "tokens_used": 500,
             "intent_drift": 0.05, "edits_made": 5, "files_changed": 2, "constraint_preservation": 0.95},
            {"run_id": "s2", "task_id": "t1", "mode": "stableagent", "success": True, "tokens_used": 500,
             "intent_drift": 0.05, "edits_made": 5, "files_changed": 2, "constraint_preservation": 0.95},
        ]
        result = calculate_summary(runs, "t1")
        assert result["baseline_count"] == 2
        assert result["stableagent_count"] == 2
        assert result["delta_tokens"] < 0  # stableagent uses fewer tokens

    def test_all_delta_fields_present(self):
        """Result should contain all delta fields."""
        result = calculate_summary([], "t1")
        required_keys = [
            "task_id", "baseline_count", "stableagent_count",
            "delta_success", "delta_tokens", "delta_intent_drift",
            "delta_edit_efficiency", "delta_over_editing",
            "delta_constraint_preservation", "verdict",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


# --- format_verdict tests ---

class TestFormatVerdict:
    """Verify format_verdict returns correct Chinese labels."""

    def test_insufficient_data(self):
        assert format_verdict("insufficient_data") == "数据不足"

    def test_promising(self):
        assert format_verdict("promising") == "有潜力"

    def test_effective(self):
        assert format_verdict("effective") == "有效"

    def test_not_effective(self):
        assert format_verdict("not_effective") == "未见效"

    def test_unknown_verdict_passthrough(self):
        """Unknown verdict should return as-is."""
        assert format_verdict("unknown_state") == "unknown_state"


# --- format_delta tests ---

class TestFormatDelta:
    """Verify format_delta formatting with direction indicators."""

    def test_near_zero(self):
        assert format_delta(0.0005) == "≈ 持平"
        assert format_delta(-0.0005) == "≈ 持平"
        assert format_delta(0.0) == "≈ 持平"

    def test_positive_higher_is_better(self):
        """Positive delta, higher is better → ↑."""
        result = format_delta(0.5, lower_is_better=False)
        assert "↑" in result

    def test_negative_higher_is_better(self):
        """Negative delta, higher is better → ↓."""
        result = format_delta(-0.5, lower_is_better=False)
        assert "↓" in result

    def test_positive_lower_is_better(self):
        """Positive delta, lower is better → ↑ (worse)."""
        result = format_delta(0.5, lower_is_better=True)
        assert "↑" in result

    def test_negative_lower_is_better(self):
        """Negative delta, lower is better → ↓ (better)."""
        result = format_delta(-0.5, lower_is_better=True)
        assert "↓" in result

    def test_format_includes_value(self):
        """Formatted string should include the numeric value."""
        result = format_delta(0.123)
        assert "0.12" in result
