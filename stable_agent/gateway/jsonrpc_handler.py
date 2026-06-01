"""JSONRPCHandler — JSON-RPC 2.0 消息处理器。

支持 MCP 协议的三个核心方法：initialize、tools/list、tools/call。
输入为 JSON-RPC 请求字典，输出为 JSON-RPC 响应字典。

用法::

    handler = JSONRPCHandler(registry, router, adapter)
    response = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.gateway.response_adapter import ResponseAdapter

logger = logging.getLogger(__name__)


class JSONRPCHandler:
    """JSON-RPC 2.0 消息处理器。

    解析 JSON-RPC 请求，路由到对应处理方法，返回标准 JSON-RPC 2.0 响应。
    支持 MCP 协议的三个核心方法：

    - initialize: 返回服务器能力信息
    - tools/list: 返回所有已注册工具列表
    - tools/call: 执行指定工具调用

    Attributes:
        _registry: UnifiedToolRegistry 实例。
        _router: ToolRouter 实例。
        _adapter: ResponseAdapter 实例。
        _server_info: 服务器信息字典。
    """

    # 服务器名称和版本
    SERVER_NAME: str = "StableAgent OS"
    SERVER_VERSION: str = "11.4.0"
    PROTOCOL_VERSION: str = "2024-11-05"

    def __init__(
        self,
        registry: Any,
        router: Any,
        adapter: ResponseAdapter,
    ) -> None:
        """初始化 JSON-RPC 处理器。

        Args:
            registry: UnifiedToolRegistry 实例。
            router: ToolRouter 实例。
            adapter: ResponseAdapter 实例。
        """
        self._registry = registry
        self._router = router
        self._adapter = adapter

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理 JSON-RPC 2.0 请求。

        根据 method 字段路由到对应的处理方法。

        请求格式：
            {"jsonrpc": "2.0", "id": <id>, "method": "<method>", "params": {...}}

        支持的方法：
            - initialize: 返回服务器能力
            - tools/list: 返回所有工具列表
            - tools/call: 执行工具调用

        Args:
            request: JSON-RPC 2.0 请求字典。

        Returns:
            JSON-RPC 2.0 响应字典。

        Examples:
            >>> handler = JSONRPCHandler(None, None, ResponseAdapter())
            >>> resp = handler.handle({
            ...     "jsonrpc": "2.0", "id": 1, "method": "initialize"})
            >>> resp["result"]["serverInfo"]["name"]
            'StableAgent OS'
        """
        method: str = request.get("method", "")
        req_id = request.get("id")
        params: dict[str, Any] = request.get("params", {})

        if method == "initialize":
            return self._handle_initialize(req_id)
        elif method == "tools/list":
            return self._handle_tools_list(req_id)
        elif method == "tools/call":
            return self._handle_tools_call(req_id, params)
        else:
            return self._make_error(
                req_id, -32601, f"Method not found: {method}"
            )

    # ------------------------------------------------------------------
    # 方法处理器
    # ------------------------------------------------------------------

    def _handle_initialize(self, req_id: Any) -> dict[str, Any]:
        """处理 initialize 方法。

        返回服务器能力信息，包括协议版本、服务器名称和版本。

        Args:
            req_id: JSON-RPC 请求 ID。

        Returns:
            initialize 响应字典。
        """
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": self.PROTOCOL_VERSION,
                "serverInfo": {
                    "name": self.SERVER_NAME,
                    "version": self.SERVER_VERSION,
                },
                "capabilities": {
                    "tools": {},
                },
            },
        }

    def _handle_tools_list(self, req_id: Any) -> dict[str, Any]:
        """处理 tools/list 方法。

        返回所有 14 个注册工具的 MCP 格式列表。

        Args:
            req_id: JSON-RPC 请求 ID。

        Returns:
            tools/list JSON-RPC 响应字典。
        """
        try:
            tools: list[dict[str, Any]] = self._registry.list_tools()
            response: dict[str, Any] = self._adapter.to_tools_list_response(tools)
            response["id"] = req_id
            return response
        except Exception as exc:
            return self._make_error(
                req_id, -32603, f"tools/list 执行失败：{exc}"
            )

    def _handle_tools_call(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        """处理 tools/call 方法。

        从 params 中提取工具名称和参数，通过 ToolRouter 执行，
        将结果通过 ResponseAdapter 转换为 MCP 格式。

        Args:
            req_id: JSON-RPC 请求 ID。
            params: 包含 name 和 arguments 的参数字典。

        Returns:
            tools/call JSON-RPC 响应字典。
        """
        tool_name: str = params.get("name", "")
        arguments: dict[str, Any] = params.get("arguments", {})

        if not tool_name:
            return self._make_error(
                req_id, -32602, "缺少必要参数：name"
            )

        try:
            result = self._router.route(tool_name, arguments)
            mcp_content: dict[str, Any] = self._adapter.to_mcp_content(result)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": mcp_content,
            }
        except Exception as exc:
            logger.exception("tools/call 异常: tool=%s, args=%s", tool_name, arguments)
            error_response: dict[str, Any] = self._adapter.to_error_response(
                "", tool_name, f"工具调用失败：{exc}"
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": error_response,
            }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _make_error(
        self, req_id: Any, code: int, message: str
    ) -> dict[str, Any]:
        """构造 JSON-RPC 2.0 错误响应。

        Args:
            req_id: JSON-RPC 请求 ID。
            code: 错误代码（-32600 解析错误，-32601 方法未找到，-32602 无效参数，-32603 内部错误）。
            message: 错误描述信息。

        Returns:
            JSON-RPC 2.0 错误响应字典。
        """
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
