"""实时 Dashboard — WebSocket + REST explain API。

本模块提供 StableAgent OS 的实时可视化面板：
- WebSocket 端点实时推送事件到浏览器
- REST API 提供事件的大白话解释

V3 升级：
- 新增 /api/run/{run_id}/trace 端点
- 新增 /api/bad-cases 端点
- 新增 /api/eval-trend 端点
- 新增 /api/approvals/pending 端点
- 新增 /api/summary 端点
- 新增 orchestrator 可选依赖注入

模块职责：
- 创建 FastAPI app（可挂载到主应用）
- 管理 WebSocket 连接池
- 订阅 EventBus 并桥接到 WebSocket
- 提供事件类型 → 中文解释映射
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from stable_agent.trace_event_bus import EventBus


# ============================================================================
# 事件解释映射表
# ============================================================================

EXPLANATIONS: dict[str, str] = {
    "workflow:started": "🧠 它刚刚接到任务，开始思考怎么处理。",
    "memory:retrieval": "🔍 它正在翻找以前的记忆卡片，看看有没有相似的经验。",
    "memory:retrieving": "🔍 它正在翻找以前的记忆卡片，看看有没有相似的经验。",
    "memory:retrieved": "📋 找到了一些相关的记忆，正在筛选最有用的那些。",
    "rag:searched": "📚 它正在查阅知识库，寻找参考资料。",
    "workflow:planned": "📐 它正在估算这次要花多少 token，选择用大模型还是小模型。",
    "execute:completed": "⚡ 任务执行完毕，正在检查结果质量。",
    "eval:completed": "📊 它正在给自己打分，看看这次做得怎么样。",
    "workflow:completed": "🎉 全部完成！正在总结经验，把好的做法记录下来。",
    "workflow:init": "🚀 准备工作就绪，马上开始处理任务。",
    # V3 新增事件解释
    "budget:allocated": "📐 它正在估算这次要花多少 token，选择用大模型还是小模型。",
    "context:built": "📦 上下文包组装完毕，准备开始干活。",
    "approval:required": "✋ 这一步可能影响文件或执行命令，需要你确认。",
    "approval:pending": "✋ 它在等待你的审批，不敢擅自行动。",
    "workflow:paused": "⏸️ 工作流已暂停，等待外部输入。",
    "workflow:resumed": "▶️ 工作流已恢复，接着之前的地方继续。",
    "workflow:failed": "❌ 出错了，它摔倒了但会显示错误原因。",
}

DEFAULT_EXPLANATION: str = "⏳ 它正在处理下一步。"


# ============================================================================
# Dashboard — 实时可视化面板
# ============================================================================


class Dashboard:
    """实时 Dashboard — WebSocket + REST explain API。

    订阅 EventBus 获取事件，通过 WebSocket 推送到浏览器客户端，
    同时提供 REST API 用于查询事件的大白话解释。

    V3 新增：
    - orchestrator: 可选依赖，用于查询 run trace/bad cases/approvals/summary。
    - 5 个新 REST 端点

    Attributes:
        event_bus: 事件总线实例（注入）。
        app: FastAPI 应用实例。
        _ws_clients: 已连接的 WebSocket 客户端列表。
        orchestrator: 可选的 orchestrator 引用。
    """

    def __init__(
        self,
        event_bus: EventBus,
        orchestrator: Optional[object] = None,
        skillopt_engine: Optional[object] = None,
    ) -> None:
        """初始化 Dashboard。

        创建 FastAPI app，注册路由和 WebSocket 端点，
        并订阅 EventBus 以桥接事件到 WebSocket。

        Args:
            event_bus: 事件总线实例。
            orchestrator: 可选的 StableAgentOrchestrator 引用（V3 新增）。
            skillopt_engine: 可选的 SkillOptimizationEngine 引用（V4 新增）。
        """
        self.event_bus: EventBus = event_bus
        self._ws_clients: list[WebSocket] = []
        self.orchestrator: Optional[object] = orchestrator
        self.skillopt_engine: Optional[object] = skillopt_engine

        # 创建 FastAPI app
        self.app: FastAPI = FastAPI(title="StableAgent Dashboard", version="0.2.0")

        # 注册路由
        self._register_routes()

        # 订阅 EventBus — 将事件桥接到 WebSocket
        self.event_bus.subscribe(self._on_event)

    # ------------------------------------------------------------------
    # 路由注册
    # ------------------------------------------------------------------

    def _register_routes(self) -> None:
        """注册所有路由和 WebSocket 端点。"""
        app: FastAPI = self.app

        # ----- GET /explain/{event_type} -----
        @app.get("/explain/{event_type}")
        async def explain_event(event_type: str) -> dict:
            """返回事件类型的大白话解释。

            从预定义的 EXPLANATIONS 字典中查找解释，未匹配时返回默认解释。

            Args:
                event_type: 事件类型标识符。

            Returns:
                包含 explanation 字段的字典。
            """
            explanation: str = EXPLANATIONS.get(event_type, DEFAULT_EXPLANATION)
            return {
                "event_type": event_type,
                "explanation": explanation,
            }

        # ----- WebSocket /ws/events -----
        @app.websocket("/ws/events")
        async def ws_events(websocket: WebSocket) -> None:
            """WebSocket 端点 — 实时推送事件。

            客户端连接后加入 _ws_clients 列表，服务端通过 EventBus
            监听器将所有新事件推送给所有已连接的客户端。

            推送 JSON 格式：
            {
                "type": "event",
                "data": {
                    "timestamp": ...,
                    "type": "...",
                    "payload": {...}
                }
            }

            客户端断开时自动清理连接。
            """
            await websocket.accept()
            self._ws_clients.append(websocket)

            try:
                # 保持连接直到客户端断开
                while True:
                    # 等待客户端消息（用于心跳检测）
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass
            except Exception:
                pass
            finally:
                # 清理断开连接的客户端
                if websocket in self._ws_clients:
                    self._ws_clients.remove(websocket)

        # ==============================================================
        # V3 新增端点
        # ==============================================================

        # ----- GET /api/run/{run_id}/trace -----
        @app.get("/api/run/{run_id}/trace")
        async def get_run_trace(run_id: str) -> dict:
            """获取 run 的 trace spans。

            Args:
                run_id: 运行 ID。

            Returns:
                JSON 包含 spans 列表和计数。
            """
            if self.orchestrator is None:
                return {"ok": False, "message": "Orchestrator not configured"}
            try:
                spans = self.orchestrator.get_run_trace(run_id)
                return {
                    "ok": True,
                    "run_id": run_id,
                    "spans": [
                        {
                            "span_id": s.span_id,
                            "name": s.name,
                            "type": s.type,
                            "status": s.status,
                            "latency_ms": s.latency_ms,
                            "input_tokens": s.input_tokens,
                            "output_tokens": s.output_tokens,
                        }
                        for s in spans
                    ],
                    "count": len(spans),
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ----- GET /api/bad-cases -----
        @app.get("/api/bad-cases")
        async def get_bad_cases(limit: int = 20) -> dict:
            """获取最近 bad cases。

            Args:
                limit: 返回数量上限，默认 20。

            Returns:
                JSON 包含 bad_cases 列表。
            """
            if self.orchestrator is None:
                return {"ok": False, "message": "Orchestrator not configured"}
            try:
                cases = self.orchestrator.bad_case_manager.retrieve_recent_bad_cases(
                    limit=limit
                )
                return {
                    "ok": True,
                    "bad_cases": [
                        {
                            "task_type": c.task_type.value,
                            "input_context": c.input_context[:200],
                            "overall_score": c.evaluation.overall_score,
                            "timestamp": c.timestamp,
                            "failure_reason": c.failure_reason,
                        }
                        for c in cases
                    ],
                    "count": len(cases),
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ----- GET /api/eval-trend -----
        @app.get("/api/eval-trend")
        async def get_eval_trend() -> dict:
            """获取评分趋势（最近 10 次 overall_score）。

            Returns:
                JSON 包含 scores 列表。
            """
            if self.orchestrator is None:
                return {"ok": False, "message": "Orchestrator not configured"}
            try:
                # 从 storage 加载最近 runs
                runs = self.orchestrator.storage.list_runs(limit=10)
                scores = [
                    {
                        "run_id": r.run_id,
                        "task": r.user_task[:80],
                        "overall_score": r.overall_score,
                        "started_at": r.started_at,
                    }
                    for r in runs
                    if r.overall_score is not None
                ]
                return {
                    "ok": True,
                    "scores": scores,
                    "count": len(scores),
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ----- GET /api/approvals/pending -----
        @app.get("/api/approvals/pending")
        async def get_pending_approvals() -> dict:
            """获取待审批列表。

            Returns:
                JSON 包含 approvals 列表。
            """
            if self.orchestrator is None:
                return {"ok": False, "message": "Orchestrator not configured"}
            try:
                approvals = self.orchestrator.approval_manager.list_pending()
                return {
                    "ok": True,
                    "approvals": [
                        {
                            "request_id": a.request_id,
                            "run_id": a.run_id,
                            "action": a.action,
                            "risk": a.risk,
                            "reason": a.reason,
                            "status": a.status,
                        }
                        for a in approvals
                    ],
                    "count": len(approvals),
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ----- GET /api/summary -----
        @app.get("/api/summary")
        async def get_system_summary() -> dict:
            """获取系统摘要：memory_count/event_count/tool_count/run_count。

            Returns:
                JSON 包含系统摘要数据。
            """
            if self.orchestrator is None:
                return {"ok": False, "message": "Orchestrator not configured"}
            try:
                summary = self.orchestrator.get_summary()
                return {
                    "ok": True,
                    "summary": summary,
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ==============================================================
        # V4 新增端点: SkillOpt 状态
        # ==============================================================

        # ----- GET /api/skillopt/status -----
        @app.get("/api/skillopt/status")
        async def skillopt_status() -> dict:
            """获取 SkillOpt 引擎状态。

            Returns:
                JSON 包含 total_epochs、accepted/rejected patches 等。
            """
            if self.skillopt_engine is None:
                return {"ok": False, "message": "SkillOpt engine not configured"}
            try:
                engine = self.skillopt_engine
                best_version = "未生成"
                current_version = "未知"
                try:
                    best = engine.doc_store.load_best_skill()
                    if best is not None:
                        best_version = best.version
                except Exception:
                    pass
                try:
                    current = engine.doc_store.load_current_skill()
                    current_version = current.version
                except Exception:
                    pass

                return {
                    "ok": True,
                    "status": {
                        "total_epochs": engine._epoch_count,
                        "accepted_patches": len(engine._accepted_patches),
                        "rejected_patches": len(engine._rejected_patches),
                        "longitudinal_entries": len(
                            engine._longitudinal_results
                        ),
                        "best_version": best_version,
                        "current_version": current_version,
                    },
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ----- GET /api/skillopt/current_skill -----
        @app.get("/api/skillopt/current_skill")
        async def skillopt_current() -> dict:
            """获取当前技能文档摘要。

            Returns:
                JSON 包含 version、content 前 200 字符等。
            """
            if self.skillopt_engine is None:
                return {"ok": False, "message": "SkillOpt engine not configured"}
            try:
                engine = self.skillopt_engine
                skill = engine.doc_store.load_current_skill()
                return {
                    "ok": True,
                    "skill": {
                        "version": skill.version,
                        "content_preview": skill.content[:200],
                        "status": skill.status,
                        "content_length": len(skill.content),
                    },
                }
            except FileNotFoundError:
                return {
                    "ok": False,
                    "message": "当前技能文档不存在",
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

        # ----- GET /api/skillopt/recent_epochs -----
        @app.get("/api/skillopt/recent_epochs")
        async def skillopt_recent_epochs(limit: int = 5) -> dict:
            """获取最近优化回合的结果。

            Args:
                limit: 返回数量上限，默认 5。

            Returns:
                JSON 包含 epochs 列表。
            """
            if self.skillopt_engine is None:
                return {"ok": False, "message": "SkillOpt engine not configured"}
            try:
                engine = self.skillopt_engine
                recent = engine._longitudinal_results[-limit:]
                recent.reverse()
                return {
                    "ok": True,
                    "epochs": recent,
                    "count": len(recent),
                }
            except Exception as e:
                return {"ok": False, "message": str(e)}

    # ------------------------------------------------------------------
    # 事件桥接
    # ------------------------------------------------------------------

    def _on_event(self, event) -> None:
        """EventBus 监听器回调 — 将事件推送到所有 WebSocket 客户端。

        Args:
            event: EventBus 发布的 Event 实例。
        """
        import asyncio

        message: dict = {
            "type": "event",
            "data": {
                "timestamp": event.timestamp,
                "type": event.type,
                "payload": event.payload,
            },
        }

        # 使用 asyncio 创建任务推送到所有客户端
        # 注意：此方法在 EventBus.publish 的同步上下文中被调用，
        # 需要异步发送 WebSocket 消息
        for client in list(self._ws_clients):
            try:
                # 在事件循环中异步发送
                import json

                async def send_to_client(ws: WebSocket, msg: dict) -> None:
                    try:
                        await ws.send_text(json.dumps(msg, ensure_ascii=False))
                    except Exception:
                        # 发送失败，清理客户端
                        if ws in self._ws_clients:
                            self._ws_clients.remove(ws)

                # 尝试获取当前事件循环并创建任务
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(send_to_client(client, message))
                except RuntimeError:
                    # 没有运行中的事件循环（如测试环境），跳过
                    pass
            except Exception:
                # 单个客户端失败不影响其他
                pass

    # ------------------------------------------------------------------
    # 挂载
    # ------------------------------------------------------------------

    def mount_to(self, main_app, prefix: str = "/dashboard") -> None:
        """将 Dashboard 的 FastAPI app 挂载到主应用上。

        使用 FastAPI 的 app.mount 机制将本 dashboard 作为子应用
        挂载到指定前缀路径下。

        Args:
            main_app: 主 FastAPI 应用实例。
            prefix: 挂载路径前缀，默认 "/dashboard"。
        """
        main_app.mount(prefix, self.app)
