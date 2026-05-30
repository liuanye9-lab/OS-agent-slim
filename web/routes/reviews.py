"""Review API 端点 — V7.1 Human Review 通道。

暴露人工审核队列的 REST API：
- GET  /api/reviews/pending → 待审核列表
- POST /api/reviews/{id}/approve → 审核通过
- POST /api/reviews/{id}/reject  → 审核拒绝
- GET  /api/reviews/{id} → 单个详情
"""

from __future__ import annotations

import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_review_routes(app, orchestrator) -> None:
    """注册 Review API 路由。

    依赖 orchestrator.proof_loop.review_queue。

    Args:
        app: FastAPI app 实例。
        orchestrator: StableAgentOrchestrator 实例。
    """

    def _get_queue():
        return orchestrator.proof_loop.review_queue if orchestrator else None

    @app.get("/api/reviews")
    async def list_reviews(workspace_id: str = ""):
        """向后兼容: 旧版 SaaS review 列表端点。"""
        queue = _get_queue()
        reviews = []
        if queue:
            for r in queue.list_all():
                reviews.append({
                    "id": r.review_id,
                    "workspace_id": workspace_id,
                    "target_type": "skill_patch",
                    "target_id": r.patch_id,
                    "reviewer": "",
                    "status": r.status,
                    "comment": r.resolution,
                })
        # 也尝试从 DB 查询（保留旧行为）
        if not reviews:
            try:
                from stable_agent.saas import SaasRepository
                repo = SaasRepository()
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
            except Exception:
                pass
        return JSONResponse({"reviews": reviews})

    @app.get("/api/reviews/pending")
    async def list_pending_reviews():
        """列出所有待审核的 Patch 请求。"""
        queue = _get_queue()
        pending = queue.list_pending()
        return JSONResponse({
            "count": len(pending),
            "reviews": [
                {
                    "review_id": r.review_id,
                    "patch_id": r.patch_id,
                    "run_id": r.run_id,
                    "failure_mode": r.failure_mode,
                    "risk_level": r.risk_level,
                    "expected_improvement": r.expected_improvement,
                    "status": r.status,
                    "created_at": r.created_at,
                    "new_rule_preview": r.new_rule[:100] + "..." if len(r.new_rule) > 100 else r.new_rule,
                }
                for r in pending
            ],
        })

    @app.get("/api/reviews/{review_id}")
    async def get_review_detail(review_id: str):
        """获取单个 Review 请求的完整详情。"""
        queue = _get_queue()
        req = queue.get(review_id)
        if req is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({
            "review_id": req.review_id,
            "patch_id": req.patch_id,
            "run_id": req.run_id,
            "failure_mode": req.failure_mode,
            "old_rule": req.old_rule,
            "new_rule": req.new_rule,
            "expected_improvement": req.expected_improvement,
            "risk_level": req.risk_level,
            "validation_report_id": req.validation_report_id,
            "status": req.status,
            "created_at": req.created_at,
            "notification": req.to_notification(),
        })

    @app.post("/api/reviews/{review_id}/approve")
    async def approve_review(review_id: str):
        """审核通过指定 Review 请求。

        触发连锁动作：
        1. ReviewQueue.approve()
        2. ProofLoop.approve_patch()
        3. best_skill.md 导出
        4. 飞书通知（如已配置）
        """
        queue = _get_queue()
        req = queue.get(review_id)
        if req is None:
            return JSONResponse({"error": "not found", "review_id": review_id}, status_code=404)

        # 审核队列
        queue.approve(review_id)

        # ProofLoop 审核 patch
        patch = orchestrator.proof_loop.approve_patch(req.patch_id, review_id)

        # 飞书通知（如果可用）
        notify_msg = ""
        try:
            if hasattr(orchestrator.proof_loop, '_notify_feishu'):
                notify_msg = orchestrator.proof_loop._notify_feishu(
                    req.patch_id, review_id, "approved",
                )
        except Exception as e:
            logger.warning("飞书通知失败: %s", e)

        return JSONResponse({
            "status": "approved",
            "review_id": review_id,
            "patch_id": req.patch_id,
            "best_skill_exported": patch is not None,
            "feishu_notified": bool(notify_msg),
        })

    @app.post("/api/reviews/{review_id}/reject")
    async def reject_review(review_id: str, request: Request):
        """审核拒绝指定 Review 请求。"""
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        reason = body.get("reason", "")

        queue = _get_queue()
        req = queue.get(review_id)
        if req is None:
            return JSONResponse({"error": "not found", "review_id": review_id}, status_code=404)

        queue.reject(review_id, reason)

        # ProofLoop 拒绝 patch
        orchestrator.proof_loop.reject_patch(req.patch_id, review_id, reason)

        return JSONResponse({
            "status": "rejected",
            "review_id": review_id,
            "reason": reason,
        })
