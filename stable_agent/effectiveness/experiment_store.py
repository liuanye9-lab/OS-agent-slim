"""JSONL-based persistent storage for Effectiveness experiments."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from .schemas import EffectivenessTask, EffectivenessRun, EffectivenessSummary
from stable_agent.capsule import ensure_capsule

logger = logging.getLogger(__name__)


class ExperimentStore:
    """JSONL-based storage for experiments, runs, and summaries."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        if data_dir is None:
            # Default to .stableagent-capsule/effectiveness/
            capsule_root = ensure_capsule()
            data_dir = str(capsule_root / "effectiveness")
        self._data_dir = Path(data_dir).resolve()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_file = self._data_dir / "effectiveness_tasks.jsonl"
        self._runs_file = self._data_dir / "effectiveness_runs.jsonl"
        self._lock_file = self._data_dir / "effectiveness.lock"
        logger.info("ExperimentStore: data_dir=%s", self._data_dir)

    # -- Task operations --

    def create_task(self, task: EffectivenessTask) -> dict:
        """Persist a task definition."""
        self._append_jsonl(self._tasks_file, task.to_dict())
        return task.to_dict()

    def get_task(self, task_id: str) -> Optional[dict]:
        """Retrieve a single task by ID."""
        for line in self._read_jsonl(self._tasks_file):
            if line.get("task_id") == task_id:
                return line
        return None

    def list_tasks(self) -> list[dict]:
        """Return all task definitions."""
        return list(self._read_jsonl(self._tasks_file))

    # -- Run operations --

    def record_run(self, run: EffectivenessRun) -> dict:
        """Persist a single A/B run result."""
        self._append_jsonl(self._runs_file, run.to_dict())
        return run.to_dict()

    def get_runs(self, task_id: Optional[str] = None) -> list[dict]:
        """Return all runs, optionally filtered by task_id."""
        runs = list(self._read_jsonl(self._runs_file))
        if task_id:
            runs = [r for r in runs if r.get("task_id") == task_id]
        return runs

    # -- Summary --

    def get_summary(self, task_id: str) -> dict:
        """Compute summary for a specific task."""
        runs = self.get_runs(task_id)
        baseline = [r for r in runs if r.get("mode") == "baseline"]
        stableagent = [r for r in runs if r.get("mode") == "stableagent"]

        summary = EffectivenessSummary(
            task_id=task_id,
            baseline_runs=baseline,
            stableagent_runs=stableagent,
        )
        summary.compute_deltas()
        return summary.to_dict()

    def get_all_summaries(self) -> list[dict]:
        """Compute summaries for all tasks."""
        tasks = self.list_tasks()
        result = []
        for t in tasks:
            tid = t.get("task_id")
            if tid:
                s = self.get_summary(tid)
                result.append(s)
        return result

    # V11.3.1: Find task by run_id and return summary
    def get_summary_by_run_id(self, run_id: str) -> Optional[dict]:
        """Look up which task a run_id belongs to, then return its summary."""
        for r in self._read_jsonl(self._runs_file):
            if r.get("run_id") == run_id:
                task_id = r.get("task_id")
                if task_id:
                    return self.get_summary(task_id)
        return None

    # -- Internal --

    def _append_jsonl(self, path: Path, record: dict) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSONL line in %s", path)
        return records
