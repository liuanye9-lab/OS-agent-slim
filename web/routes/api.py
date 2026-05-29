"""Usage + Audit + Skills + API Keys + Eval + Connect + Feedback + Health API 路由."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_api_routes(app: FastAPI, dash_sync=None) -> None:
    # -- Health --
    @app.get("/api/health")
    async def api_health():
        return {"ok": True, "service": "StableAgent Cloud", "version": "v2.2"}

    # -- Usage --
    @app.get("/api/usage")
    async def api_get_usage(project_id: str = "", workspace_id: str = ""):
        try:
            from stable_agent.saas import SaasRepository
            repo = SaasRepository()
            if project_id:
                summary = repo.get_project_usage_summary(project_id)
            elif workspace_id:
                projects = repo.list_projects(workspace_id)
                total_events = total_tokens = 0
                total_cost = 0.0
                for p in projects:
                    s = repo.get_project_usage_summary(p.id)
                    total_events += s.get("total_events", 0)
                    total_tokens += s.get("total_tokens", 0)
                    total_cost += s.get("total_cost", 0.0)
                summary = {"total_events": total_events, "total_tokens": total_tokens, "total_cost": round(total_cost, 6)}
            else:
                summary = {"total_events": 0, "total_tokens": 0, "total_cost": 0}
            return summary
        except Exception as e:
            return {"error": str(e)}

    # -- Audit --
    @app.get("/api/audit-logs")
    async def api_get_audit_logs(workspace_id: str = ""):
        try:
            from stable_agent.saas import AuditLogger, SaasRepository
            logger = AuditLogger(SaasRepository())
            logs = logger.list_recent(workspace_id) if workspace_id else []
            return {"logs": [{"id": l.id, "event_type": l.event_type, "actor": l.actor, "severity": l.severity} for l in logs]}
        except Exception as e:
            return {"error": str(e)}

    # -- Skills --
    @app.get("/api/skills")
    async def api_list_skills(workspace_id: str = ""):
        try:
            from stable_agent.saas import SaasRepository
            SaasRepository()  # noop stub
            return {"skills": []}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/skills/patches")
    async def api_list_patches(workspace_id: str = ""):
        try:
            return {"patches": []}
        except Exception as e:
            return {"error": str(e)}

    # -- API Keys --
    @app.post("/api/api-keys")
    async def api_create_api_key(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import ApiKeyManager, SaasRepository
            result = ApiKeyManager(SaasRepository()).create_key(body["workspace_id"], body["name"])
            return {"key_id": result["key_id"], "api_key": result["raw_key"], "prefix": "sk_"}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/api-keys")
    async def api_list_api_keys(workspace_id: str = ""):
        try:
            from stable_agent.saas import SaasRepository
            repo = SaasRepository()
            keys = repo.list_api_keys(workspace_id) if workspace_id else []
            return {"keys": [{"id": k.id, "name": k.name, "key_prefix": k.key_prefix,
                    "created_at": k.created_at, "revoked_at": k.revoked_at} for k in keys]}
        except Exception as e:
            return {"error": str(e)}

    @app.delete("/api/api-keys/{key_id}")
    async def api_revoke_api_key(key_id: str):
        try:
            from stable_agent.saas import ApiKeyManager, SaasRepository
            ok = ApiKeyManager(SaasRepository()).revoke_key(key_id)
            return {"key_id": key_id, "revoked": ok}
        except Exception as e:
            return {"error": str(e)}

    # -- Eval --
    @app.post("/api/evals/run")
    async def api_run_eval(request: Request):
        body = await request.json()
        return {"eval": "queued", "run_id": body.get("run_id", "")}

    # -- Feedback --
    @app.post("/api/feedback")
    async def handle_feedback(request: Request):
        body = await request.json()
        from stable_agent.observation.user_feedback_signal import UserFeedbackSignal
        import uuid
        fb = UserFeedbackSignal(
            feedback_id=str(uuid.uuid4()), run_id=body.get("run_id", ""),
            signal_type=body.get("signal_type", ""), comment=body.get("comment", ""),
        )
        if dash_sync:
            try:
                dash_sync.sync_feedback(fb.to_dict())
            except Exception:
                import logging
                logging.getLogger("uvicorn").warning("sync_feedback broadcast failed (non-critical)")
        from stable_agent.observation.learning_evidence import LearningEvidence
        evidence = LearningEvidence()
        if fb.signal_type in ("aligned",):
            le = evidence.explain_no_learning(fb.run_id)
        elif fb.signal_type in ("off_track", "not_specific", "no_executable_plan"):
            le = {"triggered": True, "reason_zh": f"用户反馈：{fb.label_zh}", "patches": [], "baseline_score": 0, "candidate_score": 0, "passed": False}
        else:
            le = evidence.explain_no_learning(fb.run_id)
        le["feedback_type"] = fb.signal_type
        le["feedback_label"] = fb.label_zh
        return JSONResponse({"ok": True, "feedback_id": fb.feedback_id, "learning_evidence": le})

    # -- Connect API --
    @app.get("/api/connect/health")
    async def connect_health():
        try:
            from stable_agent.quickstart import SetupDetector
            d = SetupDetector()
            result = d.health_check()
            try:
                from stable_agent.gateway.tool_schemas import TOOLS
                result["tools_count"] = len(TOOLS)
            except Exception:
                result["tools_count"] = 0
            return result
        except Exception as e:
            return {"ok": False, "server": "error", "error": str(e)}

    @app.get("/api/connect/config/{client}")
    async def connect_config(client: str):
        try:
            from stable_agent.quickstart import ConfigGenerator
            g = ConfigGenerator()
            if client == "claude":
                return g.claude_config()
            elif client == "codex":
                return g.codex_config()
            return g.generic_config()
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/connect/check_mcp")
    async def connect_check_mcp(request: Request):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/mcp",
                    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                )
                data = resp.json()
                return {"ok": True, "tools_count": len(data.get("result", {}).get("tools", []))}
        except Exception as e:
            return {"ok": False, "error": str(e)}
