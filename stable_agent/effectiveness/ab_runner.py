"""A/B test runner for Effectiveness experiments."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from .schemas import EffectivenessRun
from .experiment_store import ExperimentStore

logger = logging.getLogger(__name__)


class ABRunner:
    """Runs A/B comparisons for tasks."""

    def __init__(self, store: Optional[ExperimentStore] = None) -> None:
        self._store = store or ExperimentStore()

    def run_comparison(
        self,
        task_id: str,
        baseline_fn: Callable,
        stableagent_fn: Callable,
        *args,
        **kwargs,
    ) -> dict:
        """Run both baseline and stableagent modes for a task.

        Args:
            task_id: Task identifier.
            baseline_fn: Callable for baseline mode execution.
            stableagent_fn: Callable for stableagent mode execution.
            *args: Positional arguments passed to both functions.
            **kwargs: Keyword arguments passed to both functions.

        Returns:
            Summary dict with comparison metrics.
        """
        results = []

        # Run baseline
        baseline_run = self._execute(
            task_id, "baseline", baseline_fn, *args, **kwargs
        )
        results.append(baseline_run)
        self._store.record_run(baseline_run)
        logger.info("Baseline run recorded: %s", baseline_run.run_id)

        # Run stableagent
        stableagent_run = self._execute(
            task_id, "stableagent", stableagent_fn, *args, **kwargs
        )
        results.append(stableagent_run)
        self._store.record_run(stableagent_run)
        logger.info("StableAgent run recorded: %s", stableagent_run.run_id)

        # Compute summary
        return self._store.get_summary(task_id)

    def _execute(
        self,
        task_id: str,
        mode: str,
        fn: Callable,
        *args,
        **kwargs,
    ) -> EffectivenessRun:
        """Execute a single run and capture metrics."""
        run_id = f"{task_id}_{mode}_{int(time.time())}"
        start = time.time()

        try:
            result = fn(*args, **kwargs)
            duration = time.time() - start
            return EffectivenessRun(
                run_id=run_id,
                task_id=task_id,
                mode=mode,
                success=True,
                edits_made=_count_edits(result),
                files_changed=_count_files(result),
                tokens_used=_estimate_tokens(result),
                intent_drift=0.0,
                duration_sec=duration,
            )
        except Exception as exc:
            duration = time.time() - start
            return EffectivenessRun(
                run_id=run_id,
                task_id=task_id,
                mode=mode,
                success=False,
                error_message=str(exc),
                duration_sec=duration,
            )


def _count_edits(result) -> int:
    """Estimate number of edits from a result."""
    if isinstance(result, dict):
        return result.get("edits_made", 0)
    return 0


def _count_files(result) -> int:
    """Estimate number of files changed from a result."""
    if isinstance(result, dict):
        return result.get("files_changed", 0)
    return 0


def _estimate_tokens(result) -> int:
    """Estimate tokens used from a result."""
    if isinstance(result, dict):
        return result.get("tokens_used", 0)
    return 0
