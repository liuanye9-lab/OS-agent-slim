"""DashboardSync — Dashboard per-run WebSocket 同步管理器。

管理 /ws/runs/{run_id} WebSocket 端点，将 EventStream 的事件按 run_id
推送到对应前端，实现 per-run 的实时 Dashboard 数据同步。

也提供 sync_feedback() 方法，将用户反馈通过 EventStream 广播
给对应 run 的所有 WebSocket 连接。

用法::

    from stable_agent.observation.dashboard_sync import DashboardSync
    dash_sync = DashboardSync(event_stream)
    app = dash_sync.create_app()

    # 广播用户反馈
    dash_sync.sync_feedback(feedback_dict)
"""

from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stable_agent.observation.event_stream import EventStream


class DashboardSync:
    """Dashboard per-run WebSocket 同步管理器。

    管理 /ws/runs/{run_id} WebSocket 端点，将 EventStream 的事件
    按 run_id 推送到对应前端的连接。支持同一 run_id 的多个并发连接。

    同时提供 sync_feedback() 用于将用户反馈信号广播到
    对应 run 的所有 WebSocket 连接。

    Attributes:
        event_stream: EventStream 实例，用于按 run_id 订阅/发布事件。
    """

    def __init__(self, event_stream: "EventStream") -> None:
        """初始化 DashboardSync。

        Args:
            event_stream: EventStream 实例，用于按 run_id 订阅事件。
        """
        self.event_stream: EventStream = event_stream
        #: 跨方法可访问的活跃连接字典（由 create_app 设置）。
        self._active_connections: dict[str, list[WebSocket]] = {}

    def sync_feedback(self, feedback: dict[str, Any]) -> None:
        """将用户反馈通过 EventStream 和 WebSocket 广播。

        发布一个 type="user_feedback" 的事件到对应 run_id 的
        EventStream，所有订阅该 run 的 WebSocket 连接都会收到。

        Args:
            feedback: UserFeedbackSignal.to_dict() 的结果字典。
        """
        run_id: str = feedback.get("run_id", "")
        if not run_id:
            logger.warning("sync_feedback: 缺少 run_id，跳过广播")
            return

        event: dict[str, Any] = {
            "type": "user_feedback",
            "data": feedback,
        }
        self.event_stream.publish_sync(run_id, event)

    def create_app(self) -> FastAPI:
        """创建包含 /ws/runs/{run_id} 端点的 FastAPI 子应用。

        每个 WebSocket 连接对应一个 run_id，自动订阅 EventStream
        并将事件广播给同一 run_id 的所有连接。

        Returns:
            配置好 /ws/runs/{run_id} 端点的 FastAPI 应用实例。
        """
        app: FastAPI = FastAPI(title="Dashboard Per-Run Sync")
        active_connections: dict[str, list[WebSocket]] = {}
        # 将引用存到实例上，供 sync_feedback 等外部方法访问
        self._active_connections = active_connections

        @app.websocket("/ws/runs/{run_id}")
        async def ws_run(websocket: WebSocket, run_id: str) -> None:
            """Per-run WebSocket 端点。

            客户端连接后订阅对应 run_id 的 EventStream，
            接收实时事件并广播给该 run 的所有连接。

            Args:
                websocket: WebSocket 连接对象。
                run_id: 运行唯一标识。
            """
            await websocket.accept()

            # 注册连接
            if run_id not in active_connections:
                active_connections[run_id] = []
            active_connections[run_id].append(websocket)

            # 订阅 EventStream
            queue = await self.event_stream.subscribe(run_id)

            try:
                while True:
                    event: dict[str, Any] = await queue.get()
                    data: str = json.dumps(event, ensure_ascii=False)

                    # 广播给该 run 的所有连接
                    stale: list[WebSocket] = []
                    for ws in active_connections.get(run_id, []):
                        try:
                            await ws.send_text(data)
                        except Exception as e:
                            logger.debug("WebSocket 发送失败，标记为失效: %s", e)
                            stale.append(ws)

                    # 清理失效连接
                    for ws in stale:
                        try:
                            active_connections[run_id].remove(ws)
                        except ValueError:
                            pass

            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.exception("WebSocket 连接异常断开: %s", e)
            finally:
                # 清理连接
                if run_id in active_connections:
                    try:
                        active_connections[run_id].remove(websocket)
                    except ValueError:
                        pass
                    if not active_connections[run_id]:
                        del active_connections[run_id]

                # 取消订阅
                self.event_stream.unsubscribe(run_id, queue)

        return app
