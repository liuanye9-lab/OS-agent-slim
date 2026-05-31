"""Effectiveness dashboard API routes."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_effectiveness_routes(app, store):
    """Register effectiveness dashboard routes on the FastAPI app."""
    router = APIRouter(prefix="/api/effectiveness", tags=["effectiveness"])

    @router.get("/summary")
    async def get_all_summaries(run_id: str | None = None):
        """Get summaries for all tasks, or a single summary by run_id."""
        try:
            if run_id:
                summary = store.get_summary_by_run_id(run_id)
                if summary:
                    return JSONResponse({"ok": True, "data": summary})
                return JSONResponse({"ok": False, "error": "No summary found for run_id"})
            summaries = store.get_all_summaries()
            return JSONResponse({"ok": True, "data": {"summaries": summaries, "total": len(summaries)}})
        except Exception as exc:
            logger.exception("Failed to get summaries")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @router.post("/task")
    async def create_task(body: dict):
        """Create a new effectiveness task."""
        from stable_agent.effectiveness.schemas import EffectivenessTask
        try:
            task_id = body.get("task_id", f"task_{int(time.time())}")
            description = body.get("description", "No description")
            category = body.get("category", "general")

            task = EffectivenessTask(
                task_id=task_id,
                description=description,
                category=category,
            )
            result = store.create_task(task)
            return JSONResponse({"ok": True, "data": result})
        except Exception as exc:
            logger.exception("Failed to create task")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @router.get("/tasks")
    async def list_tasks():
        """List all effectiveness tasks."""
        try:
            tasks = store.list_tasks()
            return JSONResponse({"ok": True, "data": {"tasks": tasks, "total": len(tasks)}})
        except Exception as exc:
            logger.exception("Failed to list tasks")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @router.post("/run")
    async def record_run(body: dict):
        """Record a single A/B run result."""
        from stable_agent.effectiveness.schemas import EffectivenessRun
        try:
            run = EffectivenessRun(
                run_id=body.get("run_id", f"run_{int(time.time())}"),
                task_id=body["task_id"],
                mode=body.get("mode", "baseline"),
                success=body.get("success", True),
                edits_made=body.get("edits_made", 0),
                files_changed=body.get("files_changed", 0),
                tokens_used=body.get("tokens_used", 0),
                intent_drift=body.get("intent_drift", 0.0),
                duration_sec=body.get("duration_sec", 0.0),
                error_message=body.get("error_message", ""),
                # V11.3 new fields
                model=body.get("model", ""),
                stableagent_run_id=body.get("stableagent_run_id", ""),
                test_passed=body.get("test_passed", True),
                over_editing=body.get("over_editing", False),
                rework_count=body.get("rework_count", 0),
                user_satisfaction=body.get("user_satisfaction", 3.0),
                constraint_preservation=body.get("constraint_preservation", 1.0),
            )
            result = store.record_run(run)
            return JSONResponse({"ok": True, "data": result})
        except KeyError as exc:
            return JSONResponse({"ok": False, "error": f"Missing required field: {exc}"}, status_code=400)
        except Exception as exc:
            logger.exception("Failed to record run")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @router.get("/runs")
    async def list_runs(task_id: str | None = None):
        """List all runs, optionally filtered by task_id."""
        try:
            runs = store.get_runs(task_id=task_id)
            return JSONResponse({"ok": True, "data": {"runs": runs, "total": len(runs)}})
        except Exception as exc:
            logger.exception("Failed to list runs")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @router.get("/task/{task_id}")
    async def get_task_detail(task_id: str):
        """Get detailed task info including runs and summary."""
        try:
            task = store.get_task(task_id)
            if not task:
                return JSONResponse({"ok": False, "error": f"Task not found: {task_id}"}, status_code=404)

            runs = store.get_runs(task_id=task_id)
            summary = store.get_summary(task_id)
            task["runs"] = runs
            task["summary"] = summary
            return JSONResponse({"ok": True, "data": task})
        except Exception as exc:
            logger.exception("Failed to get task detail")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    app.include_router(router)
