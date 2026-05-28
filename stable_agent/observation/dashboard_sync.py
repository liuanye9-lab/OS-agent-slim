"""DashboardSync — Dashboard per-run WebSocket 同步管理器。

管理 /ws/runs/{run_id} WebSocket 端点，将 EventStream 的事件按 run_id
推送到对应前端，实现 per-run 的实时 Dashboard 数据同步。

用法::

    from stable_agent.observation.dashboard_sync import DashboardSync
    dash_sync = DashboardSync(event_stream)
    app = dash_sync.create_app()
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from stable_agent.observation.event_stream import EventStream


class DashboardSync:
    """Dashboard per-run WebSocket 同步管理器。

    管理 /ws/runs/{run_id} WebSocket 端点，将 EventStream 的事件
    按 run_id 推送到对应前端的连接。支持同一 run_id 的多个并发连接。

    Attributes:
        event_stream: EventStream 实例，用于按 run_id 订阅事件。
    """

    def __init__(self, event_stream: "EventStream") -> None:
        """初始化 DashboardSync。

        Args:
            event_stream: EventStream 实例，用于按 run_id 订阅事件。
        """
        self.event_stream: EventStream = event_stream

    def create_app(self) -> FastAPI:
        """创建包含 /ws/runs/{run_id} 端点的 FastAPI 子应用。

        每个 WebSocket 连接对应一个 run_id，自动订阅 EventStream
        并将事件广播给同一 run_id 的所有连接。

        Returns:
            配置好 /ws/runs/{run_id} 端点的 FastAPI 应用实例。
        """
        app: FastAPI = FastAPI(title="Dashboard Per-Run Sync")
        active_connections: dict[str, list[WebSocket]] = {}

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
                        except Exception:
                            stale.append(ws)

                    # 清理失效连接
                    for ws in stale:
                        try:
                            active_connections[run_id].remove(ws)
                        except ValueError:
                            pass

            except WebSocketDisconnect:
                pass
            except Exception:
                pass
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
