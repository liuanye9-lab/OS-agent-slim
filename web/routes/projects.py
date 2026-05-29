"""Project API 路由 — /api/projects/*"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_project_routes(app: FastAPI) -> None:
    @app.post("/api/projects")
    async def api_create_project(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import ProjectService, BillingManager, SaasRepository
            repo = SaasRepository()
            svc = ProjectService(repo, BillingManager(repo))
            proj = svc.create_project(body["workspace_id"], body["name"],
                description=body.get("description", ""), environment=body.get("environment", "local"))
            return {"id": proj.id, "name": proj.name, "workspace_id": proj.workspace_id, "environment": proj.environment}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/projects")
    async def api_list_projects(workspace_id: str = ""):
        try:
            from stable_agent.saas import ProjectService, SaasRepository
            svc = ProjectService(SaasRepository())
            projects = svc.list_projects(workspace_id) if workspace_id else []
            return {"projects": [{"id": p.id, "name": p.name, "workspace_id": p.workspace_id} for p in projects]}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/projects/{project_id}")
    async def api_get_project(project_id: str):
        try:
            from stable_agent.saas import ProjectService, SaasRepository
            svc = ProjectService(SaasRepository())
            proj = svc.get_project(project_id)
            if proj is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {"id": proj.id, "name": proj.name, "workspace_id": proj.workspace_id, "environment": proj.environment}
        except Exception as e:
            return {"error": str(e)}
