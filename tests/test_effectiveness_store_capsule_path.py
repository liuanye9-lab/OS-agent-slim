"""Tests for ExperimentStore capsule path default behavior."""

import pathlib
import tempfile
import pytest
from stable_agent.effectiveness.experiment_store import ExperimentStore
from stable_agent.effectiveness.schemas import EffectivenessTask, EffectivenessRun
from stable_agent.capsule import ensure_capsule


class TestExperimentStoreCapsulePath:
    """Verify ExperimentStore defaults to capsule effectiveness directory."""

    def test_default_path_is_capsule_effectiveness(self):
        """When no data_dir provided, store should use .stableagent-capsule/effectiveness/."""
        store = ExperimentStore()
        capsule_root = ensure_capsule()
        expected = (capsule_root / "effectiveness").resolve()
        assert store._data_dir == expected

    def test_custom_path_overrides_default(self):
        """When data_dir is provided, store should use it instead of capsule."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            assert store._data_dir == pathlib.Path(tmp).resolve()

    def test_data_dir_created_on_init(self):
        """Store should create its data directory on initialization."""
        with tempfile.TemporaryDirectory() as tmp:
            custom_dir = pathlib.Path(tmp) / "sub" / "effectiveness"
            assert not custom_dir.exists()
            store = ExperimentStore(data_dir=str(custom_dir))
            assert custom_dir.exists()
            assert custom_dir.is_dir()

    def test_record_and_read_run(self):
        """Store should persist and retrieve runs via JSONL."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            run = EffectivenessRun(
                run_id="r1", task_id="t1", mode="stableagent",
                success=True, edits_made=5, tokens_used=1000,
            )
            result = store.record_run(run)
            assert result["run_id"] == "r1"

            runs = store.get_runs()
            assert len(runs) == 1
            assert runs[0]["run_id"] == "r1"

    def test_record_and_read_task(self):
        """Store should persist and retrieve tasks via JSONL."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            task = EffectivenessTask(task_id="t1", description="Test task")
            result = store.create_task(task)
            assert result["task_id"] == "t1"

            tasks = store.list_tasks()
            assert len(tasks) == 1
            assert tasks[0]["task_id"] == "t1"

    def test_get_runs_filtered_by_task_id(self):
        """get_runs should filter by task_id."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            store.record_run(EffectivenessRun(run_id="r1", task_id="t1", mode="baseline"))
            store.record_run(EffectivenessRun(run_id="r2", task_id="t1", mode="stableagent"))
            store.record_run(EffectivenessRun(run_id="r3", task_id="t2", mode="baseline"))

            t1_runs = store.get_runs(task_id="t1")
            assert len(t1_runs) == 2
            assert all(r["task_id"] == "t1" for r in t1_runs)

            t2_runs = store.get_runs(task_id="t2")
            assert len(t2_runs) == 1

    def test_summary_computation(self):
        """get_summary should compute deltas correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            store.create_task(EffectivenessTask(task_id="t1", description="Test"))
            for i in range(2):
                store.record_run(EffectivenessRun(
                    run_id=f"b{i}", task_id="t1", mode="baseline",
                    success=False, tokens_used=2000, intent_drift=0.3,
                    edits_made=5, files_changed=4,
                ))
            for i in range(2):
                store.record_run(EffectivenessRun(
                    run_id=f"s{i}", task_id="t1", mode="stableagent",
                    success=True, tokens_used=800, intent_drift=0.05,
                    edits_made=5, files_changed=2,
                ))

            summary = store.get_summary("t1")
            assert summary["task_id"] == "t1"
            assert summary["baseline_count"] == 2
            assert summary["stableagent_count"] == 2
            assert summary["delta_success"] > 0
            assert summary["verdict"] in ("effective", "promising", "not_effective", "insufficient_data")

    def test_empty_store_returns_empty_lists(self):
        """Empty store should return empty lists, not raise errors."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            assert store.list_tasks() == []
            assert store.get_runs() == []
            assert store.get_all_summaries() == []

    def test_summary_for_nonexistent_task(self):
        """get_summary for a task with no runs should return zero counts."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            summary = store.get_summary("nonexistent")
            assert summary["baseline_count"] == 0
            assert summary["stableagent_count"] == 0
            assert summary["verdict"] == "insufficient_data"

    def test_v113_fields_persisted(self):
        """V11.3 new fields should be persisted and retrievable."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            run = EffectivenessRun(
                run_id="r1", task_id="t1", mode="stableagent",
                model="qwen-plus", stableagent_run_id="sa-001",
                test_passed=True, over_editing=False,
                rework_count=2, user_satisfaction=4.5,
                constraint_preservation=0.95,
            )
            store.record_run(run)
            runs = store.get_runs()
            assert len(runs) == 1
            assert runs[0]["model"] == "qwen-plus"
            assert runs[0]["stableagent_run_id"] == "sa-001"
            assert runs[0]["test_passed"] is True
            assert runs[0]["over_editing"] is False
            assert runs[0]["rework_count"] == 2
            assert runs[0]["user_satisfaction"] == 4.5
            assert runs[0]["constraint_preservation"] == 0.95

    def test_get_summary_by_run_id(self):
        """get_summary_by_run_id should find the task and return summary."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            task = EffectivenessTask(task_id="t1", description="test")
            store.create_task(task)
            baseline = EffectivenessRun(run_id="b1", task_id="t1", mode="baseline",
                                       success=False, edits_made=5, tokens_used=2000,
                                       intent_drift=0.5, constraint_preservation=0.6)
            stableagent = EffectivenessRun(run_id="s1", task_id="t1", mode="stableagent",
                                          success=True, edits_made=8, tokens_used=1000,
                                          intent_drift=0.1, constraint_preservation=0.95)
            store.record_run(baseline)
            store.record_run(stableagent)

            summary = store.get_summary_by_run_id("s1")
            assert summary is not None
            assert summary["task_id"] == "t1"
            assert summary["baseline_count"] == 1
            assert summary["stableagent_count"] == 1

    def test_get_summary_by_run_id_not_found(self):
        """get_summary_by_run_id should return None for unknown run_id."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            assert store.get_summary_by_run_id("nonexistent") is None

    def test_get_summary_by_run_id_no_tasks(self):
        """get_summary_by_run_id should return None when no tasks exist."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(data_dir=tmp)
            assert store.get_summary_by_run_id("any_id") is None
