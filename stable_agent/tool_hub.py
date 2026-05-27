"""工具注册与调用中心模块。

本模块提供 ToolHub 类，管理外部工具的注册、查找、调用和注销。
所有工具通过统一的 schema 格式注册，调用时自动校验参数并捕获异常。

模块职责：
- 注册/注销外部工具
- 按名称调用工具
- 查询工具列表和 schema

# STUB: 真实部署时可通过此 Hub 连接第三方服务（Slack、Notion、Google Docs），
# 并在 MCP Server 中暴露为额外接口。需加入安全控制（白名单、权限校验），
# 避免模型滥用敏感工具。可扩展为动态加载 Tool Plugin。
"""

from __future__ import annotations

import warnings
from typing import Any, Callable


class ToolHub:
    """外部工具注册与调用中心。

    管理一个工具注册表，提供注册、查找、调用和注销功能。
    每个工具由名称唯一标识，携带调用函数、参数 schema 和描述。

    Attributes:
        tools: name → {"callable": Callable, "schema": dict, "description": str} 的字典。
    """

    def __init__(self) -> None:
        """初始化空的工具注册表。"""
        self.tools: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        tool_callable: Callable[..., Any],
        schema: dict[str, Any],
        description: str = "",
    ) -> None:
        """注册一个外部工具。

        如果 name 已存在，打印警告并覆盖旧工具。

        Args:
            name: 工具唯一名称。
            tool_callable: 工具的可调用对象。
            schema: JSON Schema 格式的参数描述，例如
                {"type": "object", "properties": {"param1": {"type": "string"}}, "required": ["param1"]}。
            description: 工具的人类可读描述。

        Examples:
            >>> hub = ToolHub()
            >>> hub.register_tool("echo", lambda x: x, {"type": "object", "properties": {"x": {"type": "string"}}})
            >>> len(hub.tools)
            1
        """
        if name in self.tools:
            warnings.warn(
                f"Tool '{name}' already registered, overwriting.",
                stacklevel=2,
            )
        self.tools[name] = {
            "callable": tool_callable,
            "schema": schema,
            "description": description,
        }

    def list_tools(self) -> list[dict[str, str]]:
        """列出所有已注册工具的名称和描述。

        Returns:
            工具信息列表，每项包含 "name" 和 "description"。

        Examples:
            >>> hub = ToolHub()
            >>> hub.register_tool("greet", lambda: "hi", {}, "Says hi")
            >>> hub.list_tools()
            [{'name': 'greet', 'description': 'Says hi'}]
        """
        return [
            {"name": name, "description": info["description"]}
            for name, info in self.tools.items()
        ]

    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        """调用指定工具。

        根据 name 查找工具，使用 args 作为关键字参数调用 tool_callable。
        捕获并返回调用过程中的异常信息。

        Args:
            name: 要调用的工具名称。
            args: 传递给工具的关键字参数字典。

        Returns:
            工具调用的返回值，或错误信息字符串（异常时）。

        Raises:
            ValueError: 如果 name 对应的工具不存在。

        Examples:
            >>> hub = ToolHub()
            >>> hub.register_tool("add", lambda a, b: a + b, {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}})
            >>> hub.call_tool("add", {"a": 1, "b": 2})
            3
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' is not registered.")

        tool_info: dict = self.tools[name]
        tool_callable: Callable[..., Any] = tool_info["callable"]

        try:
            return tool_callable(**args)
        except Exception as exc:
            return f"Tool '{name}' execution error: {exc}"

    def unregister_tool(self, name: str) -> bool:
        """注销指定工具。

        Args:
            name: 要注销的工具名称。

        Returns:
            True 表示工具存在并被移除，False 表示工具不存在。

        Examples:
            >>> hub = ToolHub()
            >>> hub.register_tool("test", lambda: None, {})
            >>> hub.unregister_tool("test")
            True
            >>> hub.unregister_tool("nonexistent")
            False
        """
        if name in self.tools:
            del self.tools[name]
            return True
        return False

    def get_tool_schema(self, name: str) -> dict | None:
        """获取工具的 JSON Schema。

        Args:
            name: 工具名称。

        Returns:
            工具的 schema 字典，如果工具不存在返回 None。

        Examples:
            >>> hub = ToolHub()
            >>> schema = {"type": "object", "properties": {}}
            >>> hub.register_tool("empty", lambda: None, schema)
            >>> hub.get_tool_schema("empty") == schema
            True
            >>> hub.get_tool_schema("missing") is None
            True
        """
        tool_info: dict | None = self.tools.get(name)
        if tool_info is None:
            return None
        return tool_info["schema"]
