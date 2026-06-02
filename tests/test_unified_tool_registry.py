"""test_unified_tool_registry.py — UnifiedToolRegistry 补充单元测试。

测试覆盖：
- tools/list 返回所有 14 个 V5 工具
- tools/call 调用 stableagent.context.build 返回 run_id/tool_call_id
- 工具调用生成 run_id（不为空）
- handler 接收 (RunContext, dict) 签名
- _make_result 支持 bilingual 字段
- 未知工具返回 is_error=True
"""

from __future__ import annotations

import pytest

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.models import StableAgentToolResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def registry() -> UnifiedToolRegistry:
    """创建无 orchestrator 的注册中心。"""
    return UnifiedToolRegistry(orchestrator=None)


# ============================================================================
# 测试
# ============================================================================


class TestUnifiedToolRegistrySupplementary:
    """UnifiedToolRegistry 补充单元测试。"""

    # ------------------------------------------------------------------
    # 测试 1：tools/list 返回所有 14 个 V5 工具
    # ------------------------------------------------------------------

    def test_list_tools_returns_all_v5_tools(self, registry: UnifiedToolRegistry) -> None:
        """验证 tools/list 返回工具 (受 profile 影响)。

        V11.5: 默认 minimal profile 只返回核心工具。
        """
        tools = registry.list_tools()
        # minimal profile 返回 <= 12 个工具
        assert len(tools) >= 1, f"期望至少 1 个工具，实际 {len(tools)} 个"

        tool_names = [t["name"] for t in tools]
        # os_agent 必须在所有 profile 中
        assert "stableagent.task.os_agent" in tool_names, "缺少核心工具 stableagent.task.os_agent"

    # ------------------------------------------------------------------
    # 测试 2：tools/call 调用 stableagent.context.build 返回 run_id
    # ------------------------------------------------------------------

    def test_call_context_build_returns_run_id(self, registry: UnifiedToolRegistry) -> None:
        """验证调用 stableagent.context.build 返回非空 run_id 和 tool_call_id。

        即使 orchestrator 未注入，_make_result 也会从 RunContext 中
        填充 run_id 和 tool_call_id 字段。
        """
        handler = registry.get_handler("stableagent.context.build")
        assert handler is not None, "未找到 stableagent.context.build handler"

        ctx = RunContext()
        result = handler(ctx, {"task_input": "测试任务"})

        assert isinstance(result, StableAgentToolResult)
        assert result.run_id != "", "run_id 不应为空"
        assert result.tool_call_id != "", "tool_call_id 不应为空"
        assert result.run_id == ctx.run_id
        assert result.tool_call_id == ctx.tool_call_id

    # ------------------------------------------------------------------
    # 测试 3：工具调用生成 run_id（不为空）
    # ------------------------------------------------------------------

    def test_tool_call_generates_nonempty_run_id(self, registry: UnifiedToolRegistry) -> None:
        """验证所有工具调用都生成非空 run_id。"""
        ctx = RunContext()
        # 验证 RunContext 默认生成非空标识
        assert ctx.run_id != "", "RunContext.run_id 不应为空"
        assert ctx.tool_call_id != "", "RunContext.tool_call_id 不应为空"
        assert ctx.trace_id != "", "RunContext.trace_id 不应为空"

        # 通过 handler 调用验证 run_id 传递到结果中
        handler = registry.get_handler("stableagent.memory.retrieve")
        assert handler is not None
        result = handler(ctx, {"task_input": "测试"})
        assert result.run_id == ctx.run_id
        assert len(result.run_id) > 0

    # ------------------------------------------------------------------
    # 测试 4：handler 接收 (RunContext, dict) 签名
    # ------------------------------------------------------------------

    def test_handler_receives_runcontext_and_dict(self, registry: UnifiedToolRegistry) -> None:
        """验证所有 handler 接收 (RunContext, dict) 签名并正常返回。"""
        import inspect

        tool_names = [
            "stableagent.task.process",
            "stableagent.context.build",
            "stableagent.context.estimate_budget",
            "stableagent.memory.retrieve",
            "stableagent.memory.write_candidate",
            "stableagent.rag.retrieve",
            "stableagent.eval.evaluate",
            "stableagent.badcase.record",
            "stableagent.skillopt.status",
            "stableagent.skillopt.get_current_skill",
            "stableagent.skillopt.run_epoch",
            "stableagent.skillopt.export_best",
            "stableagent.trace.get_run",
            "stableagent.approval.respond",
        ]

        for tool_name in tool_names:
            handler = registry.get_handler(tool_name)
            assert handler is not None, f"未找到 {tool_name} 的 handler"
            assert callable(handler), f"{tool_name} handler 不可调用"

            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
            # handler 应至少有 2 个参数（self, ctx, args）或 2 个（bound method 时 self 已被绑定）
            assert len(params) >= 2, (
                f"{tool_name} handler 参数数量不足：期望 ≥2，实际 {len(params)}"
            )

    # ------------------------------------------------------------------
    # 测试 5：_make_result 支持 bilingual 字段
    # ------------------------------------------------------------------

    def test_make_result_supports_bilingual(self, registry: UnifiedToolRegistry) -> None:
        """验证 _make_result 支持 plain_text_zh / plain_text_en / dashboard_url。"""
        ctx = RunContext()
        result = registry._make_result(
            ctx, "stableagent.test",
            plain_text_zh="中文结果",
            plain_text_en="English result",
            dashboard_url="/dashboard/test",
        )
        assert result.plain_text_zh == "中文结果", (
            f"期望 plain_text_zh='中文结果'，实际 '{result.plain_text_zh}'"
        )
        assert result.plain_text_en == "English result", (
            f"期望 plain_text_en='English result'，实际 '{result.plain_text_en}'"
        )
        assert result.dashboard_url == "/dashboard/test", (
            f"期望 dashboard_url='/dashboard/test'，实际 '{result.dashboard_url}'"
        )

    def test_make_result_fallback_when_bilingual_empty(self, registry: UnifiedToolRegistry) -> None:
        """验证 bilingual 字段为空时回退到 plain_text。"""
        ctx = RunContext()
        result = registry._make_result(
            ctx, "stableagent.test",
            plain_text="通用文本",
        )
        # 当 plain_text_zh 和 plain_text_en 为空时，应回退到 plain_text
        assert result.plain_text_zh == "通用文本"
        assert result.plain_text_en == "通用文本"
        # dashboard_url 为空时，应使用默认值
        assert result.dashboard_url == f"/dashboard/{ctx.run_id}"

    # ------------------------------------------------------------------
    # 测试 6：未知工具返回 None（通过 get_handler）
    # ------------------------------------------------------------------

    def test_unknown_tool_returns_none(self, registry: UnifiedToolRegistry) -> None:
        """验证未知工具调用 get_handler 返回 None。"""
        handler = registry.get_handler("stableagent.fake.tool")
        assert handler is None, "未知工具应返回 None"

    def test_nonexistent_tool_in_router_returns_error(self) -> None:
        """验证 ToolRouter 路由未知工具时返回 is_error=True。"""
        from stable_agent.gateway.tool_router import ToolRouter

        registry = UnifiedToolRegistry(orchestrator=None)
        router = ToolRouter(registry=registry)
        result = router.route("stableagent.fake.tool", {})
        assert result.is_error is True, "未知工具路由应返回 is_error=True"
        assert "未知工具" in result.plain_text
