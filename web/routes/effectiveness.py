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
    async def get_all_summaries():
        """Get summaries for all tasks."""
        try:
            summaries = store.get_all_summaries()
            return JSONResponse({"summaries": summaries, "total": len(summaries)})
        except Exception as exc:
            logger.exception("Failed to get summaries")
            raise HTTPException(status_code=500, detail=str(exc))

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
            return JSONResponse(result)
        except Exception as exc:
            logger.exception("Failed to create task")
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/tasks")
    async def list_tasks():
        """List all effectiveness tasks."""
        try:
            tasks = store.list_tasks()
            return JSONResponse({"tasks": tasks, "total": len(tasks)})
        except Exception as exc:
            logger.exception("Failed to list tasks")
            raise HTTPException(status_code=500, detail=str(exc))

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
            )
            result = store.record_run(run)
            return JSONResponse(result)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing required field: {exc}")
        except Exception as exc:
            logger.exception("Failed to record run")
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/runs")
    async def list_runs(task_id: str | None = None):
        """List all runs, optionally filtered by task_id."""
        try:
            runs = store.get_runs(task_id=task_id)
            return JSONResponse({"runs": runs, "total": len(runs)})
        except Exception as exc:
            logger.exception("Failed to list runs")
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/task/{task_id}")
    async def get_task_detail(task_id: str):
        """Get detailed task info including runs and summary."""
        try:
            task = store.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

            runs = store.get_runs(task_id=task_id)
            summary = store.get_summary(task_id)
            task["runs"] = runs
            task["summary"] = summary
            return JSONResponse(task)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to get task detail")
            raise HTTPException(status_code=500, detail=str(exc))

    app.include_router(router)
