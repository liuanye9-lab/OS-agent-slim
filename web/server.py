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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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
    app: FastAPI = FastAPI(title="StableAgent OS", version="0.2.0")

    # ------------------------------------------------------------------
    # 3. 挂载 MCP Server（/mcp 前缀）
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
    app.mount("/mcp", mcp_server.app)

    # ------------------------------------------------------------------
    # 4. 挂载 Dashboard（/dashboard 前缀）
    # ------------------------------------------------------------------
    dashboard: Dashboard = Dashboard(event_bus, orchestrator=orchestrator)
    dashboard.mount_to(app, prefix="/dashboard")

    # ------------------------------------------------------------------
    # 5. V5: 挂载统一 MCP Gateway（/mcp/v5 前缀，避免与旧 /mcp 冲突）
    # ------------------------------------------------------------------
    try:
        from stable_agent.gateway.mcp_gateway import MCPGateway
        from stable_agent.observation.dashboard_sync import DashboardSync

        # 创建 Gateway
        gateway: MCPGateway = MCPGateway(orchestrator=orchestrator)
        v5_app = gateway.create_fastapi_app()
        app.mount("/mcp/v5", v5_app)

        # 创建 DashboardSync 并挂载（使用 gateway 的 event_stream）
        dash_sync: DashboardSync = DashboardSync(gateway.event_stream)
        sync_app = dash_sync.create_app()
        app.mount("/dashboard-sync", sync_app)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn").warning(f"V5 MCP Gateway mount skipped: {e}")

    # ------------------------------------------------------------------
    # 6. 配置静态文件和模板
    # ------------------------------------------------------------------
    web_dir: str = os.path.dirname(os.path.abspath(__file__))
    static_dir: str = os.path.join(web_dir, "static")
    templates_dir: str = os.path.join(web_dir, "templates")

    # 如果静态文件目录存在则挂载
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 读取 dashboard.html 模板文件
    dashboard_html_path: str = os.path.join(templates_dir, "dashboard.html")

    # ------------------------------------------------------------------
    # 7. 注册根路由
    # ------------------------------------------------------------------
    @app.get("/")
    async def root():
        """根路由 — 直接返回 Dashboard HTML。

        Dashboard.html 不使用 Jinja2 模板语法（无 {{ }} 或 {% %}），
        直接以静态 HTML 方式返回，避免 Jinja2 缓存兼容性问题。

        Returns:
            HTMLResponse 包含完整的 Dashboard 页面。
        """
        from fastapi.responses import HTMLResponse

        if os.path.exists(dashboard_html_path):
            with open(dashboard_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        return HTMLResponse(
            content="<h1>Dashboard not found</h1>", status_code=404
        )

    return app


# ============================================================================
# 模块级 app 实例（用于 uvicorn 启动）
# ============================================================================

app: FastAPI = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
