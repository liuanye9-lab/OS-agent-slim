"""web.routes.cloud — Slim Cloud Center API 路由。

提供 Worker 管理、任务管理、Dashboard 数据 API。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 延迟导入，避免 slim 模式加载重型模块
_control_center = None


def get_control_center():
    """获取全局 ControlCenter 单例。"""
    global _control_center
    if _control_center is None:
        from stable_agent.cloud.control_center import ControlCenter
        _control_center = ControlCenter()
    return _control_center


def register_cloud_routes(app: FastAPI) -> None:
    """注册所有 Cloud API 路由。"""

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/api/cloud/health")
    async def cloud_health():
        cc = get_control_center()
        return cc.health()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    @app.post("/api/workers/register")
    async def worker_register(request: Request):
        body = await request.json()
        cc = get_control_center()
        worker = cc.register_worker(
            worker_id=body.get("worker_id", ""),
            name=body.get("name", ""),
            machine_type=body.get("machine_type", "linux"),
            capabilities=body.get("capabilities", []),
        )
        return {"ok": True, "worker": worker.to_dict()}

    @app.get("/api/workers")
    async def worker_list():
        cc = get_control_center()
        workers = cc.list_workers()
        return {
            "ok": True,
            "workers": [w.to_dict() for w in workers],
            "count": len(workers),
        }

    @app.post("/api/workers/{worker_id}/heartbeat")
    async def worker_heartbeat(worker_id: str):
        cc = get_control_center()
        ok = cc.worker_heartbeat(worker_id)
        return {"ok": ok}

    @app.get("/api/workers/{worker_id}/next-task")
    async def worker_next_task(worker_id: str):
        cc = get_control_center()
        task = cc.get_next_task(worker_id)
        if task:
            return {"ok": True, "task": task.to_dict()}
        return {"ok": True, "task": None, "message": "no pending task"}

    @app.post("/api/workers/{worker_id}/task/{task_id}/started")
    async def task_started(worker_id: str, task_id: str):
        cc = get_control_center()
        ok = cc.task_started(worker_id, task_id)
        return {"ok": ok}

    @app.post("/api/workers/{worker_id}/task/{task_id}/log")
    async def task_log(worker_id: str, task_id: str, request: Request):
        body = await request.json()
        cc = get_control_center()
        ok = cc.task_log(worker_id, task_id, body.get("message", ""))
        return {"ok": ok}

    @app.post("/api/workers/{worker_id}/task/{task_id}/completed")
    async def task_completed(worker_id: str, task_id: str, request: Request):
        body = await request.json()
        cc = get_control_center()
        ok = cc.task_completed(worker_id, task_id, result=body.get("result", ""))
        return {"ok": ok}

    @app.post("/api/workers/{worker_id}/task/{task_id}/failed")
    async def task_failed(worker_id: str, task_id: str, request: Request):
        body = await request.json()
        cc = get_control_center()
        ok = cc.task_failed(worker_id, task_id, error=body.get("error", ""))
        return {"ok": ok}

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @app.post("/api/tasks")
    async def create_task(request: Request):
        body = await request.json()
        cc = get_control_center()
        task = cc.submit_task(
            task_input=body.get("task_input", ""),
            title=body.get("title", ""),
            priority=body.get("priority", 5),
            worker_id=body.get("worker_id"),
            source=body.get("source", "dashboard"),
        )
        return {"ok": True, "task": task.to_dict()}

    @app.get("/api/tasks")
    async def list_tasks(status: Optional[str] = None, limit: int = 50):
        cc = get_control_center()
        tasks = cc.list_tasks(status=status, limit=limit)
        return {
            "ok": True,
            "tasks": [t.to_dict() for t in tasks],
            "count": len(tasks),
        }

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        cc = get_control_center()
        task = cc.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"ok": True, "task": task.to_dict()}

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        cc = get_control_center()
        ok = cc.cancel_task(task_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Cannot cancel task")
        return {"ok": True}

    # ------------------------------------------------------------------
    # Runs / Events
    # ------------------------------------------------------------------

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str, limit: int = 100):
        cc = get_control_center()
        events = cc.get_events(run_id=run_id, limit=limit)
        return {"ok": True, "events": events, "count": len(events)}

    # ------------------------------------------------------------------
    # Dashboard data API
    # ------------------------------------------------------------------

    @app.get("/api/slim/status")
    async def slim_status():
        """Dashboard 聚合数据接口。"""
        cc = get_control_center()
        health = cc.health()
        workers = cc.list_workers()
        tasks = cc.list_tasks(limit=20)
        events = cc.get_events(limit=20)
        return {
            "ok": True,
            "health": health,
            "workers": [w.to_dict() for w in workers],
            "tasks": [t.to_dict() for t in tasks],
            "events": events,
        }

    @app.get("/api/slim/capsule")
    async def slim_capsule():
        """Agent Capsule 摘要。"""
        capsule_path = ".stableagent-capsule"
        summary = {
            "expression_rules_count": 0,
            "memory_count": 0,
            "bad_case_count": 0,
            "token_usage_summary": {},
        }
        try:
            import json
            expr_path = os.path.join(capsule_path, "profile", "expressions.json")
            if os.path.exists(expr_path):
                with open(expr_path) as f:
                    data = json.load(f)
                    summary["expression_rules_count"] = len(data.get("rules", []))

            mem_path = os.path.join(capsule_path, "memory")
            if os.path.isdir(mem_path):
                summary["memory_count"] = len(os.listdir(mem_path))

            bc_path = os.path.join(capsule_path, "bad_cases.jsonl")
            if os.path.exists(bc_path):
                with open(bc_path) as f:
                    summary["bad_case_count"] = sum(1 for _ in f)
        except Exception:
            pass

        return {"ok": True, "capsule": summary}
