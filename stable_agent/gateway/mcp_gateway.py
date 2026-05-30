"""MCPGateway — V5 统一 MCP Gateway 入口。

封装所有 V5 组件（UnifiedToolRegistry、ToolRouter、ResponseAdapter、
JSONRPCHandler、RunStore、EventStream），提供 FastAPI 路由注册。

通过 create_fastapi_app() 创建包含 /mcp 端点的 FastAPI app：
- POST /mcp: JSON-RPC 2.0 端点（initialize/tools/list/tools/call）
- GET /mcp: SSE 事件流端点（按 run_id 筛选）

用法::

    gateway = MCPGateway(orchestrator)
    app = gateway.create_fastapi_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

from __future__ import annotations

import asyncio
import json
import dataclasses
from typing import Any, TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.gateway.tool_router import ToolRouter
from stable_agent.gateway.response_adapter import ResponseAdapter
from stable_agent.gateway.jsonrpc_handler import JSONRPCHandler
from stable_agent.observation.run_store import RunStore
from stable_agent.observation.event_stream import EventStream


class MCPGateway:
    """V5 统一 MCP Gateway 入口。

    封装所有 V5 组件，提供 FastAPI 路由注册。自动从 orchestrator
    获取 security_policy、approval_manager、event_bus。
    自动创建 RunStore 和 EventStream。

    Attributes:
        run_store: RunStore 实例。
        event_stream: EventStream 实例。
        registry: UnifiedToolRegistry 实例。
        router: ToolRouter 实例。
        adapter: ResponseAdapter 实例。
        jsonrpc: JSONRPCHandler 实例。
        _orchestrator: StableAgentOrchestrator 引用。
    """

    def __init__(self, orchestrator: Any = None) -> None:
        """初始化 MCPGateway。

        创建所有内部组件（UnifiedToolRegistry、ToolRouter、
        ResponseAdapter、JSONRPCHandler、RunStore、EventStream）。

        Args:
            orchestrator: StableAgentOrchestrator 实例，用于注入各组件。
                          None 时创建独立运行的 Gateway（部分功能受限）。
        """
        self._orchestrator: Any = orchestrator

        # 创建独立组件
        self.run_store: RunStore = RunStore()
        self.event_stream: EventStream = EventStream()

        # 创建工具注册中心
        self.registry: UnifiedToolRegistry = UnifiedToolRegistry(orchestrator)

        # 创建工具路由器
        self.router: ToolRouter = ToolRouter(
            registry=self.registry,
            security_policy=getattr(orchestrator, 'security_policy', None) if orchestrator else None,
            approval_manager=getattr(orchestrator, 'approval_manager', None) if orchestrator else None,
            run_store=self.run_store,
            event_stream=self.event_stream,
            event_bus=getattr(orchestrator, 'event_bus', None) if orchestrator else None,
        )

        # 创建适配器和 JSON-RPC 处理器
        self.adapter: ResponseAdapter = ResponseAdapter()
        self.jsonrpc: JSONRPCHandler = JSONRPCHandler(
            self.registry, self.router, self.adapter,
        )

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def create_fastapi_app(self) -> FastAPI:
        """创建包含 /mcp 端点的 FastAPI app。"""
        app: FastAPI = FastAPI(title="StableAgent Cloud — MCP Gateway")

        @app.post("/")
        async def mcp_post(req: Request):
            body: dict[str, Any] = await req.json()
            result: dict[str, Any] = self.jsonrpc.handle(body)

            # V5.5: 对 tools/call 结果注入 DecisionTrace 字段
            if body.get("method") == "tools/call":
                if "result" in result and "structuredContent" in result["result"]:
                    sc: dict[str, Any] = result["result"]["structuredContent"]
                    run_id: str = sc.get("run_id", "")
                    trace_url: str = f"/runs/{run_id}" if run_id else ""
                    stage_name: str = sc.get("current_stage", "execution")
                    sc["trace_url"] = trace_url
                    sc["dashboard_url"] = trace_url
                    sc["observer_url"] = f"/observe/{run_id}" if run_id else ""  # V6.0: 推荐入口
                    sc["current_stage"] = stage_name

                    # SaaS v1.3: 记录用量 & 审计
                    _record_saas_usage_and_audit(body, result)

            # V6.5: 递归序列化所有 dataclass → dict，防止 JSON 序列化错误
            result = self._serialize_dataclasses(result)
            return JSONResponse(content=result)

        @app.get("/")
        async def mcp_get(req: Request):
            run_id: str = req.query_params.get("run_id", "")
            if not run_id:
                return JSONResponse(
                    content={"error": "run_id required for SSE"},
                    status_code=400,
                )

            async def event_generator():
                """SSE 事件生成器。

                订阅指定 run_id 的事件流，持续产出 SSE 格式事件。
                客户端断开连接时自动取消订阅。
                """
                queue = await self.event_stream.subscribe(run_id)
                try:
                    while True:
                        event: dict[str, Any] = await queue.get()
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.CancelledError:
                    pass
                finally:
                    self.event_stream.unsubscribe(run_id, queue)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )

        return app

    @staticmethod
    def _serialize_dataclasses(obj: Any) -> Any:
        """递归将 dataclass 实例转为 dict，确保 JSON 可序列化。"""
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {f.name: MCPGateway._serialize_dataclasses(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if isinstance(obj, dict):
            return {k: MCPGateway._serialize_dataclasses(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [MCPGateway._serialize_dataclasses(v) for v in obj]
        return obj


# ===================================================================
# SaaS v1.3: 用量 & 审计辅助函数
# ===================================================================

def _record_saas_usage_and_audit(body: dict, result: dict) -> None:
    """记录每次 tools/call 的用量和审计事件（非阻塞，静默失败）。"""
    try:
        tool_name = body.get("params", {}).get("name", "")
        arguments = body.get("params", {}).get("arguments", {})
        sc = result.get("result", {}).get("structuredContent", {})

        ws_id = str(arguments.get("workspace_id", "") or sc.get("workspace_id", "") or "").strip()
        proj_id = str(arguments.get("project_id", "") or sc.get("project_id", "") or "").strip()
        run_id = sc.get("run_id", "")

        if not ws_id:
            return  # local mode, skip

        # Usage
        try:
            from stable_agent.saas import UsageCounter, SaasRepository
            uc = UsageCounter(SaasRepository())
            uc.record_mcp_tool_called(ws_id, proj_id, run_id or "", tool_name=tool_name)
        except Exception:
            import logging
            logging.getLogger("mcp_gateway").debug("UsageCounter record failed for tool: %s", tool_name)

        # Audit
        try:
            from stable_agent.saas import AuditLogger, SaasRepository
            audit = AuditLogger(SaasRepository())
            risk = result.get("result", {}).get("structuredContent", {}).get("risk_level", "low")
            if risk in ("high", "critical"):
                audit.log("mcp_tool_called", workspace_id=ws_id, project_id=proj_id,
                          target=f"tool:{tool_name}", details={"run_id": run_id, "risk": risk})
        except Exception:
            import logging
            logging.getLogger("mcp_gateway").debug("AuditLogger record failed for tool: %s", tool_name)
    except Exception:
        import logging
        logging.getLogger("mcp_gateway").debug("_record_saas_usage_and_audit failed")
