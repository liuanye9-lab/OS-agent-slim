"""Tests for V11.3 Effectiveness module."""

from __future__ import annotations

import json
import os
import tempfile
import pytest

from stable_agent.effectiveness.schemas import EffectivenessTask, EffectivenessRun, EffectivenessSummary
from stable_agent.effectiveness.experiment_store import ExperimentStore
from stable_agent.effectiveness.metrics import calculate_summary, format_verdict, format_delta


# -- Schema Tests --

class TestEffectivenessTask:
    def test_create_task(self):
        task = EffectivenessTask(task_id="test-1", description="Fix auth bug")
        assert task.task_id == "test-1"
        assert task.description == "Fix auth bug"
        assert task.category == "general"

    def test_to_dict(self):
        task = EffectivenessTask(task_id="t1", description="desc", category="bugfix")
        d = task.to_dict()
        assert d["task_id"] == "t1"
        assert d["category"] == "bugfix"
        assert d["run_count"] == 0


class TestEffectivenessRun:
    def test_create_run(self):
        run = EffectivenessRun(run_id="r1", task_id="t1", mode="stableagent")
        assert run.mode == "stableagent"
        assert run.success is True

    def test_edit_efficiency(self):
        run = EffectivenessRun(run_id="r1", task_id="t1", mode="baseline",
                               edits_made=10, tokens_used=1000)
        assert run.edit_efficiency == pytest.approx(0.01, abs=0.001)

    def test_over_editing_ratio(self):
        run = EffectivenessRun(run_id="r1", task_id="t1", mode="baseline",
                               edits_made=10, files_changed=3)
        assert run.over_editing_ratio == pytest.approx(0.3, abs=0.001)

    def test_to_dict(self):
        run = EffectivenessRun(run_id="r1", task_id="t1", mode="stableagent",
                               success=True, tokens_used=500)
        d = run.to_dict()
        assert d["run_id"] == "r1"
        assert d["tokens_used"] == 500


class TestEffectivenessSummary:
    def test_compute_deltas_insufficient_data(self):
        s = EffectivenessSummary(task_id="t1")
        s.compute_deltas()
        assert s.verdict == "insufficient_data"

    def test_compute_deltas_effective(self):
        baseline_runs = [
            EffectivenessRun(run_id="b1", task_id="t1", mode="baseline",
                            success=False, edits_made=5, tokens_used=2000,
                            files_changed=3, intent_drift=0.5,
                            constraint_preservation=0.6),
            EffectivenessRun(run_id="b2", task_id="t1", mode="baseline",
                            success=False, edits_made=6, tokens_used=2200,
                            files_changed=4, intent_drift=0.6,
                            constraint_preservation=0.5),
        ]
        stableagent_runs = [
            EffectivenessRun(run_id="s1", task_id="t1", mode="stableagent",
                            success=True, edits_made=8, tokens_used=1000,
                            files_changed=2, intent_drift=0.1,
                            constraint_preservation=0.95),
            EffectivenessRun(run_id="s2", task_id="t1", mode="stableagent",
                            success=True, edits_made=9, tokens_used=1100,
                            files_changed=2, intent_drift=0.2,
                            constraint_preservation=0.9),
        ]
        s = EffectivenessSummary(task_id="t1",
                                baseline_runs=baseline_runs,
                                stableagent_runs=stableagent_runs)
        s.compute_deltas()
        assert s.verdict == "effective"
        assert s.delta_success > 0
        assert s.delta_tokens < 0
        assert s.delta_intent_drift < 0


# -- Store Tests --

class TestExperimentStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = ExperimentStore(data_dir=self.tmpdir)

    def test_create_and_get_task(self):
        task = EffectivenessTask(task_id="t1", description="test")
        self.store.create_task(task)
        result = self.store.get_task("t1")
        assert result is not None
        assert result["task_id"] == "t1"

    def test_record_and_get_runs(self):
        run = EffectivenessRun(run_id="r1", task_id="t1", mode="baseline")
        self.store.record_run(run)
        runs = self.store.get_runs(task_id="t1")
        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"

    def test_get_summary(self):
        # Create task
        task = EffectivenessTask(task_id="t1", description="test")
        self.store.create_task(task)

        # Record runs
        for mode in ["baseline", "stableagent"]:
            for i in range(3):
                run = EffectivenessRun(
                    run_id=f"r_{mode}_{i}",
                    task_id="t1",
                    mode=mode,
                    success=mode == "stableagent",
                    edits_made=5 if mode == "baseline" else 8,
                    tokens_used=2000 if mode == "baseline" else 1000,
                    files_changed=3,
                    intent_drift=0.5 if mode == "baseline" else 0.1,
                )
                self.store.record_run(run)

        summary = self.store.get_summary("t1")
        assert summary["task_id"] == "t1"
        assert summary["baseline_count"] == 3
        assert summary["stableagent_count"] == 3

    def test_persistence(self):
        """Verify data persists across store instances."""
        task = EffectivenessTask(task_id="persist-1", description="test")
        self.store.create_task(task)

        # New store instance
        store2 = ExperimentStore(data_dir=self.tmpdir)
        result = store2.get_task("persist-1")
        assert result is not None
        assert result["task_id"] == "persist-1"


# -- Metrics Tests --

class TestCalculateSummary:
    def test_empty_runs(self):
        result = calculate_summary([], "t1")
        assert result["verdict"] == "insufficient_data"

    def test_with_dict_runs(self):
        runs = []
        for mode in ["baseline", "stableagent"]:
            for i in range(3):
                runs.append({
                    "run_id": f"r_{mode}_{i}",
                    "task_id": "t1",
                    "mode": mode,
                    "success": mode == "stableagent",
                    "edits_made": 5 if mode == "baseline" else 8,
                    "files_changed": 3,
                    "tokens_used": 2000 if mode == "baseline" else 1000,
                    "intent_drift": 0.5 if mode == "baseline" else 0.1,
                })
        result = calculate_summary(runs, "t1")
        assert result["baseline_count"] == 3
        assert result["stableagent_count"] == 3


class TestFormatVerdict:
    def test_effective(self):
        assert format_verdict("effective") == "有效"

    def test_promising(self):
        assert format_verdict("promising") == "有潜力"

    def test_not_effective(self):
        assert format_verdict("not_effective") == "未见效"

    def test_insufficient_data(self):
        assert format_verdict("insufficient_data") == "数据不足"

    def test_unknown(self):
        assert format_verdict("unknown") == "unknown"


class TestFormatDelta:
    def test_zero(self):
        assert format_delta(0.0) == "≈ 持平"

    def test_positive_higher_better(self):
        # value > 0, higher is better → ↑
        assert "↑" in format_delta(0.5)

    def test_negative_higher_better(self):
        # value < 0, higher is better → ↓
        assert "↓" in format_delta(-0.5)

    def test_positive_lower_better(self):
        # value > 0, lower is better → positive means worse → ↑
        result = format_delta(0.5, lower_is_better=True)
        assert "↑" in result

    def test_negative_lower_better(self):
        # value < 0, lower is better → negative means better → ↓
        result = format_delta(-0.5, lower_is_better=True)
        assert "↓" in result
