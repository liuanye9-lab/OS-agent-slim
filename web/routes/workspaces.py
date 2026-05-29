"""Workspace API 路由 — /api/workspaces/*"""
from __future__ import annotations

from fastapi import FastAPI, Request


def register_workspace_routes(app: FastAPI) -> None:
    @app.post("/api/workspaces")
    async def api_create_workspace(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import WorkspaceService, BillingManager, SaasRepository
            repo = SaasRepository()
            repo.init_db()
            svc = WorkspaceService(repo, BillingManager(repo))
            ws = svc.create_workspace(body.get("name", ""), tier=body.get("tier", "free"))
            return {"id": ws.id, "name": ws.name, "tier": ws.billing_plan}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/workspaces")
    async def api_list_workspaces():
        try:
            from stable_agent.saas import WorkspaceService, SaasRepository
            svc = WorkspaceService(SaasRepository())
            ws_list = svc.list_workspaces()
            return {"workspaces": [{"id": w.id, "name": w.name, "tier": w.billing_plan} for w in ws_list]}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/workspaces/{workspace_id}")
    async def api_get_workspace(workspace_id: str):
        try:
            from stable_agent.saas import WorkspaceService, SaasRepository
            from fastapi.responses import JSONResponse
            svc = WorkspaceService(SaasRepository())
            ws = svc.get_workspace(workspace_id)
            if ws is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {"id": ws.id, "name": ws.name, "slug": ws.slug, "tier": ws.billing_plan}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/workspaces/{workspace_id}/members")
    async def api_workspace_members(workspace_id: str):
        try:
            from stable_agent.saas import WorkspaceService, SaasRepository
            svc = WorkspaceService(SaasRepository())
            members = svc.list_members(workspace_id)
            return {"members": [{"id": m.id, "user_id": m.user_id, "email": m.email, "role": m.role} for m in members]}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/workspaces/{workspace_id}/members")
    async def api_invite_member(workspace_id: str, request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import WorkspaceService, SaasRepository
            import uuid
            svc = WorkspaceService(SaasRepository())
            member = svc.add_member(workspace_id, f"user_{uuid.uuid4().hex[:8]}",
                email=body.get("email", ""), role=body.get("role", "developer"))
            return {"member_id": member.id, "email": member.email, "role": member.role}
        except Exception as e:
            return {"error": str(e)}
