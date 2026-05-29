"""StableAgent OS — 主 FastAPI 服务器入口。

本模块是 StableAgent OS 的 HTTP 服务入口，负责：
- 创建和配置 FastAPI 主应用
- 实例化所有核心模块（依赖注入）
- 挂载 MCP Server、Dashboard 子应用
- 配置静态文件和 Jinja2 模板
- 提供根路由渲染 Dashboard 页面

V3 升级：
- 使用 StableAgentOrchestrator 统一管理所有模块
- MCPServer 接收 mcp_tools 依赖
- Dashboard 接收 orchestrator 依赖

V5 升级：
- 挂载统一 MCP Gateway（/mcp/v5 前缀）
- 挂载 DashboardSync（per-run WebSocket 端点）

启动方式：
  python web/server.py
  uvicorn web.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from stable_agent.models import BadCase, Event, EvaluationResult, MemoryItem, TaskType
from stable_agent.context_decision_engine import ContextDecisionEngine
from stable_agent.context_budget_manager import ContextBudgetManager
from stable_agent.memory_router import MemoryBank, MemoryRouter
from stable_agent.eval_and_bad_case import BadCaseManager, Evaluator
from stable_agent.workflow_state_machine import WorkflowEngine
from stable_agent.trace_event_bus import EventBus
from stable_agent.mcp_server import MCPServer
from stable_agent.dashboard import Dashboard


def create_app() -> FastAPI:
    """创建完整的 StableAgent OS 应用。

    执行顺序：
    1. 实例化 EventBus（单例语义）
    2. 实例化所有核心模块
    3. 创建 WorkflowEngine 并注入所有依赖
    4. 创建 FastAPI 主应用
    5. 挂载 MCP Server（/mcp 前缀）
    6. 挂载 Dashboard（/dashboard 前缀）
    7. 配置静态文件和模板
    8. 注册根路由

    Returns:
        配置完成的 FastAPI 应用实例。
    """
    # ------------------------------------------------------------------
    # 1. 实例化核心模块
    # ------------------------------------------------------------------
    event_bus: EventBus = EventBus()
    decision_engine: ContextDecisionEngine = ContextDecisionEngine()
    budget_manager: ContextBudgetManager = ContextBudgetManager()
    memory_bank: MemoryBank = MemoryBank()
    memory_router: MemoryRouter = MemoryRouter(memory_bank)
    evaluator: Evaluator = Evaluator()
    bad_case_manager: BadCaseManager = BadCaseManager()
    workflow_engine: WorkflowEngine = WorkflowEngine(
        decision_engine=decision_engine,
        budget_manager=budget_manager,
        memory_router=memory_router,
        evaluator=evaluator,
        bad_case_manager=bad_case_manager,
        event_bus=event_bus,
    )

    # ------------------------------------------------------------------
    # V3: 尝试加载 orchestrator（用于 dashboard 的 run/bad_case/approval 查询）
    # ------------------------------------------------------------------
    orchestrator = None
    try:
        from stable_agent.orchestrator import StableAgentOrchestrator
        orchestrator = StableAgentOrchestrator()
    except Exception:
        pass

    # ------------------------------------------------------------------
    # V3: 构建 MCP 工具注册中心
    # ------------------------------------------------------------------
    mcp_tools = None
    try:
        from stable_agent.mcp_tools import MCPToolRegistry
        mcp_tools = MCPToolRegistry(orchestrator)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 2. 创建 FastAPI 主应用
    # ------------------------------------------------------------------
    app: FastAPI = FastAPI(title="StableAgent Cloud", version="1.5.0",
        docs_url="/docs", redoc_url="/redoc")

    # SaaS v1.6: CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # 3. Commercial SaaS: 统一 MCP 入口
    #    /mcp        → V5/V6 Gateway (生产主入口)
    #    /mcp/legacy → 旧 MCPServer (向后兼容)
    #    /mcp/v5     → V5 Gateway alias (deprecated, 重定向到 /mcp)
    # ------------------------------------------------------------------
    try:
        from stable_agent.gateway.mcp_gateway import MCPGateway
        from stable_agent.observation.dashboard_sync import DashboardSync

        # 创建 Gateway
        gateway: MCPGateway = MCPGateway(orchestrator=orchestrator)
        gateway_run_store = gateway.run_store
        v5_app = gateway.create_fastapi_app()

        # 生产主入口: /mcp
        app.mount("/mcp", v5_app)
        # Legacy alias: /mcp/v5 (保留向后兼容)
        # 注意: /mcp/v5 别名通过 connect API 自动指向 /mcp 即可

        # 创建 DashboardSync 并挂载（使用 gateway 的 event_stream）
        dash_sync: DashboardSync = DashboardSync(gateway.event_stream)
        sync_app = dash_sync.create_app()
        app.mount("/dashboard-sync", sync_app)
    except Exception as e:
        gateway_run_store = None
        import logging
        logging.getLogger("uvicorn").warning(f"V5 MCP Gateway mount skipped: {e}")

    # ------------------------------------------------------------------
    # 4. Legacy MCPServer（/mcp/legacy 前缀 — 向后兼容）
    # ------------------------------------------------------------------
    mcp_server: MCPServer = MCPServer(
        decision_engine=decision_engine,
        budget_manager=budget_manager,
        memory_router=memory_router,
        evaluator=evaluator,
        bad_case_manager=bad_case_manager,
        workflow_engine=workflow_engine,
        event_bus=event_bus,
        mcp_tools=mcp_tools,
    )
    app.mount("/mcp/legacy", mcp_server.app)

    # ------------------------------------------------------------------
    # 5. 配置静态文件和模板
    # ------------------------------------------------------------------
    web_dir: str = os.path.dirname(os.path.abspath(__file__))
    static_dir: str = os.path.join(web_dir, "static")
    templates_dir: str = os.path.join(web_dir, "templates")

    # SaaS v1.6: 自定义 404 页面
    _404_html: str = os.path.join(templates_dir, "404.html")

    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc):
        if os.path.exists(_404_html):
            with open(_404_html, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=404)
        return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)

    # 如果静态文件目录存在则挂载
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 读取模板文件
    dashboard_html_path: str = os.path.join(templates_dir, "dashboard.html")
    dashboard_v2_html_path: str = os.path.join(templates_dir, "dashboard_v2.html")

    # ------------------------------------------------------------------
    # 6. 注册路由（必须在 Dashboard mount 之前注册 /dashboard/v2，
    #    因为 mount 会遮蔽其前缀下的所有路由）
    # ------------------------------------------------------------------

    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get("/")
    async def root():
        """根路由 — 直接返回 Dashboard HTML。

        Dashboard.html 不使用 Jinja2 模板语法（无 {{ }} 或 {% %}），
        直接以静态 HTML 方式返回，避免 Jinja2 缓存兼容性问题。

        Returns:
            HTMLResponse 包含完整的 Dashboard 页面。
        """
        if os.path.exists(dashboard_html_path):
            with open(dashboard_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        return HTMLResponse(
            content="<h1>Dashboard not found</h1>", status_code=404
        )

    # ------------------------------------------------------------------
    # V5.5: Dashboard V2 路由（必须在 Dashboard mount 之前）
    # ------------------------------------------------------------------

    @app.get("/dashboard/v2")
    async def dashboard_v2():
        """Dashboard V2 — 决策观察舱 UI。

        Returns:
            HTMLResponse 包含完整的 Dashboard V2 页面。
        """
        if os.path.exists(dashboard_v2_html_path):
            with open(dashboard_v2_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        return HTMLResponse(
            content="<h1>Dashboard V2 not found</h1>", status_code=404
        )

    @app.get("/runs/{run_id}")
    async def run_page(run_id: str):
        """按 run_id 返回 Dashboard V3 页面 (V6.5)。"""
        dashboard_v3_html_path: str = os.path.join(templates_dir, "dashboard_v3.html")
        if os.path.exists(dashboard_v3_html_path):
            with open(dashboard_v3_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            html_content = html_content.replace(
                "<head>",
                f'<head>\n    <meta name="run-id" content="{run_id}">',
            )
            return HTMLResponse(content=html_content)
        # fallback to V2
        if os.path.exists(dashboard_v2_html_path):
            with open(dashboard_v2_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            html_content = html_content.replace(
                "<head>",
                f'<head>\n    <meta name="run-id" content="{run_id}">',
            )
            return HTMLResponse(content=html_content)
        return HTMLResponse(content="<h1>Run page not found</h1>", status_code=404)

    # V6.5: Dashboard V3 路由（必须在 Dashboard mount 之前）
    @app.get("/dashboard/v3")
    async def dashboard_v3():
        dashboard_v3_html_path: str = os.path.join(templates_dir, "dashboard_v3.html")
        if os.path.exists(dashboard_v3_html_path):
            with open(dashboard_v3_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Dashboard V3 not found</h1>", status_code=404)

    # SaaS: 所有 SaaS 页面路由（必须在 Dashboard mount 之前）
    _usage_h = os.path.join(templates_dir, "usage.html")
    _apikeys_h = os.path.join(templates_dir, "apikeys.html")
    _billing_h = os.path.join(templates_dir, "billing.html")
    _team_h = os.path.join(templates_dir, "team.html")
    _skills_h = os.path.join(templates_dir, "skills.html")
    _review_h = os.path.join(templates_dir, "review.html")

    @app.get("/dashboard/usage")
    async def saas_usage(): return _serve_html(_usage_h)
    @app.get("/dashboard/apikeys")
    async def saas_apikeys(): return _serve_html(_apikeys_h)
    @app.get("/dashboard/billing")
    async def saas_billing(): return _serve_html(_billing_h)
    @app.get("/dashboard/team")
    async def saas_team(): return _serve_html(_team_h)
    @app.get("/dashboard/skills")
    async def saas_skills(): return _serve_html(_skills_h)
    @app.get("/dashboard/review")
    async def saas_review(): return _serve_html(_review_h)

    def _serve_html(path: str):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Page not found</h1>", status_code=404)

    # ------------------------------------------------------------------
    # 7. 挂载 Dashboard（/dashboard 前缀）— 必须在 V2/V3 路由之后
    # ------------------------------------------------------------------
    dashboard: Dashboard = Dashboard(event_bus, orchestrator=orchestrator)
    dashboard.mount_to(app, prefix="/dashboard")

    # ------------------------------------------------------------------
    # 8. 反馈 API 端点 — 接收用户反馈并广播到 DashboardSync
    # ------------------------------------------------------------------

    @app.post("/api/feedback")
    async def handle_feedback(request: Request):
        """接收来自 Dashboard V2 的用户反馈。

        创建 UserFeedbackSignal 并通过 DashboardSync 的 EventStream
        广播给对应 run 的所有 WebSocket 连接，触发学习面板更新。

        Args:
            request: FastAPI Request，body 为 JSON。

        Returns:
            JSONResponse {"ok": True, "feedback_id": str}
        """
        body: dict = await request.json()

        # 创建 UserFeedbackSignal
        from stable_agent.observation.user_feedback_signal import UserFeedbackSignal
        import uuid

        fb: UserFeedbackSignal = UserFeedbackSignal(
            feedback_id=str(uuid.uuid4()),
            run_id=body.get("run_id", ""),
            signal_type=body.get("signal_type", ""),
            comment=body.get("comment", ""),
        )

        # 通过 DashboardSync 广播反馈事件到 WebSocket
        try:
            dash_sync.sync_feedback(fb.to_dict())
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(
                f"sync_feedback 广播失败 (非致命): {e}"
            )

        # 构建学习证据响应（供前端即时更新学习面板）
        from stable_agent.observation.learning_evidence import LearningEvidence
        evidence = LearningEvidence()

        # 根据反馈类型生成学习证据
        if fb.signal_type in ("aligned",):
            # 对齐的反馈 = 正面证据，不需要触发 learning
            learning_evidence = evidence.explain_no_learning(fb.run_id)
            learning_evidence["feedback_type"] = fb.signal_type
            learning_evidence["feedback_label"] = fb.label_zh
        elif fb.signal_type in ("off_track", "not_specific", "no_executable_plan"):
            # 负面反馈 = 需要触发学习的信号
            learning_evidence = {
                "triggered": True,
                "reason_zh": f"用户反馈：{fb.label_zh}。系统将分析差异并优化 skill 文档。",
                "reason_en": f"User feedback: {fb.label_en}. System will analyze gaps and optimize skill docs.",
                "feedback_type": fb.signal_type,
                "feedback_label": fb.label_zh,
                "patches": [],
                "baseline_score": 0.0,
                "candidate_score": 0.0,
                "passed": False,
            }
        else:
            # 中性反馈
            learning_evidence = evidence.explain_no_learning(fb.run_id)
            learning_evidence["feedback_type"] = fb.signal_type
            learning_evidence["feedback_label"] = fb.label_zh

        return JSONResponse({
            "ok": True,
            "feedback_id": fb.feedback_id,
            "learning_evidence": learning_evidence,
        })

    # ------------------------------------------------------------------
    # V6.5: /connect 一键接入页面
    # ------------------------------------------------------------------

    connect_html_path: str = os.path.join(templates_dir, "connect.html")
    login_html_path: str = os.path.join(templates_dir, "login.html")

    @app.get("/login")
    async def login_page():
        if os.path.exists(login_html_path):
            with open(login_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)

    @app.get("/connect")
    async def connect_page():
        """一键接入页面 — 展示 Claude Code / Codex / Cursor 接入方式。"""
        if os.path.exists(connect_html_path):
            with open(connect_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Connect page not found</h1>", status_code=404)

    # ------------------------------------------------------------------
    # SaaS: Skill/Review API（页面路由已在 Dashboard mount 之前注册）
    # ------------------------------------------------------------------

    # Skill API
    @app.get("/api/skills")
    async def api_list_skills(workspace_id: str = ""):
        """列出工作空间下的所有 Skills。"""
        try:
            from stable_agent.saas import SaasRepository
            repo = SaasRepository()
            projects = repo.list_projects(workspace_id) if workspace_id else []
            skills = []
            for p in projects:
                # 简化为直接从内存返回（实际应从 repo 查询）
                pass
            return {"skills": skills}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/skills/patches")
    async def api_list_patches(workspace_id: str = ""):
        """列出工作空间下的 Skill Patches。"""
        try:
            from stable_agent.saas import SaasRepository
            repo = SaasRepository()
            # 从 skill_patches 表查询（简化：返回所有 project 的 patches）
            return {"patches": []}
        except Exception as e:
            return {"error": str(e)}

    # Review API
    @app.get("/api/reviews")
    async def api_list_reviews(workspace_id: str = ""):
        """列出待审核的 Human Reviews。"""
        try:
            from stable_agent.saas import SaasRepository
            repo = SaasRepository()
            # 从 human_reviews 表查询 pending 记录
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
                    pass
            return {"reviews": reviews}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/reviews/{review_id}")
    async def api_process_review(review_id: str, request: Request):
        """处理审核（approve/reject）。"""
        body = await request.json()
        action = body.get("action", "approve")
        try:
            from stable_agent.saas import SaasRepository, SkillReviewService
            repo = SaasRepository()
            svc = SkillReviewService(repo=repo)
            if action == "approve":
                result = svc.approve_review(review_id, reviewer=body.get("reviewer", "admin"))
            else:
                result = svc.reject_review(review_id, reviewer=body.get("reviewer", "admin"))
            return {"review_id": review_id, "status": result.status, "action": action}
        except Exception as e:
            return {"error": str(e)}
    # ------------------------------------------------------------------
    # SaaS: Members API
    # ------------------------------------------------------------------
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
            svc = WorkspaceService(SaasRepository())
            import uuid
            member = svc.add_member(workspace_id, f"user_{uuid.uuid4().hex[:8]}",
                email=body.get("email", ""), role=body.get("role", "developer"))
            return {"member_id": member.id, "email": member.email, "role": member.role}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # SaaS v1.5: Auth API
    # ------------------------------------------------------------------

    @app.post("/api/auth/register")
    async def api_register(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            user = auth.register(body["email"], body["password"], body.get("name", ""))
            token = auth.login(body["email"], body["password"])
            return {"user_id": user.id, "email": user.email, "token": token}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/auth/login")
    async def api_login(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            token = auth.login(body["email"], body["password"])
            user = auth.get_current_user(token)
            return {"token": token, "email": user.email if user else body["email"]}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

    @app.get("/api/auth/me")
    async def api_me(request: Request):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return JSONResponse({"error": "未提供 token"}, status_code=401)
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            user = auth.get_current_user(token)
            if user is None:
                return JSONResponse({"error": "token 无效或已过期"}, status_code=401)
            return {"user_id": user.id, "email": user.email, "name": user.name}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # V6.5: /api/connect/* 接入配置 API
    # ------------------------------------------------------------------

    @app.get("/api/connect/health")
    async def connect_health():
        """健康检查 — 返回服务状态和接入信息。"""
        try:
            from stable_agent.quickstart import SetupDetector
            d = SetupDetector()
            result = d.health_check()
            # 补充工具数量
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
        """返回指定客户端的 MCP 配置。"""
        try:
            from stable_agent.quickstart import ConfigGenerator
            g = ConfigGenerator()
            if client == "claude":
                return g.claude_config()
            elif client == "codex":
                return g.codex_config()
            else:
                return g.generic_config()
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/connect/check_mcp")
    async def connect_check_mcp(request: Request):
        """检查 MCP 端点是否可用。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/mcp",
                    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                )
                data = resp.json()
                tools = data.get("result", {}).get("tools", [])
                return {"ok": True, "tools_count": len(tools)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # V6.5: /api/runs/{run_id}/* 运行数据 API
    # ------------------------------------------------------------------

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str):
        """获取指定 run_id 的所有历史事件（支持 Dashboard 刷新后回放）。"""
        try:
            store = gateway_run_store
            if store is None:
                return []
            events = store.get_events(run_id)
            import dataclasses
            result = []
            for e in events:
                if dataclasses.is_dataclass(e):
                    result.append(dataclasses.asdict(e))
                elif isinstance(e, dict):
                    result.append(e)
                else:
                    result.append({"raw": str(e)})
            return result
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"get_run_events failed: {e}")
            return []

    @app.get("/api/runs/{run_id}/summary")
    async def get_run_summary(run_id: str):
        """获取指定 run_id 的任务总结。"""
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
        """提交用户对特定 run 的反馈。"""
        try:
            body = await request.json()
            from stable_agent.observation.user_feedback_signal import UserFeedbackSignal
            import uuid
            fb = UserFeedbackSignal(
                feedback_id=str(uuid.uuid4()),
                run_id=run_id,
                signal_type=body.get("label", body.get("signal_type", "")),
                comment=body.get("comment", ""),
            )
            try:
                dash_sync.sync_feedback(fb.to_dict())
            except Exception:
                pass
            return {"ok": True, "feedback_id": fb.feedback_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ===================================================================
    # SaaS v1.2: 商业 API 路由
    # ===================================================================

    @app.get("/api/health")
    async def api_health():
        """健康检查。"""
        return {"ok": True, "service": "StableAgent Cloud", "version": "v1.2"}

    # -- Workspace --

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
            repo = SaasRepository()
            svc = WorkspaceService(repo)
            ws_list = svc.list_workspaces()
            return {"workspaces": [{"id": w.id, "name": w.name, "tier": w.billing_plan} for w in ws_list]}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/workspaces/{workspace_id}")
    async def api_get_workspace(workspace_id: str):
        try:
            from stable_agent.saas import WorkspaceService, SaasRepository
            svc = WorkspaceService(SaasRepository())
            ws = svc.get_workspace(workspace_id)
            if ws is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {"id": ws.id, "name": ws.name, "slug": ws.slug, "tier": ws.billing_plan}
        except Exception as e:
            return {"error": str(e)}

    # -- Project --

    @app.post("/api/projects")
    async def api_create_project(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import ProjectService, BillingManager, SaasRepository
            repo = SaasRepository()
            svc = ProjectService(repo, BillingManager(repo))
            proj = svc.create_project(body["workspace_id"], body["name"],
                description=body.get("description", ""),
                environment=body.get("environment", "local"))
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

    # -- Run --

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
        """SaaS v1.3: 获取 Run 完整详情（包含 eval + trace 摘要）。"""
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.get_run(run_id)
            if run is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            # 收集 eval 数据
            eval_data = {}
            try:
                repo = SaasRepository()
                # 检查有无 eval_result
                eval_data = {"note": "eval not yet available"}
            except Exception:
                pass
            return {
                "run_id": run.run_id,
                "status": run.status,
                "progress_pct": run.progress_pct,
                "overall_score": run.overall_score,
                "intent_alignment_score": run.intent_alignment_score,
                "token_used": run.token_used,
                "cost_estimate": run.cost_estimate,
                "learning_triggered": run.learning_triggered,
                "skill_updated": run.skill_updated,
                "dashboard_url": run.dashboard_url,
                "trace_url": run.trace_url,
                "user_task": run.user_task,
                "started_at": run.started_at,
                "ended_at": run.ended_at,
                "workspace_id": run.workspace_id,
                "project_id": run.project_id,
                "agent_id": run.agent_id,
                "eval": eval_data,
            }
        except Exception as e:
            return {"error": str(e)}

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
                total_events = 0; total_tokens = 0; total_cost = 0.0
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

    # -- Audit Log --

    @app.get("/api/audit-logs")
    async def api_get_audit_logs(workspace_id: str = ""):
        try:
            from stable_agent.saas import AuditLogger, SaasRepository
            logger = AuditLogger(SaasRepository())
            logs = logger.list_recent(workspace_id) if workspace_id else []
            return {"logs": [{"id": l.id, "event_type": l.event_type, "actor": l.actor, "severity": l.severity} for l in logs]}
        except Exception as e:
            return {"error": str(e)}

    # -- API Keys --

    @app.post("/api/api-keys")
    async def api_create_api_key(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import ApiKeyManager, SaasRepository
            mgr = ApiKeyManager(SaasRepository())
            result = mgr.create_key(body["workspace_id"], body["name"])
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
            mgr = ApiKeyManager(SaasRepository())
            ok = mgr.revoke_key(key_id)
            return {"key_id": key_id, "revoked": ok}
        except Exception as e:
            return {"error": str(e)}

    # -- Eval --

    @app.post("/api/evals/run")
    async def api_run_eval(request: Request):
        body = await request.json()
        return {"eval": "queued", "run_id": body.get("run_id", "")}

    return app


# ============================================================================
# 模块级 app 实例（用于 uvicorn 启动）
# ============================================================================

app: FastAPI = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
