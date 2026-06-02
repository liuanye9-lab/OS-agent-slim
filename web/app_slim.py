"""StableAgent OS — Slim Cloud Edition 应用工厂。

轻量级 FastAPI 应用，不加载重型模块（saas/skill_optimizer/self_improvement）。
适用于 2 核 2G 云服务器。

Usage:
    STABLEAGENT_PROFILE=slim uvicorn web.server_slim:app --host 127.0.0.1 --port 18789
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

logger = logging.getLogger("uvicorn")


def create_slim_app() -> FastAPI:
    """创建 Slim Cloud Center 应用。"""
    from stable_agent.cloud.config import get_cloud_config
    config = get_cloud_config()
    logger.info("Creating Slim Cloud Center (profile=%s)", config.profile)

    app = FastAPI(
        title="StableAgent OS Slim Cloud Center",
        version="1.0.0",
        docs_url="/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 存储 config 到 app state
    app.state.config = config

    # ------------------------------------------------------------------
    # Static files
    # ------------------------------------------------------------------
    web_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(web_dir, "static")
    templates_dir = os.path.join(web_dir, "templates")

    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ------------------------------------------------------------------
    # Cloud API routes
    # ------------------------------------------------------------------
    from web.routes.cloud import register_cloud_routes
    register_cloud_routes(app)

    # ------------------------------------------------------------------
    # Slim MCP Gateway
    # ------------------------------------------------------------------
    from stable_agent.gateway.mcp_gateway import MCPGateway
    gateway = MCPGateway(orchestrator=None)
    app.mount("/mcp", gateway.create_fastapi_app())
    logger.info("MCP Gateway mounted at /mcp (slim mode, orchestrator=None)")

    # ------------------------------------------------------------------
    # Slim Dashboard page
    # ------------------------------------------------------------------
    slim_template = os.path.join(templates_dir, "slim_dashboard.html")

    @app.get("/slim")
    async def slim_dashboard():
        if os.path.exists(slim_template):
            with open(slim_template, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Slim Dashboard template not found</h1>", status_code=404)

    # ------------------------------------------------------------------
    # Root redirect
    # ------------------------------------------------------------------

    @app.get("/")
    async def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/slim")

    # ------------------------------------------------------------------
    # API Health
    # ------------------------------------------------------------------

    @app.get("/api/health")
    async def api_health():
        from stable_agent.cloud.control_center import ControlCenter
        cc = ControlCenter(config=config)
        h = cc.health()
        cc.close()
        return h

    # ------------------------------------------------------------------
    # Feedback API (minimal, no heavy dependencies)
    # ------------------------------------------------------------------

    @app.post("/api/feedback/remember")
    async def feedback_remember(request: Request):
        body = await request.json()
        try:
            from stable_agent.feedback.feedback_learning_service import FeedbackLearningService
            svc = FeedbackLearningService()
            return svc.handle_remember(
                run_id=body.get("run_id", ""),
                user_note=body.get("note", ""),
                context=body.get("context"),
            )
        except Exception as exc:
            logger.warning("Feedback remember failed: %s", exc)
            return {"ok": False, "error": str(exc), "summary_zh": "反馈服务不可用 (slim 模式可能缺少依赖)"}

    @app.post("/api/feedback/dont-do-this-again")
    async def feedback_dont(request: Request):
        body = await request.json()
        try:
            from stable_agent.feedback.feedback_learning_service import FeedbackLearningService
            svc = FeedbackLearningService()
            return svc.handle_dont_do_this_again(
                run_id=body.get("run_id", ""),
                user_note=body.get("note", ""),
                context=body.get("context"),
            )
        except Exception as exc:
            logger.warning("Feedback dont failed: %s", exc)
            return {"ok": False, "error": str(exc), "summary_zh": "反馈服务不可用 (slim 模式可能缺少依赖)"}

    @app.post("/api/feedback/correct-and-remember")
    async def feedback_correct(request: Request):
        body = await request.json()
        try:
            from stable_agent.feedback.feedback_learning_service import FeedbackLearningService
            svc = FeedbackLearningService()
            return svc.handle_correct_and_remember(
                run_id=body.get("run_id", ""),
                user_note=body.get("note", ""),
                context=body.get("context"),
            )
        except Exception as exc:
            logger.warning("Feedback correct failed: %s", exc)
            return {"ok": False, "error": str(exc), "summary_zh": "反馈服务不可用 (slim 模式可能缺少依赖)"}

    return app
