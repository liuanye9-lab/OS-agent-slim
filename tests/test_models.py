"""StableAgent OS 数据模型单元测试。

覆盖所有枚举值验证、数据类实例化、默认值和校验逻辑。
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from stable_agent.models import (
    ApprovalRequest,
    ApprovalStatus,
    BadCase,
    ContextItem,
    ContextPack,
    EvalCase,
    EvaluationResult,
    Event,
    MemoryItem,
    MemoryLayer,
    MemoryLifecycle,
    RiskLevel,
    RunRecord,
    SandboxResult,
    SpanStatus,
    SpanType,
    TaskInput,
    TaskType,
    TokenBudget,
    TraceSpan,
    Workflow,
    WorkflowState,
)


# ============================================================================
# 枚举测试
# ============================================================================


class TestTaskType:
    """TaskType 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有任务类型值都正确定义。"""
        assert TaskType.BUG_FIX == "bug_fix"
        assert TaskType.UI_DESIGN == "ui_design"
        assert TaskType.ARCH_REFACTOR == "arch_refactor"
        assert TaskType.PROMPT_OPTIMIZATION == "prompt_optimization"
        assert TaskType.EVAL_TASK == "eval_task"
        assert TaskType.CODE_GENERATION == "code_generation"
        assert TaskType.GENERAL_QA == "general_qa"

    def test_is_str_enum(self) -> None:
        """验证 TaskType 是 StrEnum，可直接用于字符串比较。"""
        assert isinstance(TaskType.BUG_FIX, str)
        assert TaskType.BUG_FIX == "bug_fix"

    def test_iterable(self) -> None:
        """验证可遍历所有枚举值。"""
        values = list(TaskType)
        assert len(values) == 7


class TestWorkflowState:
    """WorkflowState 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有工作流状态值都正确定义。"""
        assert WorkflowState.INIT == "init"
        assert WorkflowState.RETRIEVE_MEMORY == "retrieve_memory"
        assert WorkflowState.RETRIEVE_KNOWLEDGE == "retrieve_knowledge"
        assert WorkflowState.PLAN == "plan"
        assert WorkflowState.EXECUTE == "execute"
        assert WorkflowState.EVALUATE == "evaluate"
        assert WorkflowState.LEARN == "learn"
        assert WorkflowState.COMPLETE == "complete"

    def test_is_str_enum(self) -> None:
        """验证 WorkflowState 是 StrEnum。"""
        assert isinstance(WorkflowState.INIT, str)

    def test_iterable(self) -> None:
        """验证可遍历所有枚举值（含 V3 新增 7 个，共 15 个）。"""
        values = list(WorkflowState)
        assert len(values) == 15

    def test_init_is_default_start(self) -> None:
        """验证 INIT 是初始状态。"""
        assert WorkflowState.INIT == "init"


# ============================================================================
# 数据类实例化测试
# ============================================================================


class TestMemoryItem:
    """MemoryItem 数据类测试。"""

    def test_default_instantiation(self) -> None:
        """测试使用必填字段实例化。"""
        item = MemoryItem(
            id="mem-001",
            content="用户偏好使用 TypeScript",
            type="user_pref",
        )
        assert item.id == "mem-001"
        assert item.content == "用户偏好使用 TypeScript"
        assert item.type == "user_pref"
        assert 0.0 <= item.priority <= 1.0
        assert item.status == "active"
        assert isinstance(item.timestamp, float)

    def test_full_instantiation(self) -> None:
        """测试使用所有字段实例化。"""
        now = time.time()
        item = MemoryItem(
            id="mem-002",
            content="项目 A 要求 Python 3.11+",
            type="project_constraint",
            timestamp=now,
            priority=0.9,
            source="workflow-123",
            status="active",
        )
        assert item.id == "mem-002"
        assert item.priority == 0.9
        assert item.source == "workflow-123"
        assert item.status == "active"

    def test_priority_out_of_range_raises(self) -> None:
        """验证 priority 超出 [0, 1] 范围时抛出 ValueError。"""
        with pytest.raises(ValueError, match="priority"):
            MemoryItem(
                id="mem-003",
                content="test",
                type="user_pref",
                priority=1.5,
            )

    def test_invalid_status_raises(self) -> None:
        """验证 status 不是 active/outdated 时抛出 ValueError。"""
        with pytest.raises(ValueError, match="status"):
            MemoryItem(
                id="mem-004",
                content="test",
                type="user_pref",
                status="deleted",
            )


class TestEvaluationResult:
    """EvaluationResult 数据类测试。"""

    def test_default_instantiation(self) -> None:
        """测试默认实例化（全零评分）。"""
        result = EvaluationResult()
        assert result.completion_rate == 0.0
        assert result.overall_score == 0.0

    def test_full_instantiation(self) -> None:
        """测试使用所有字段实例化。"""
        result = EvaluationResult(
            completion_rate=0.95,
            context_hit_rate=0.88,
            token_efficiency=0.72,
            hallucination_score=0.05,
            user_preference_score=0.90,
            overall_score=0.85,
        )
        assert result.completion_rate == 0.95
        assert result.hallucination_score == 0.05

    def test_score_out_of_range_raises(self) -> None:
        """验证评分超出 [0, 1] 范围时抛出 ValueError。"""
        with pytest.raises(ValueError):
            EvaluationResult(completion_rate=1.5)

        with pytest.raises(ValueError):
            EvaluationResult(hallucination_score=-0.1)


class TestTokenBudget:
    """TokenBudget 数据类测试。"""

    def test_default_instantiation(self) -> None:
        """测试默认 budget 实例化。"""
        budget = TokenBudget()
        assert budget.memory_budget == 2000
        assert budget.rag_budget == 4000
        assert budget.prompt_budget == 8000
        assert budget.output_budget == 4096

    def test_custom_instantiation(self) -> None:
        """测试自定义 budget。"""
        budget = TokenBudget(
            memory_budget=1000,
            rag_budget=2000,
            prompt_budget=4000,
            output_budget=2048,
        )
        assert budget.memory_budget == 1000

    def test_non_positive_raises(self) -> None:
        """验证非正整数 budget 抛出 ValueError。"""
        with pytest.raises(ValueError):
            TokenBudget(memory_budget=0)

        with pytest.raises(ValueError):
            TokenBudget(rag_budget=-1)


class TestTaskInput:
    """TaskInput 数据类测试。"""

    def test_minimal_instantiation(self) -> None:
        """测试最小字段实例化（仅 raw_input）。"""
        inp = TaskInput(raw_input="请修复登录页面的 CSS 错位问题")
        assert inp.raw_input == "请修复登录页面的 CSS 错位问题"
        assert inp.task_type is None
        assert inp.urgency == 1

    def test_with_task_type(self) -> None:
        """测试指定 task_type 的实例化。"""
        inp = TaskInput(
            raw_input="修复 bug",
            task_type=TaskType.BUG_FIX,
            urgency=3,
        )
        assert inp.task_type == TaskType.BUG_FIX
        assert inp.urgency == 3

    def test_urgency_out_of_range_raises(self) -> None:
        """验证 urgency 超出 1~5 时抛出 ValueError。"""
        with pytest.raises(ValueError, match="urgency"):
            TaskInput(raw_input="test", urgency=0)

        with pytest.raises(ValueError, match="urgency"):
            TaskInput(raw_input="test", urgency=6)


class TestEvent:
    """Event 数据类测试。"""

    def test_default_instantiation(self) -> None:
        """测试默认事件实例化。"""
        event = Event()
        assert isinstance(event.timestamp, float)
        assert event.type == ""
        assert event.payload == {}

    def test_full_instantiation(self) -> None:
        """测试带负载的事件实例化。"""
        now = time.time()
        event = Event(
            timestamp=now,
            type="workflow.state_change",
            payload={"from": "init", "to": "plan"},
        )
        assert event.timestamp == now
        assert event.type == "workflow.state_change"
        assert event.payload["from"] == "init"


class TestWorkflow:
    """Workflow 数据类测试。"""

    def test_default_instantiation(self) -> None:
        """测试默认工作流实例化。"""
        wf = Workflow()
        assert wf.task_type == TaskType.GENERAL_QA
        assert wf.current_state == WorkflowState.INIT
        assert wf.context_pack == {}
        assert wf.history == []

    def test_transition_to(self) -> None:
        """测试状态迁移功能。"""
        wf = Workflow()
        assert wf.current_state == WorkflowState.INIT

        wf.transition_to(WorkflowState.RETRIEVE_MEMORY)
        assert wf.current_state == WorkflowState.RETRIEVE_MEMORY
        assert len(wf.history) == 1
        assert wf.history[0]["from"] == WorkflowState.INIT
        assert wf.history[0]["to"] == WorkflowState.RETRIEVE_MEMORY
        assert "timestamp" in wf.history[0]

    def test_transition_to_same_state_raises(self) -> None:
        """验证迁移到相同状态时抛出 ValueError。"""
        wf = Workflow()
        with pytest.raises(ValueError, match="same state"):
            wf.transition_to(WorkflowState.INIT)

    def test_full_lifecycle(self) -> None:
        """测试完整的生命周期状态迁移。"""
        wf = Workflow()
        states = [
            WorkflowState.RETRIEVE_MEMORY,
            WorkflowState.RETRIEVE_KNOWLEDGE,
            WorkflowState.PLAN,
            WorkflowState.EXECUTE,
            WorkflowState.EVALUATE,
            WorkflowState.LEARN,
            WorkflowState.COMPLETE,
        ]
        for state in states:
            wf.transition_to(state)
        assert wf.current_state == WorkflowState.COMPLETE
        assert len(wf.history) == 7


class TestSandboxResult:
    """SandboxResult 数据类测试。"""

    def test_default_instantiation(self) -> None:
        """测试默认实例化（成功执行）。"""
        result = SandboxResult()
        assert result.return_code == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_error_result(self) -> None:
        """测试错误执行结果。"""
        result = SandboxResult(
            return_code=1,
            stdout="processing...",
            stderr="ModuleNotFoundError: No module named 'foo'",
        )
        assert result.return_code == 1
        assert "ModuleNotFoundError" in result.stderr


class TestBadCase:
    """BadCase 数据类测试。"""

    def test_full_instantiation(self) -> None:
        """测试完整的 BadCase 实例化。"""
        evaluation = EvaluationResult(
            completion_rate=0.3,
            overall_score=0.25,
        )
        bc = BadCase(
            task_type=TaskType.BUG_FIX,
            input_context="修复登录页面 500 错误",
            output="未找到问题，重试后仍然失败",
            evaluation=evaluation,
            failure_reason="上下文不足，无法定位 bug 根因",
        )
        assert bc.task_type == TaskType.BUG_FIX
        assert bc.evaluation.overall_score == 0.25
        assert isinstance(bc.timestamp, float)


# ============================================================================
# __init__.py 导入测试 — 验证包导出完整性
# ============================================================================


class TestPackageExports:
    """验证 stable_agent 包的公共导出。"""

    def test_import_task_type(self) -> None:
        """验证可从包级别导入 TaskType。"""
        from stable_agent import TaskType as TT
        assert TT.BUG_FIX == "bug_fix"

    def test_import_workflow_state(self) -> None:
        """验证可从包级别导入 WorkflowState。"""
        from stable_agent import WorkflowState as WS
        assert WS.INIT == "init"

    def test_import_memory_item(self) -> None:
        """验证可从包级别导入 MemoryItem。"""
        from stable_agent import MemoryItem
        item = MemoryItem(id="t1", content="test", type="user_pref")
        assert item.id == "t1"

    def test_import_evaluation_result(self) -> None:
        """验证可从包级别导入 EvaluationResult。"""
        from stable_agent import EvaluationResult
        assert EvaluationResult().overall_score == 0.0

    def test_import_workflow(self) -> None:
        """验证可从包级别导入 Workflow。"""
        from stable_agent import Workflow
        assert Workflow().current_state == WorkflowState.INIT

    def test_import_event(self) -> None:
        """验证可从包级别导入 Event。"""
        from stable_agent import Event
        assert isinstance(Event().timestamp, float)

    def test_import_sandbox_result(self) -> None:
        """验证可从包级别导入 SandboxResult。"""
        from stable_agent import SandboxResult
        assert SandboxResult().return_code == 0

    def test_import_bad_case(self) -> None:
        """验证可从包级别导入 BadCase。"""
        from stable_agent import BadCase
        assert BadCase is not None


# ============================================================================
# V3 新增：枚举测试
# ============================================================================


class TestMemoryLayer:
    """MemoryLayer 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有分层值都正确定义。"""
        assert MemoryLayer.HOT == "hot"
        assert MemoryLayer.WARM == "warm"
        assert MemoryLayer.COLD == "cold"

    def test_is_str_enum(self) -> None:
        """验证是 StrEnum。"""
        assert isinstance(MemoryLayer.HOT, str)


class TestMemoryLifecycle:
    """MemoryLifecycle 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有生命周期值都正确定义。"""
        assert MemoryLifecycle.CANDIDATE == "candidate"
        assert MemoryLifecycle.ACTIVE == "active"
        assert MemoryLifecycle.OUTDATED == "outdated"
        assert MemoryLifecycle.ARCHIVED == "archived"

    def test_is_str_enum(self) -> None:
        """验证是 StrEnum。"""
        assert isinstance(MemoryLifecycle.ACTIVE, str)


class TestSpanType:
    """SpanType 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有 SpanType 值都正确定义。"""
        assert SpanType.MEMORY_RETRIEVAL == "memory_retrieval"
        assert SpanType.RAG_RETRIEVAL == "rag_retrieval"
        assert SpanType.LLM_CALL == "llm_call"
        assert SpanType.TOOL_CALL == "tool_call"
        assert SpanType.EVAL == "eval"
        assert SpanType.PLAN == "plan"
        assert SpanType.EXECUTE == "execute"
        assert SpanType.LEARN == "learn"
        assert SpanType.APPROVAL == "approval"

    def test_is_str_enum(self) -> None:
        """验证是 StrEnum。"""
        assert isinstance(SpanType.LLM_CALL, str)


class TestSpanStatus:
    """SpanStatus 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有 SpanStatus 值都正确定义。"""
        assert SpanStatus.STARTED == "started"
        assert SpanStatus.SUCCESS == "success"
        assert SpanStatus.FAILED == "failed"
        assert SpanStatus.CANCELLED == "cancelled"

    def test_is_str_enum(self) -> None:
        """验证是 StrEnum。"""
        assert isinstance(SpanStatus.STARTED, str)


class TestRiskLevel:
    """RiskLevel 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有风险等级值都正确定义。"""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.FORBIDDEN == "forbidden"

    def test_is_str_enum(self) -> None:
        """验证是 StrEnum。"""
        assert isinstance(RiskLevel.MEDIUM, str)


class TestApprovalStatus:
    """ApprovalStatus 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """验证所有审批状态值都正确定义。"""
        assert ApprovalStatus.PENDING == "pending"
        assert ApprovalStatus.APPROVED == "approved"
        assert ApprovalStatus.REJECTED == "rejected"

    def test_is_str_enum(self) -> None:
        """验证是 StrEnum。"""
        assert isinstance(ApprovalStatus.PENDING, str)


# ============================================================================
# V3 新增：WorkflowState 扩展测试
# ============================================================================


class TestWorkflowStateExtended:
    """WorkflowState V3 扩展测试。"""

    def test_new_states_exist(self) -> None:
        """验证 V3 新增状态都正确定义。"""
        assert WorkflowState.DECIDE == "decide"
        assert WorkflowState.BUDGET == "budget"
        assert WorkflowState.BUILD_CONTEXT == "build_context"
        assert WorkflowState.APPROVAL_REQUIRED == "approval_required"
        assert WorkflowState.OBSERVE == "observe"
        assert WorkflowState.FAILED == "failed"
        assert WorkflowState.CANCELLED == "cancelled"

    def test_new_states_work_with_transition(self) -> None:
        """验证新状态可用于状态迁移。"""
        wf = Workflow()
        wf.transition_to(WorkflowState.DECIDE)
        assert wf.current_state == WorkflowState.DECIDE
        wf.transition_to(WorkflowState.BUDGET)
        assert wf.current_state == WorkflowState.BUDGET
        wf.transition_to(WorkflowState.FAILED)
        assert wf.current_state == WorkflowState.FAILED


# ============================================================================
# V3 新增：MemoryItem 扩展字段测试
# ============================================================================


class TestMemoryItemExtended:
    """MemoryItem V3 扩展字段测试。"""

    def test_extended_fields_defaults(self) -> None:
        """测试 V3 新增字段的默认值。"""
        item = MemoryItem(id="mem-ext", content="test", type="user_pref")
        assert item.layer == "warm"
        assert item.lifecycle == "active"
        assert item.confidence == 0.7
        assert item.valid_at is None
        assert item.invalid_at is None
        assert item.last_used_at is None
        assert item.usage_count == 0
        assert item.tags == []

    def test_layer_default_is_warm(self) -> None:
        """测试 layer 默认值为 'warm'。"""
        item = MemoryItem(id="mem-layer", content="test", type="user_pref")
        assert item.layer == MemoryLayer.WARM.value

    def test_confidence_warns_out_of_range(self) -> None:
        """测试 confidence 超出范围时发出 warning（不抛异常）。"""
        with pytest.warns(UserWarning, match="confidence"):
            MemoryItem(
                id="mem-conf",
                content="test",
                type="user_pref",
                confidence=1.5,
            )

    def test_layer_warns_unknown_value(self) -> None:
        """测试 layer 为未知值时发出 warning。"""
        with pytest.warns(UserWarning, match="layer"):
            MemoryItem(
                id="mem-layer-bad",
                content="test",
                type="user_pref",
                layer="frozen",
            )

    def test_lifecycle_warns_unknown_value(self) -> None:
        """测试 lifecycle 为未知值时发出 warning。"""
        with pytest.warns(UserWarning, match="lifecycle"):
            MemoryItem(
                id="mem-life-bad",
                content="test",
                type="user_pref",
                lifecycle="expired",
            )

    def test_custom_tags(self) -> None:
        """测试自定义标签。"""
        item = MemoryItem(
            id="mem-tags",
            content="test",
            type="user_pref",
            tags=["python", "fastapi", "v3"],
        )
        assert item.tags == ["python", "fastapi", "v3"]
        assert len(item.tags) == 3


# ============================================================================
# V3 新增：EvaluationResult 扩展字段测试
# ============================================================================


class TestEvaluationResultExtended:
    """EvaluationResult V3 扩展字段测试。"""

    def test_extended_fields_defaults(self) -> None:
        """测试 V3 新增字段的默认值。"""
        result = EvaluationResult()
        assert result.retrieval_quality == 0.0
        assert result.memory_quality == 0.0
        assert result.tool_quality == 0.0
        assert result.format_quality == 0.0
        assert result.safety_score == 1.0
        assert result.token_roi == 0.0
        assert result.failure_reasons == []
        assert result.improvement_rules == []

    def test_token_roi_can_exceed_one(self) -> None:
        """测试 token_roi 可以超过 1.0。"""
        result = EvaluationResult(token_roi=2.5)
        assert result.token_roi == 2.5

    def test_safety_score_default_one(self) -> None:
        """测试 safety_score 默认 1.0（安全）。"""
        result = EvaluationResult()
        assert result.safety_score == 1.0

    def test_new_quality_fields_in_range(self) -> None:
        """测试新质量字段在 [0, 1] 范围内。"""
        result = EvaluationResult(
            retrieval_quality=0.9,
            memory_quality=0.8,
            tool_quality=0.7,
            format_quality=0.6,
        )
        assert result.retrieval_quality == 0.9
        assert result.memory_quality == 0.8
        assert result.tool_quality == 0.7
        assert result.format_quality == 0.6

    def test_new_quality_fields_out_of_range_raises(self) -> None:
        """测试新质量字段超出 [0, 1] 范围抛出 ValueError。"""
        with pytest.raises(ValueError):
            EvaluationResult(retrieval_quality=1.5)
        with pytest.raises(ValueError):
            EvaluationResult(safety_score=-0.1)


# ============================================================================
# V3 新增：数据类实例化测试
# ============================================================================


class TestRunRecord:
    """RunRecord 数据类测试。"""

    def test_creation(self) -> None:
        """测试 RunRecord 创建。"""
        record = RunRecord(
            run_id="run-001",
            user_task="修复登录页面崩溃",
        )
        assert record.run_id == "run-001"
        assert record.user_task == "修复登录页面崩溃"
        assert record.task_type == TaskType.GENERAL_QA
        assert record.status == "init"
        assert record.total_input_tokens == 0
        assert record.total_output_tokens == 0
        assert record.total_cost_estimate == 0.0
        assert record.overall_score is None
        assert record.ended_at is None
        assert isinstance(record.started_at, float)

    def test_full_creation(self) -> None:
        """测试 RunRecord 完整创建。"""
        now = time.time()
        record = RunRecord(
            run_id="run-full",
            user_task="重构架构",
            task_type=TaskType.ARCH_REFACTOR,
            status="running",
            started_at=now,
            total_input_tokens=1500,
            total_output_tokens=800,
            total_cost_estimate=0.015,
            overall_score=0.92,
        )
        assert record.task_type == TaskType.ARCH_REFACTOR
        assert record.status == "running"
        assert record.total_input_tokens == 1500
        assert record.overall_score == 0.92

    def test_invalid_status_raises(self) -> None:
        """测试无效 status 抛出 ValueError。"""
        with pytest.raises(ValueError, match="status"):
            RunRecord(run_id="bad", user_task="test", status="unknown")


class TestTraceSpan:
    """TraceSpan 数据类测试。"""

    def test_creation(self) -> None:
        """测试 TraceSpan 创建。"""
        span = TraceSpan(
            span_id="span-001",
            run_id="run-001",
        )
        assert span.span_id == "span-001"
        assert span.run_id == "run-001"
        assert span.parent_span_id is None
        assert span.type == "execute"
        assert span.status == "started"
        assert span.input_tokens == 0
        assert span.output_tokens == 0
        assert span.cost_estimate == 0.0
        assert span.payload == {}
        assert span.plain_text == ""
        assert isinstance(span.started_at, float)
        assert span.ended_at is None

    def test_nested_span(self) -> None:
        """测试嵌套 Span 创建。"""
        parent = TraceSpan(span_id="parent", run_id="run-001")
        child = TraceSpan(
            span_id="child",
            run_id="run-001",
            parent_span_id="parent",
            name="LLM Call",
            type="llm_call",
        )
        assert child.parent_span_id == "parent"
        assert child.name == "LLM Call"
        assert child.type == "llm_call"

    def test_full_creation(self) -> None:
        """测试 TraceSpan 完整创建。"""
        span = TraceSpan(
            span_id="span-full",
            run_id="run-001",
            name="Tool Execution",
            type="tool_call",
            status="success",
            input_tokens=200,
            output_tokens=150,
            cost_estimate=0.002,
            payload={"tool": "format_code"},
            plain_text="Code formatted successfully",
        )
        assert span.status == "success"
        assert span.payload["tool"] == "format_code"
        assert span.plain_text == "Code formatted successfully"


class TestContextItem:
    """ContextItem 数据类测试。"""

    def test_creation(self) -> None:
        """测试 ContextItem 创建。"""
        item = ContextItem(
            id="ctx-001",
            content="用户偏好使用 TypeScript",
        )
        assert item.id == "ctx-001"
        assert item.content == "用户偏好使用 TypeScript"
        assert item.source_type == ""
        assert item.source_id == ""
        assert item.priority == 0.5
        assert item.relevance_score == 0.0
        assert item.token_estimate == 0
        assert item.reason == ""
        assert item.risk is None
        assert item.placement == "middle"

    def test_full_creation(self) -> None:
        """测试 ContextItem 完整创建。"""
        item = ContextItem(
            id="ctx-full",
            content="Memory: null pointer fix",
            source_type="memory",
            source_id="mem-001",
            priority=0.9,
            relevance_score=0.85,
            token_estimate=50,
            reason="High relevance to current bug",
            risk="low",
            placement="top",
        )
        assert item.source_type == "memory"
        assert item.risk == "low"
        assert item.placement == "top"


class TestContextPack:
    """ContextPack 数据类测试。"""

    def test_creation(self) -> None:
        """测试 ContextPack 创建。"""
        pack = ContextPack()
        assert pack.pack_id == ""
        assert pack.run_id == ""
        assert pack.task_input == ""
        assert pack.task_type == TaskType.GENERAL_QA
        assert pack.items == []
        assert pack.total_tokens == 0
        assert pack.budget_limit == 0
        assert pack.cacheable_prefix == ""
        assert pack.volatile_context == ""
        assert pack.critical_reminders == []
        assert pack.compaction_report == {}

    def test_with_items(self) -> None:
        """测试带条目的 ContextPack。"""
        items = [
            ContextItem(id="i1", content="Item 1"),
            ContextItem(id="i2", content="Item 2"),
        ]
        pack = ContextPack(
            pack_id="pack-001",
            run_id="run-001",
            task_input="Fix bug",
            items=items,
            total_tokens=100,
            budget_limit=500,
            critical_reminders=["Check security", "Run tests"],
        )
        assert len(pack.items) == 2
        assert pack.total_tokens == 100
        assert len(pack.critical_reminders) == 2


class TestApprovalRequest:
    """ApprovalRequest 数据类测试。"""

    def test_creation(self) -> None:
        """测试 ApprovalRequest 创建。"""
        req = ApprovalRequest(
            request_id="req-001",
            run_id="run-001",
            action="delete_production_data",
        )
        assert req.request_id == "req-001"
        assert req.run_id == "run-001"
        assert req.action == "delete_production_data"
        assert req.risk == "medium"
        assert req.reason == ""
        assert req.status == "pending"
        assert isinstance(req.created_at, float)
        assert req.resolved_at is None
        assert req.details == {}

    def test_full_creation(self) -> None:
        """测试 ApprovalRequest 完整创建。"""
        now = time.time()
        req = ApprovalRequest(
            request_id="req-full",
            run_id="run-001",
            action="modify_config",
            risk="high",
            reason="Configuration change requires review",
            status="pending",
            created_at=now,
            details={"config_key": "db_url", "old_value": "localhost", "new_value": "prod.example.com"},
        )
        assert req.risk == "high"
        assert req.reason == "Configuration change requires review"
        assert req.details["config_key"] == "db_url"


class TestEvalCase:
    """EvalCase 数据类测试。"""

    def test_creation(self) -> None:
        """测试 EvalCase 创建。"""
        case = EvalCase(
            case_id="case-001",
            input_task="修复登录页面崩溃",
        )
        assert case.case_id == "case-001"
        assert case.input_task == "修复登录页面崩溃"
        assert case.expected_behavior == ""
        assert case.must_include == []
        assert case.must_not_include == []
        assert case.source == "manual"
        assert case.created_from_bad_case_id is None
        assert case.task_type == TaskType.GENERAL_QA

    def test_from_bad_case(self) -> None:
        """测试从 BadCase 创建的 EvalCase。"""
        case = EvalCase(
            case_id="case-bc",
            input_task="修复 NPE",
            expected_behavior="Should handle null gracefully",
            must_include=["Optional", "null check"],
            must_not_include=["NullPointerException"],
            source="auto",
            created_from_bad_case_id="bad-001",
            task_type=TaskType.BUG_FIX,
        )
        assert case.source == "auto"
        assert case.created_from_bad_case_id == "bad-001"
        assert "Optional" in case.must_include
        assert "NullPointerException" in case.must_not_include


# ============================================================================
# V3 新增：包导出扩展测试
# ============================================================================


class TestInitExportsExtended:
    """验证 V3 新增类型的包导出完整性。"""

    def test_import_memory_layer(self) -> None:
        """验证可从包级别导入 MemoryLayer。"""
        from stable_agent import MemoryLayer as ML
        assert ML.HOT == "hot"

    def test_import_risk_level(self) -> None:
        """验证可从包级别导入 RiskLevel。"""
        from stable_agent import RiskLevel as RL
        assert RL.HIGH == "high"

    def test_import_run_record(self) -> None:
        """验证可从包级别导入 RunRecord。"""
        from stable_agent import RunRecord
        record = RunRecord(run_id="r1", user_task="test")
        assert record.run_id == "r1"

    def test_import_trace_span(self) -> None:
        """验证可从包级别导入 TraceSpan。"""
        from stable_agent import TraceSpan
        span = TraceSpan(span_id="s1", run_id="r1")
        assert span.span_id == "s1"

    def test_import_context_item(self) -> None:
        """验证可从包级别导入 ContextItem。"""
        from stable_agent import ContextItem
        item = ContextItem(id="c1", content="test")
        assert item.id == "c1"

    def test_import_context_pack(self) -> None:
        """验证可从包级别导入 ContextPack。"""
        from stable_agent import ContextPack
        assert ContextPack is not None

    def test_import_approval_request(self) -> None:
        """验证可从包级别导入 ApprovalRequest。"""
        from stable_agent import ApprovalRequest
        req = ApprovalRequest(request_id="a1", run_id="r1", action="test")
        assert req.request_id == "a1"

    def test_import_eval_case(self) -> None:
        """验证可从包级别导入 EvalCase。"""
        from stable_agent import EvalCase
        case = EvalCase(case_id="e1", input_task="test")
        assert case.case_id == "e1"
