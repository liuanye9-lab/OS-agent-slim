"""Review API 路由 — /api/reviews/*"""
from __future__ import annotations

from fastapi import FastAPI, Request


def register_review_routes(app: FastAPI) -> None:
    @app.get("/api/reviews")
    async def api_list_reviews(workspace_id: str = ""):
        try:
            from stable_agent.saas import SaasRepository
            repo = SaasRepository()
            reviews = []
            if workspace_id:
                try:
                    conn = repo._get_conn()
                    rows = conn.execute(
                        "SELECT * FROM human_reviews WHERE workspace_id=? AND status='pending' ORDER BY created_at DESC LIMIT 20",
                        (workspace_id,),
                    ).fetchall()
                    for r in rows:
                        reviews.append({
                            "id": r["id"], "workspace_id": r["workspace_id"],
                            "target_type": r["target_type"], "target_id": r["target_id"],
                            "reviewer": r["reviewer"] or "", "status": r["status"],
                            "comment": r["comment"] or "",
                        })
                except Exception:
                    import logging
                    logging.getLogger(__name__).debug("Review list DB query failed")
            return {"reviews": reviews}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/reviews/{review_id}")
    async def api_process_review(review_id: str, request: Request):
        body = await request.json()
        action = body.get("action", "approve")
        try:
            from stable_agent.saas import SaasRepository, SkillReviewService
            svc = SkillReviewService(repo=SaasRepository())
            if action == "approve":
                result = svc.approve_review(review_id, reviewer=body.get("reviewer", "admin"))
            else:
                result = svc.reject_review(review_id, reviewer=body.get("reviewer", "admin"))
            return {"review_id": review_id, "status": result.status, "action": action}
        except Exception as e:
            return {"error": str(e)}
