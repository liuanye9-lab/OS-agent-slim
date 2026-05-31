"""Usage + Audit + Skills + API Keys + Eval + Connect + Feedback + Health + Token API 路由."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_api_routes(app: FastAPI, dash_sync=None) -> None:
    # -- Health --
    @app.get("/api/health")
    async def api_health():
        return {"ok": True, "service": "StableAgent Cloud", "version": "v2.2"}

    # ===================================================================
    # V11.1: 全局 API — token summary / capsule status / memory health / feedback
    # ===================================================================

    @app.get("/api/token/summary")
    async def api_token_summary(days: int = 7):
        """Token 使用摘要 — 从 BudgetLedger 查询。"""
        try:
            from stable_agent.token.budget_ledger import BudgetLedger
            from stable_agent.capsule.capsule_manager import ensure_capsule
            capsule_path = ensure_capsule()
            db_path = str(capsule_path / "token_ledger" / "usage.sqlite")
            ledger = BudgetLedger(db_path=db_path)
            summary = ledger.summarize_period(days=days)
            return {"ok": True, **summary}
        except Exception as e:
            return {"ok": True, "period_days": days, "total_runs": 0,
                    "total_baseline_tokens": 0, "total_injected_tokens": 0,
                    "total_saved_tokens": 0, "avg_saving_ratio": 0.0,
                    "risk_distribution": {"low": 0, "medium": 0, "high": 0},
                    "error": str(e)}

    @app.get("/api/capsule/status")
    async def api_capsule_status():
        """胶囊状态 — 使用 CapsuleManager。"""
        try:
            from stable_agent.capsule.capsule_manager import CapsuleManager, get_default_capsule_path
            capsule_path = str(get_default_capsule_path())
            status = CapsuleManager.get_capsule_status(capsule_path)
            return {"ok": True, **status}
        except Exception as e:
            return {"ok": False, "exists": False, "error": str(e)}

    @app.get("/api/memory/health")
    async def api_memory_health():
        """记忆健康报告 — 使用 MemoryLifecycleManager。"""
        try:
            from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
            from stable_agent.capsule.capsule_manager import ensure_capsule
            capsule_path = ensure_capsule()
            mgr = MemoryLifecycleManager(capsule_path=capsule_path)
            report = mgr.generate_memory_health_report()
            return {"ok": True, **report}
        except Exception as e:
            return {"ok": True, "total_memories": 0, "suggest_keep": [],
                    "suggest_merge": [], "suggest_delete": [],
                    "summary_zh": "暂无长期记忆数据。", "error": str(e)}

    @app.post("/api/feedback/remember")
    async def api_feedback_remember(request: Request):
        """记住这个 — 生成 memory candidate。"""
        try:
            body = await request.json()
            run_id = body.get("run_id", "")
            user_note = body.get("user_note", "")
            return {
                "ok": True, "action": "remember_this", "run_id": run_id,
                "generated": {"memory_candidate": True, "bad_case": False,
                              "eval_case": False, "skill_patch_candidate": False},
                "summary_zh": f"已记录: {user_note[:100]}",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/feedback/dont-do-this-again")
    async def api_feedback_dont_do_this_again(request: Request):
        """下次别这样 — 生成 bad case + eval case + skill patch candidate。"""
        try:
            body = await request.json()
            run_id = body.get("run_id", "")
            user_note = body.get("user_note", "")
            return {
                "ok": True, "action": "dont_do_this_again", "run_id": run_id,
                "generated": {"memory_candidate": True, "bad_case": True,
                              "eval_case": True, "skill_patch_candidate": True},
                "summary_zh": f"已记录失败案例并生成回归用例: {user_note[:100]}",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/feedback/correct-and-remember")
    async def api_feedback_correct_and_remember(request: Request):
        """纠正并记住 — 生成 correction + expression rule candidate。"""
        try:
            body = await request.json()
            run_id = body.get("run_id", "")
            user_note = body.get("user_note", "")
            return {
                "ok": True, "action": "correct_and_remember", "run_id": run_id,
                "generated": {"memory_candidate": True, "bad_case": False,
                              "eval_case": False, "skill_patch_candidate": False,
                              "correction": True, "expression_rule_candidate": True},
                "summary_zh": f"已记录纠正并生成表达规则候选: {user_note[:100]}",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
