"""Metrics calculation for Effectiveness A/B testing."""

from __future__ import annotations

from .schemas import EffectivenessSummary, EffectivenessRun


def calculate_summary(runs: list[dict | EffectivenessRun], task_id: str) -> dict:
    """Calculate A/B summary from a list of runs.

    Args:
        runs: List of run dicts or EffectivenessRun objects.
        task_id: Task identifier.

    Returns:
        Summary dict with delta metrics and verdict.
    """
    baseline = [r for r in runs if _get_mode(r) == "baseline"]
    stableagent = [r for r in runs if _get_mode(r) == "stableagent"]

    summary = EffectivenessSummary(
        task_id=task_id,
        baseline_runs=baseline,
        stableagent_runs=stableagent,
    )
    summary.compute_deltas()
    return summary.to_dict()


def _get_mode(run: dict | EffectivenessRun) -> str:
    if isinstance(run, dict):
        return run.get("mode", "baseline")
    return run.mode


def format_verdict(verdict: str) -> str:
    """Return a human-readable verdict label."""
    labels = {
        "insufficient_data": "数据不足",
        "promising": "有潜力",
        "effective": "有效",
        "not_effective": "未见效",
    }
    return labels.get(verdict, verdict)


def format_delta(value: float, lower_is_better: bool = False) -> str:
    """Format a delta value with direction indicator."""
    if abs(value) < 0.001:
        return "≈ 持平"
    if lower_is_better:
        direction = "↓" if value < 0 else "↑"
    else:
        direction = "↑" if value > 0 else "↓"
    return f"{direction} {abs(value):.2f}"
