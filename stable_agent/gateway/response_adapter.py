"""ResponseAdapter — 将 StableAgentToolResult 转换为 MCP 标准格式。

提供三组转换：工具调用结果 → MCP content、错误 → 错误响应、
工具列表 → JSON-RPC tools/list 响应。

用法::

    adapter = ResponseAdapter()
    mcp_response = adapter.to_mcp_content(tool_result)
    error_response = adapter.to_error_response(run_id, tool_name, "失败原因")
    tools_list = adapter.to_tools_list_response(tools)
"""

from __future__ import annotations

from typing import Any

from stable_agent.models import StableAgentToolResult


class ResponseAdapter:
    """将 StableAgentToolResult 转换为 MCP content 格式。

    负责 V5 工具返回结果到 MCP 协议格式的标准化转换，
    支持成功响应、错误响应和 tools/list 响应的生成。
    """

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def to_mcp_content(self, result: StableAgentToolResult) -> dict[str, Any]:
        """将 StableAgentToolResult 转换为 MCP content 格式。

        生成标准的 MCP tools/call 响应，包含 content 数组和
        structuredContent 对象。

        Args:
            result: StableAgentToolResult 实例。

        Returns:
            MCP 格式的 content 响应字典，结构为：
            {
                "content": [{"type": "text", "text": "..."}],
                "structuredContent": {...},
                "isError": bool
            }

        Examples:
            >>> result = StableAgentToolResult(
            ...     ok=True, run_id="r1", tool_name="test.tool",
            ...     plain_text="成功", data={"count": 5})
            >>> adapter = ResponseAdapter()
            >>> resp = adapter.to_mcp_content(result)
            >>> resp["content"][0]["type"]
            'text'
            >>> resp["structuredContent"]["ok"]
            True
        """
        return {
            "content": [
                {"type": "text", "text": result.plain_text}
            ],
            "structuredContent": {
                "ok": result.ok,
                "run_id": result.run_id,
                "tool_name": result.tool_name,
                "data": result.data,
                "warnings": result.warnings,
                "next_actions": result.next_actions,
                "trace_url": result.trace_url,
                # V5.5 新增字段
                "current_stage": result.data.get("stage", "execution"),
                "plain_text_zh": result.plain_text,
                "plain_text_en": result.data.get("plain_text_en", result.plain_text),
                "dashboard_url": f"/runs/{result.run_id}",
            },
            "isError": result.is_error,
        }

    def to_error_response(
        self,
        run_id: str,
        tool_name: str,
        error_msg: str,
    ) -> dict[str, Any]:
        """生成 MCP 错误响应。

        当工具执行失败或出现异常时，使用此方法生成标准化错误响应。

        Args:
            run_id: 运行 ID。
            tool_name: 工具名称。
            error_msg: 错误描述信息。

        Returns:
            MCP 格式的错误响应字典。

        Examples:
            >>> adapter = ResponseAdapter()
            >>> resp = adapter.to_error_response("r1", "test.tool", "参数无效")
            >>> resp["isError"]
            True
            >>> resp["content"][0]["text"]
            '参数无效'
        """
        return {
            "content": [
                {"type": "text", "text": error_msg}
            ],
            "structuredContent": {
                "ok": False,
                "run_id": run_id,
                "tool_name": tool_name,
                "data": {},
                "warnings": [],
                "next_actions": [],
                "trace_url": f"/runs/{run_id}",
            },
            "isError": True,
        }

    def to_tools_list_response(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """生成 MCP tools/list 的 JSON-RPC 响应。

        将工具定义列表包装为标准的 JSON-RPC 2.0 响应格式。

        Args:
            tools: 工具定义列表，每个元素包含 name、description、input_schema。

        Returns:
            JSON-RPC 2.0 格式的 tools/list 响应字典。

        Examples:
            >>> adapter = ResponseAdapter()
            >>> tools = [{"name": "test.tool", "description": "测试工具"}]
            >>> resp = adapter.to_tools_list_response(tools)
            >>> resp["jsonrpc"]
            '2.0'
            >>> resp["result"]["tools"][0]["name"]
            'test.tool'
        """
        return {
            "jsonrpc": "2.0",
            "id": None,
            "result": {"tools": tools},
        }
