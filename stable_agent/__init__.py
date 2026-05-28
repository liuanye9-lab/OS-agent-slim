"""StableAgent OS — 稳定型 AI Agent 操作系统。

MCP 版本边界：V3/V4 已冻结（仅 bug fix），V5 gateway 是唯一活跃入口。
"""

MCP_VERSION: str = "5.6.0"
ACTIVE_MCP_ENTRY: str = "stable_agent.gateway"

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

__all__ = [
    # MCP 版本边界
    "MCP_VERSION",
    "ACTIVE_MCP_ENTRY",
    # 枚举
    "TaskType",
    "WorkflowState",
    "MemoryLayer",
    "MemoryLifecycle",
    "SpanType",
    "SpanStatus",
    "RiskLevel",
    "ApprovalStatus",
    # 核心数据类
    "MemoryItem",
    "EvaluationResult",
    "Workflow",
    "TaskInput",
    "TokenBudget",
    "Event",
    "SandboxResult",
    "BadCase",
    # V3 新增数据类
    "RunRecord",
    "TraceSpan",
    "ContextItem",
    "ContextPack",
    "ApprovalRequest",
    "EvalCase",
]
