"""Approval API 路由 — /api/approvals/*"""
from __future__ import annotations

from fastapi import FastAPI, Request


def register_approval_routes(app: FastAPI) -> None:
    @app.get("/api/approvals/pending")
    async def api_approval_pending(workspace_id: str = "", run_id: str = ""):
        try:
            from stable_agent.approval.pending_tool_store import PendingToolStore
            store = PendingToolStore()
            if run_id:
                calls = store.list_by_run(run_id)
            else:
                calls = store.list_all()
            return {"pending": [
                {"approval_id": c.approval_id, "run_id": c.run_id,
                 "tool_name": c.tool_name, "created_at": c.created_at,
                 "status": c.status, "workspace_id": c.workspace_id}
                for c in calls
            ]}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/approvals/{approval_id}/approve")
    async def api_approval_approve(approval_id: str):
        try:
            from stable_agent.approval import ApprovalResumeService
            svc = ApprovalResumeService()
            return svc.approve_and_resume(approval_id)
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/approvals/{approval_id}/reject")
    async def api_approval_reject(approval_id: str, request: Request = None):
        body = await request.json() if request else {}
        try:
            from stable_agent.approval import ApprovalResumeService
            svc = ApprovalResumeService()
            return svc.reject(approval_id, reason=body.get("reason", ""))
        except Exception as e:
            return {"error": str(e)}
