"""P2 高级模块 + 编排器测试套件。

覆盖 ToolHub、Sandbox、StableAgentOrchestrator 的所有核心功能。

测试数量：26 个，覆盖所有关键逻辑路径。
"""

from __future__ import annotations

import time

import pytest

from stable_agent.models import (
    EvaluationResult,
    MemoryItem,
    SandboxResult,
    TaskType,
)

# ============================================================================
# 模块导入
# ============================================================================

from stable_agent.tool_hub import ToolHub
from stable_agent.swe_sandbox import Sandbox
from stable_agent.orchestrator import StableAgentOrchestrator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tool_hub() -> ToolHub:
    """创建 ToolHub 实例的 fixture。"""
    return ToolHub()


@pytest.fixture
def sandbox() -> Sandbox:
    """创建 Sandbox 实例的 fixture。"""
    return Sandbox(timeout=5)


@pytest.fixture
def orchestrator() -> StableAgentOrchestrator:
    """创建 StableAgentOrchestrator 实例的 fixture。"""
    return StableAgentOrchestrator()


# ============================================================================
# ToolHub 测试 (8 tests)
# ============================================================================


class TestToolHub:
    """ToolHub 类的单元测试。"""

    def test_register_tool(self, tool_hub: ToolHub) -> None:
        """测试注册工具。"""
        tool_hub.register_tool(
            name="echo",
            tool_callable=lambda x: x,
            schema={"type": "object", "properties": {"x": {"type": "string"}}},
            description="Echo back the input",
        )
        assert "echo" in tool_hub.tools
        assert tool_hub.tools["echo"]["description"] == "Echo back the input"

    def test_register_duplicate_tool_overwrites(self, tool_hub: ToolHub) -> None:
        """测试注册重复工具名时覆盖旧工具并发出警告。"""
        tool_hub.register_tool(
            name="dup",
            tool_callable=lambda: 1,
            schema={},
            description="First",
        )
        with pytest.warns(UserWarning, match="already registered"):
            tool_hub.register_tool(
                name="dup",
                tool_callable=lambda: 2,
                schema={},
                description="Second",
            )
        assert tool_hub.tools["dup"]["description"] == "Second"

    def test_list_tools(self, tool_hub: ToolHub) -> None:
        """测试列出所有已注册工具。"""
        tool_hub.register_tool("t1", lambda: None, {}, "First tool")
        tool_hub.register_tool("t2", lambda: None, {}, "Second tool")
        tools_list: list[dict[str, str]] = tool_hub.list_tools()
        assert len(tools_list) == 2
        names: set[str] = {t["name"] for t in tools_list}
        assert names == {"t1", "t2"}

    def test_call_tool_success(self, tool_hub: ToolHub) -> None:
        """测试正常调用工具。"""
        tool_hub.register_tool(
            name="add",
            tool_callable=lambda a, b: a + b,
            schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        )
        result: int = tool_hub.call_tool("add", {"a": 10, "b": 20})
        assert result == 30

    def test_call_tool_with_exception(self, tool_hub: ToolHub) -> None:
        """测试工具调用产生异常时返回错误字符串。"""
        tool_hub.register_tool(
            name="fail",
            tool_callable=lambda: 1 / 0,
            schema={},
        )
        result: str = tool_hub.call_tool("fail", {})
        assert isinstance(result, str)
        assert "error" in result.lower()

    def test_call_tool_not_found_raises_value_error(self, tool_hub: ToolHub) -> None:
        """测试调用不存在的工具抛出 ValueError。"""
        with pytest.raises(ValueError, match="not registered"):
            tool_hub.call_tool("nonexistent", {})

    def test_unregister_tool(self, tool_hub: ToolHub) -> None:
        """测试注销工具。"""
        tool_hub.register_tool("temp", lambda: None, {})
        assert tool_hub.unregister_tool("temp") is True
        assert "temp" not in tool_hub.tools
        assert tool_hub.unregister_tool("temp") is False

    def test_get_tool_schema(self, tool_hub: ToolHub) -> None:
        """测试获取工具的 schema。"""
        schema: dict = {"type": "object", "properties": {"x": {"type": "number"}}}
        tool_hub.register_tool("math", lambda x: x * 2, schema)
        assert tool_hub.get_tool_schema("math") == schema
        assert tool_hub.get_tool_schema("missing") is None


# ============================================================================
# Sandbox 测试 (7 tests)
# ============================================================================


class TestSandbox:
    """Sandbox 类的单元测试。"""

    def test_run_command_success(self, sandbox: Sandbox) -> None:
        """测试成功执行命令。"""
        result: SandboxResult = sandbox.run_command(["echo", "hello_world"])
        assert result.return_code == 0
        assert "hello_world" in result.stdout

    def test_run_command_failure(self, sandbox: Sandbox) -> None:
        """测试执行失败命令。"""
        result: SandboxResult = sandbox.run_command(
            ["python", "-c", "import sys; sys.exit(42)"]
        )
        assert result.return_code == 42

    def test_run_command_timeout(self, sandbox: Sandbox) -> None:
        """测试命令超时。"""
        # 使用 sleep 命令触发超时
        result: SandboxResult = sandbox.run_command(
            ["python", "-c", "import time; time.sleep(10)"],
            timeout=1,
        )
        assert result.return_code == -1
        assert "timed out" in result.stderr.lower()

    def test_execute_script_success(self, sandbox: Sandbox) -> None:
        """测试成功执行 Python 脚本。"""
        result: SandboxResult = sandbox.execute_script(
            "print('hello sandbox')", timeout=5
        )
        assert result.return_code == 0
        assert "hello sandbox" in result.stdout

    def test_execute_script_with_error(self, sandbox: Sandbox) -> None:
        """测试执行有语法错误的脚本。"""
        result: SandboxResult = sandbox.execute_script(
            "print('start'); raise ValueError('boom')", timeout=5
        )
        # 应该非零退出码
        assert result.return_code != 0

    def test_safe_run_success(self, sandbox: Sandbox) -> None:
        """测试 safe_run 成功执行函数。"""
        result: int = sandbox.safe_run(lambda x, y: x * y, 6, 7)
        assert result == 42

    def test_safe_run_exception(self, sandbox: Sandbox) -> None:
        """测试 safe_run 捕获异常。"""
        result: str = sandbox.safe_run(lambda: 1 / 0)
        assert isinstance(result, str)
        assert "error" in result.lower()


# ============================================================================
# Orchestrator 测试 (8 tests)
# ============================================================================


class TestOrchestrator:
    """StableAgentOrchestrator 的集成测试。"""

    def test_instantiation(self, orchestrator: StableAgentOrchestrator) -> None:
        """测试编排器实例化成功。"""
        assert orchestrator.event_bus is not None
        assert orchestrator.decision_engine is not None
        assert orchestrator.budget_manager is not None
        assert orchestrator.memory_router is not None
        assert orchestrator.evaluator is not None
        assert orchestrator.bad_case_manager is not None
        assert orchestrator.workflow_engine is not None
        assert orchestrator.rag_manager is not None
        assert orchestrator.knowledge_graph is not None
        assert orchestrator.version_control is not None
        assert orchestrator.tool_hub is not None
        assert orchestrator.sandbox is not None
        assert orchestrator.trace_storage is not None

    def test_process_task_returns_basic_structure(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试 process_task 返回基本结构。"""
        result: dict = orchestrator.process_task("修复登录页面的样式错位问题")
        assert "task_type" in result
        assert "workflow_state" in result
        assert "evaluation" in result
        assert "events_count" in result

    def test_process_task_returns_evaluation(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试 process_task 返回评估结果。"""
        result: dict = orchestrator.process_task("修复登录页面的样式错位问题")
        evaluation: EvaluationResult | None = result.get("evaluation")
        assert evaluation is not None
        assert isinstance(evaluation, EvaluationResult)
        assert 0.0 <= evaluation.overall_score <= 1.0

    def test_process_task_bug_fix_classification(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试 BUG_FIX 类任务分类正确。"""
        result: dict = orchestrator.process_task("修复登录崩溃问题")
        assert result["task_type"] == TaskType.BUG_FIX

    def test_process_task_arch_refactor_classification(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试 ARCH_REFACTOR 类任务分类正确。"""
        result: dict = orchestrator.process_task("重构用户认证模块，改用 JWT 方案")
        assert result["task_type"] == TaskType.ARCH_REFACTOR

    def test_get_summary_structure(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试 get_summary 返回完整结构。"""
        summary: dict = orchestrator.get_summary()
        assert "memory_count" in summary
        assert "event_count" in summary
        assert "bad_case_count" in summary
        assert "tool_count" in summary
        assert isinstance(summary["memory_count"], int)
        assert isinstance(summary["event_count"], int)
        assert isinstance(summary["bad_case_count"], int)
        assert isinstance(summary["tool_count"], int)

    def test_events_published_during_processing(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试处理任务时发布事件数量 > 0。"""
        orchestrator.process_task("修复登录页面的样式错位问题")
        assert len(orchestrator.event_bus._events) > 0

    def test_prefilled_memories_count(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试预填充记忆数量正确。"""
        # 预填充了 5 条 + 可能由 learn 阶段新增的
        assert len(orchestrator.memory_bank._items) >= 5

    def test_process_task_workflow_completes(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试工作流能正常完成。"""
        from stable_agent.models import WorkflowState

        result: dict = orchestrator.process_task("修复登录页面的样式错位问题")
        assert result["workflow_state"] == WorkflowState.COMPLETE

    def test_tools_registered_on_init(
        self, orchestrator: StableAgentOrchestrator
    ) -> None:
        """测试编排器初始化时注册了示例工具。"""
        tools: list[dict[str, str]] = orchestrator.tool_hub.list_tools()
        assert len(tools) >= 2
        tool_names: set[str] = {t["name"] for t in tools}
        assert "format_code" in tool_names
        assert "count_lines" in tool_names
