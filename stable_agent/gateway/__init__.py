# V5 is the ONLY active MCP entry point. All new tools MUST be registered via UnifiedToolRegistry.
"""V5 Gateway 层 — 统一 MCP 工具调用入口。

本包提供 V5 的核心抽象：
- RunContext: 统一工具调用上下文，支持嵌套 span 追踪
- StableAgentToolResult: 统一 MCP 工具返回结构
- TOOLS: 14 个 stableagent.* 命名空间工具的 JSON Schema
- AVATAR_STATE_MAP: 事件类型 → 头像动画状态的映射
"""

from __future__ import annotations

# 版本断言：gateway 必须为 V5 唯一入口
assert __name__ == "stable_agent.gateway", (
    "V5 gateway 是唯一活跃的 MCP 入口点，不得通过其他路径导入。"
)

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.tool_schemas import (
    AVATAR_STATE_MAP,
    TOOLS,
    get_avatar_state,
    get_risk_level,
    get_tool_by_name,
    get_tool_names,
)
from stable_agent.models import StableAgentToolResult

__all__ = [
    "RunContext",
    "StableAgentToolResult",
    "TOOLS",
    "AVATAR_STATE_MAP",
    "get_tool_names",
    "get_tool_by_name",
    "get_avatar_state",
    "get_risk_level",
]
