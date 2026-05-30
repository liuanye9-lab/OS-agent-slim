"""Run API 路由 — /api/runs/*"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_run_routes(app: FastAPI, gateway_run_store=None, dash_sync=None) -> None:
    @app.post("/api/runs")
    async def api_create_run(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.create_run(body.get("workspace_id", ""), body.get("project_id", ""),
                agent_id=body.get("agent_id", ""), user_task=body.get("user_task", ""))
            return {"run_id": run.run_id, "status": run.status, "dashboard_url": run.dashboard_url}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/runs/{run_id}")
    async def api_get_run(run_id: str):
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.get_run(run_id)
            if run is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {"run_id": run.run_id, "status": run.status, "progress_pct": run.progress_pct,
                    "overall_score": run.overall_score, "token_used": run.token_used,
                    "dashboard_url": run.dashboard_url, "user_task": run.user_task}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/runs/{run_id}/detail")
    async def api_get_run_detail(run_id: str):
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.get_run(run_id)
            if run is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {
                "run_id": run.run_id, "status": run.status,
                "progress_pct": run.progress_pct, "overall_score": run.overall_score,
                "intent_alignment_score": run.intent_alignment_score,
                "token_used": run.token_used, "cost_estimate": run.cost_estimate,
                "dashboard_url": run.dashboard_url, "trace_url": run.trace_url,
                "user_task": run.user_task, "started_at": run.started_at,
                "ended_at": run.ended_at, "workspace_id": run.workspace_id,
                "project_id": run.project_id, "agent_id": run.agent_id,
            }
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str):
        try:
            store = gateway_run_store
            if store is None:
                return JSONResponse(
                    {"error": "gateway_run_store unavailable", "run_id": run_id},
                    status_code=503,
                )
            import dataclasses
            events = store.get_events(run_id)
            # V9.2: run_id 不存在于 RunStore → 返回 404
            run_status = store.get_run_status(run_id)
            if run_status is None:
                return JSONResponse(
                    {"error": "run not found", "run_id": run_id},
                    status_code=404,
                )
            result = []
            for e in events:
                if dataclasses.is_dataclass(e):
                    result.append(dataclasses.asdict(e))
                elif isinstance(e, dict):
                    result.append(e)
                else:
                    result.append({"raw": str(e)})
            # V10: 结构化返回，含 event_count
            return {
                "run_id": run_id,
                "event_count": len(result),
                "events": result,
            }
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").exception("get_run_events failed: %s", e)
            return JSONResponse(
                {"error": str(e), "run_id": run_id},
                status_code=500,
            )

    @app.get("/api/runs/{run_id}/summary")
    async def get_run_summary(run_id: str):
        try:
            store = gateway_run_store
            if store is None:
                return {"run_id": run_id, "error": "gateway run store unavailable"}
            return store.get_run_summary(run_id)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"get_run_summary failed: {e}")
            return {"run_id": run_id, "error": str(e)}

    @app.post("/api/runs/{run_id}/feedback")
    async def submit_run_feedback(run_id: str, request: Request):
        try:
            body = await request.json()
            from stable_agent.observation.user_feedback_signal import UserFeedbackSignal
            import uuid
            fb = UserFeedbackSignal(
                feedback_id=str(uuid.uuid4()), run_id=run_id,
                signal_type=body.get("label", body.get("signal_type", "")),
                comment=body.get("comment", ""),
            )
            if dash_sync:
                try:
                    dash_sync.sync_feedback(fb.to_dict())
                except Exception:
                    pass
            return {"ok": True, "feedback_id": fb.feedback_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}
