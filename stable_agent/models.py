"""StableAgent OS 共享数据模型模块。

本模块是项目中所有模块的唯一数据模型来源，所有跨模块传递的对象
均在此定义。使用 @dataclass 确保数据不可变性，StrEnum 确保枚举值
的类型安全。

模块职责：
- 定义任务类型和工作流状态的枚举
- 定义记忆、评估、事件等核心数据结构
- 提供类型安全的工厂方法用于创建实例

约定：
- 所有时间戳使用 time.time() float 格式
- 所有字段必须有类型注解和默认值
"""

from __future__ import annotations

import time
import uuid
import warnings
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Optional


# ============================================================================
# 枚举定义 — 任务类型与工作流状态
# ============================================================================


class TaskType(StrEnum):
    """任务类型枚举。

    定义了 StableAgent OS 支持的所有任务类型，用于路由到不同的
    处理流程。使用 StrEnum 可直接序列化为 JSON 字符串值。
    """

    BUG_FIX = "bug_fix"  #: 修复代码缺陷
    UI_DESIGN = "ui_design"  #: 用户界面设计
    ARCH_REFACTOR = "arch_refactor"  #: 架构重构
    PROMPT_OPTIMIZATION = "prompt_optimization"  #: Prompt 优化
    EVAL_TASK = "eval_task"  #: 评估任务
    CODE_GENERATION = "code_generation"  #: 代码生成
    GENERAL_QA = "general_qa"  #: 通用问答


class WorkflowState(StrEnum):
    """工作流状态枚举。

    定义了从初始化到完成的全生命周期状态。状态机按以下顺序流转：
    INIT → RETRIEVE_MEMORY → RETRIEVE_KNOWLEDGE → PLAN → EXECUTE
    → EVALUATE → LEARN → COMPLETE
    V3 新增：DECIDE, BUDGET, BUILD_CONTEXT, APPROVAL_REQUIRED, OBSERVE, FAILED, CANCELLED
    """

    INIT = "init"  #: 初始化，解析输入
    RETRIEVE_MEMORY = "retrieve_memory"  #: 检索历史记忆（用户偏好、成功/失败案例）
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"  #: 检索外部知识库（RAG）
    PLAN = "plan"  #: 制定执行计划
    EXECUTE = "execute"  #: 执行计划步骤
    EVALUATE = "evaluate"  #: 评估执行结果
    LEARN = "learn"  #: 从结果中学习，更新记忆
    COMPLETE = "complete"  #: 完成，返回最终结果
    # V3 新增状态
    DECIDE = "decide"  #: 决策阶段
    BUDGET = "budget"  #: 预算分配
    BUILD_CONTEXT = "build_context"  #: 构建上下文包
    APPROVAL_REQUIRED = "approval_required"  #: 需要审批
    OBSERVE = "observe"  #: 观察/监控
    FAILED = "failed"  #: 执行失败
    CANCELLED = "cancelled"  #: 已取消


# ============================================================================
# V3 新增枚举定义
# ============================================================================


class MemoryLayer(StrEnum):
    """记忆分层枚举。

    控制记忆在不同层级中的存储与检索策略。
    """

    HOT = "hot"  #: 本轮任务必须用
    WARM = "warm"  #: 可能相关，检索后进入
    COLD = "cold"  #: 归档资料，默认不进入上下文


class MemoryLifecycle(StrEnum):
    """记忆生命周期枚举。

    管理记忆从创建到归档的完整生命周期。
    """

    CANDIDATE = "candidate"  #: 待确认写入
    ACTIVE = "active"  #: 当前有效
    OUTDATED = "outdated"  #: 已过时
    ARCHIVED = "archived"  #: 已归档


class SpanType(StrEnum):
    """追踪 Span 类型枚举。"""

    MEMORY_RETRIEVAL = "memory_retrieval"
    RAG_RETRIEVAL = "rag_retrieval"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    EVAL = "eval"
    PLAN = "plan"
    EXECUTE = "execute"
    LEARN = "learn"
    APPROVAL = "approval"
    # V4 Skill Optimizer span types
    SKILLOPT_EPOCH_STARTED = "skillopt.epoch_started"
    SKILLOPT_ROLLOUTS_COLLECTED = "skillopt.rollouts_collected"
    SKILLOPT_FAILURES_ANALYZED = "skillopt.failures_analyzed"
    SKILLOPT_SUCCESSES_ANALYZED = "skillopt.successes_analyzed"
    SKILLOPT_PATCH_MERGED = "skillopt.patch_merged"
    SKILLOPT_PATCH_RANKED = "skillopt.patch_ranked"
    SKILLOPT_CANDIDATE_CREATED = "skillopt.candidate_created"
    SKILLOPT_VALIDATION_PASSED = "skillopt.validation_passed"
    SKILLOPT_VALIDATION_FAILED = "skillopt.validation_failed"
    SKILLOPT_REJECTED_BUFFER_UPDATED = "skillopt.rejected_buffer_updated"
    SKILLOPT_SLOW_UPDATE_CREATED = "skillopt.slow_update_created"
    SKILLOPT_BEST_SKILL_EXPORTED = "skillopt.best_skill_exported"


class SpanStatus(StrEnum):
    """追踪 Span 状态枚举。"""

    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    """风险等级枚举。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FORBIDDEN = "forbidden"


class ApprovalStatus(StrEnum):
    """审批状态枚举。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ============================================================================
# 类型别名
# ============================================================================

EventImportance = Literal["debug", "normal", "important", "critical"]
"""事件重要性等级。

- debug: 调试级别，仅开发/调试时关注
- normal: 普通级别，常规事件
- important: 重要级别，需重点关注
- critical: 关键级别，影响决策或安全
"""


# ============================================================================
# 数据类定义 — 核心数据结构
# ============================================================================


@dataclass
class MemoryItem:
    """记忆条目。

    存储一次交互中提取的长期记忆信息，包括用户偏好、项目约束、
    成功案例和失败案例。由 Learn 阶段写入，由 RETRIEVE_MEMORY 阶段读取。

    Attributes:
        id: 唯一标识符，建议使用 UUID。
        content: 记忆的文本内容。
        type: 记忆类型，如 user_pref / project_constraint / success_case / bad_case。
        timestamp: 创建时间戳（UTC，time.time() 格式）。
        priority: 优先级，0.0（最低）~1.0（最高）。用于检索时的排序。
        source: 来源标识，如触发该记忆的工作流 ID。
        status: 状态，active 表示仍有效，outdated 表示已过时。
        layer: 记忆分层，hot/warm/cold。
        lifecycle: 生命周期状态，candidate/active/outdated/archived。
        valid_at: 生效时间（time.time() 格式），None 表示立即生效。
        invalid_at: 失效时间（time.time() 格式），None 表示永不过期。
        confidence: 置信度，0.0~1.0。
        last_used_at: 最后使用时间（time.time() 格式）。
        usage_count: 使用次数。
        tags: 标签列表。
    """

    id: str
    content: str
    type: str  # user_pref / project_constraint / success_case / bad_case
    timestamp: float = field(default_factory=time.time)
    priority: float = 0.5
    source: str = ""
    status: str = "active"  # active / outdated
    # V3 新增字段
    layer: str = "warm"  # hot/warm/cold
    lifecycle: str = "active"  # candidate/active/outdated/archived
    valid_at: Optional[float] = None
    invalid_at: Optional[float] = None
    confidence: float = 0.7
    last_used_at: Optional[float] = None
    usage_count: int = 0
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """验证字段合法性。"""
        # 优先级必须在 0~1 范围内
        if not 0.0 <= self.priority <= 1.0:
            raise ValueError(
                f"priority must be in [0.0, 1.0], got {self.priority}"
            )
        # status 只能是 active 或 outdated
        if self.status not in ("active", "outdated"):
            raise ValueError(
                f"status must be 'active' or 'outdated', got '{self.status}'"
            )
        # V3: 新增字段的宽松验证 —— 仅 warning，不抛异常
        if not 0.0 <= self.confidence <= 1.0:
            warnings.warn(
                f"confidence should be in [0.0, 1.0], got {self.confidence}"
            )
        valid_layers = {item.value for item in MemoryLayer}
        if self.layer not in valid_layers:
            warnings.warn(
                f"layer '{self.layer}' is not a known MemoryLayer value. "
                f"Known values: {valid_layers}"
            )
        valid_lifecycles = {item.value for item in MemoryLifecycle}
        if self.lifecycle not in valid_lifecycles:
            warnings.warn(
                f"lifecycle '{self.lifecycle}' is not a known MemoryLifecycle value. "
                f"Known values: {valid_lifecycles}"
            )


@dataclass
class EvaluationResult:
    """评估结果。

    记录一次任务执行后的多维评估指标。由 EVALUATE 阶段生成，
    用于 LEARN 阶段判断是否需要记录为 BadCase。

    Attributes:
        completion_rate: 任务完成率，0.0~1.0。
        context_hit_rate: 上下文命中率，检索到的有用记忆占比。
        token_efficiency: Token 效率，有效输出 token / 总消耗 token。
        hallucination_score: 幻觉评分，越低越好（0 表示无幻觉）。
        user_preference_score: 用户偏好匹配度，0.0~1.0。
        overall_score: 综合评分，各维度的加权平均。
        retrieval_quality: 检索质量评分，0.0~1.0。
        memory_quality: 记忆质量评分，0.0~1.0。
        tool_quality: 工具使用质量评分，0.0~1.0。
        format_quality: 输出格式质量评分，0.0~1.0。
        safety_score: 安全评分，0.0~1.0，默认 1.0（安全）。
        token_roi: Token 投资回报率，可超过 1.0。
        failure_reasons: 失败原因列表。
        improvement_rules: 改进规则列表。
    """

    completion_rate: float = 0.0
    context_hit_rate: float = 0.0
    token_efficiency: float = 0.0
    hallucination_score: float = 0.0
    user_preference_score: float = 0.0
    overall_score: float = 0.0
    # V3 新增字段
    retrieval_quality: float = 0.0
    memory_quality: float = 0.0
    tool_quality: float = 0.0
    format_quality: float = 0.0
    safety_score: float = 1.0
    token_roi: float = 0.0
    failure_reasons: list[str] = field(default_factory=list)
    improvement_rules: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """验证所有评分在合法范围内。"""
        # 需要验证 [0, 1] 范围的字段（不含 token_roi，它可超过 1.0）
        bounded_fields = (
            "completion_rate",
            "context_hit_rate",
            "token_efficiency",
            "hallucination_score",
            "user_preference_score",
            "overall_score",
            "retrieval_quality",
            "memory_quality",
            "tool_quality",
            "format_quality",
            "safety_score",
        )
        for name in bounded_fields:
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be in [0.0, 1.0], got {value}"
                )


@dataclass
class TokenBudget:
    """Token 预算。

    定义一次任务执行中各阶段的 token 分配上限。用于控制成本
    和防止上下文溢出。

    Attributes:
        memory_budget: 记忆检索阶段最大 token 数。
        rag_budget: 知识库检索阶段最大 token 数。
        prompt_budget: 构建 prompt 时的最大 token 数。
        output_budget: 模型输出的最大 token 数。
    """

    memory_budget: int = 2000
    rag_budget: int = 4000
    prompt_budget: int = 8000
    output_budget: int = 4096

    def __post_init__(self) -> None:
        """验证所有预算为正整数。"""
        for name in (
            "memory_budget",
            "rag_budget",
            "prompt_budget",
            "output_budget",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"{name} must be a positive integer, got {value}"
                )


@dataclass
class TaskInput:
    """任务输入。

    用户提交的原始输入以及系统推断的任务元信息。

    Attributes:
        raw_input: 用户的原始输入文本。
        task_type: 系统推断的任务类型，None 表示待推断。
        urgency: 紧急程度，1（低）~5（高），默认 1。
    """

    raw_input: str
    task_type: Optional[TaskType] = None
    urgency: int = 1

    def __post_init__(self) -> None:
        """验证 urgency 在 1~5 范围内。"""
        if not 1 <= self.urgency <= 5:
            raise ValueError(f"urgency must be in [1, 5], got {self.urgency}")


@dataclass
class Event:
    """事件。

    EventBus 中传递的消息单元。所有模块通过发布/订阅 Event 进行
    松耦合通信。

    Attributes:
        timestamp: 事件发生时间戳（time.time() 格式）。
        type: 事件类型标识字符串，如 "workflow.state_change"。
        payload: 事件携带的数据负载。
    """

    timestamp: float = field(default_factory=time.time)
    type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """工作流。

    一次任务处理的完整上下文，贯穿整个状态机生命周期。由各阶段
    按顺序读取和更新。

    Attributes:
        task_type: 任务类型。
        current_state: 当前工作流状态。
        context_pack: 上下文数据包，在各阶段间传递中间结果。
        history: 状态变更历史记录，每条记录包含 state 和 timestamp。
    """

    task_type: TaskType = TaskType.GENERAL_QA
    current_state: WorkflowState = WorkflowState.INIT
    context_pack: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition_to(self, new_state: WorkflowState) -> None:
        """执行状态迁移，并记录到 history。

        将当前状态切换到 new_state，并在 history 中追加一条记录，
        包含旧状态、新状态和时间戳。

        Args:
            new_state: 目标状态。

        Raises:
            ValueError: 如果 new_state 与当前状态相同。
        """
        if new_state == self.current_state:
            raise ValueError(
                f"Cannot transition to the same state: {new_state}"
            )
        old_state = self.current_state
        self.history.append({
            "from": old_state,
            "to": new_state,
            "timestamp": time.time(),
        })
        self.current_state = new_state


@dataclass
class SandboxResult:
    """沙箱执行结果。

    记录在隔离沙箱中执行代码的返回信息。

    Attributes:
        return_code: 进程退出码，0 表示成功。
        stdout: 标准输出内容。
        stderr: 标准错误输出内容。
    """

    return_code: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class BadCase:
    """负面案例。

    记录一次评估不合格的任务执行，用于后续的反思学习和 Prompt 优化。
    仅当 overall_score 低于阈值时创建。

    Attributes:
        task_type: 任务类型。
        input_context: 输入上下文（用户原始输入）。
        output: 模型/系统输出。
        evaluation: 评估结果详情。
        timestamp: 记录时间戳。
        failure_reason: 失败原因分析。
    """

    task_type: TaskType
    input_context: str
    output: str
    evaluation: EvaluationResult
    timestamp: float = field(default_factory=time.time)
    failure_reason: str = ""


# ============================================================================
# V3 新增数据类
# ============================================================================


@dataclass
class RunRecord:
    """运行记录。

    记录一次完整的任务执行运行信息，用于追踪、审计和成本分析。

    Attributes:
        run_id: 运行唯一标识（UUID）。
        user_task: 用户原始输入。
        task_type: 任务类型。
        status: 运行状态，init/running/completed/failed/cancelled。
        started_at: 开始时间戳（time.time() 格式）。
        ended_at: 结束时间戳，None 表示未结束。
        total_input_tokens: 总输入 token 数。
        total_output_tokens: 总输出 token 数。
        total_cost_estimate: 预估总成本（美元）。
        overall_score: 综合评分，None 表示未评估。
    """

    run_id: str
    user_task: str
    task_type: TaskType = TaskType.GENERAL_QA
    status: str = "init"
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_estimate: float = 0.0
    overall_score: Optional[float] = None

    def __post_init__(self) -> None:
        """验证 status 合法性。"""
        valid_statuses = {"init", "running", "completed", "failed", "cancelled"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"status must be one of {valid_statuses}, got '{self.status}'"
            )


@dataclass
class TraceSpan:
    """追踪 Span。

    记录一次运行中的单个操作追踪信息，支持嵌套形成调用树。

    Attributes:
        span_id: Span 唯一标识。
        run_id: 所属运行 ID。
        parent_span_id: 父 Span ID，None 表示根 Span。
        name: Span 名称。
        type: Span 类型。
        status: Span 状态。
        started_at: 开始时间戳。
        ended_at: 结束时间戳，None 表示仍在进行。
        latency_ms: 耗时（毫秒）。
        input_tokens: 输入 token 数。
        output_tokens: 输出 token 数。
        cost_estimate: 预估成本（美元）。
        payload: 附加数据负载。
        plain_text: 纯文本内容。
    """

    span_id: str
    run_id: str
    parent_span_id: Optional[str] = None
    name: str = ""
    type: str = "execute"  # SpanType.EXECUTE.value
    status: str = "started"  # SpanStatus.STARTED.value
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    latency_ms: Optional[int] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)
    plain_text: str = ""


@dataclass
class ContextItem:
    """上下文条目。

    表示上下文包中的一个条目，可以是记忆、RAG 文档、规则等。

    Attributes:
        id: 条目唯一标识。
        content: 条目文本内容。
        source_type: 来源类型（memory/rag/rule/user/system）。
        source_id: 来源 ID。
        priority: 优先级，0.0~1.0。
        relevance_score: 相关性评分，0.0~1.0。
        token_estimate: 预估 token 数。
        reason: 选择原因说明。
        risk: 风险等级，None 表示无风险。
        placement: 在上下文中的位置（top/middle/bottom）。
    """

    id: str
    content: str
    source_type: str = ""
    source_id: str = ""
    priority: float = 0.5
    relevance_score: float = 0.0
    token_estimate: int = 0
    reason: str = ""
    risk: Optional[str] = None
    placement: str = "middle"


@dataclass
class ContextPack:
    """上下文包。

    一次任务执行所需的完整上下文集合，由 BUILD_CONTEXT 阶段构建。

    Attributes:
        pack_id: 上下文包唯一标识。
        run_id: 所属运行 ID。
        task_input: 用户任务输入。
        task_type: 任务类型。
        items: 上下文条目列表。
        total_tokens: 总 token 数。
        budget_limit: 预算上限。
        cacheable_prefix: 可缓存的前缀内容。
        volatile_context: 易变上下文内容。
        critical_reminders: 关键提醒列表。
        compaction_report: 压缩报告。
    """

    pack_id: str = ""
    run_id: str = ""
    task_input: str = ""
    task_type: TaskType = TaskType.GENERAL_QA
    items: list[ContextItem] = field(default_factory=list)
    total_tokens: int = 0
    budget_limit: int = 0
    cacheable_prefix: str = ""
    volatile_context: str = ""
    critical_reminders: list[str] = field(default_factory=list)
    compaction_report: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    """审批请求。

    记录需要人工审批的操作请求。

    Attributes:
        request_id: 请求唯一标识。
        run_id: 所属运行 ID。
        action: 请求执行的动作。
        risk: 风险等级。
        reason: 请求原因。
        status: 审批状态。
        created_at: 创建时间戳。
        resolved_at: 解决时间戳，None 表示未解决。
        details: 请求详细信息。
    """

    request_id: str
    run_id: str
    action: str
    risk: str = "medium"  # RiskLevel.MEDIUM.value
    reason: str = ""
    status: str = "pending"  # ApprovalStatus.PENDING.value
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalCase:
    """评估用例。

    用于回归测试的评估用例，可手动创建或从 BadCase 自动生成。

    Attributes:
        case_id: 用例唯一标识。
        input_task: 输入任务描述。
        expected_behavior: 期望行为描述。
        must_include: 输出中必须包含的内容列表。
        must_not_include: 输出中禁止包含的内容列表。
        source: 来源（manual/auto）。
        created_from_bad_case_id: 如果从 BadCase 创建，记录来源 BadCase ID。
        task_type: 任务类型。
    """

    case_id: str
    input_task: str
    expected_behavior: str = ""
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    source: str = "manual"
    created_from_bad_case_id: Optional[str] = None
    task_type: TaskType = TaskType.GENERAL_QA


# ============================================================================
# V5 新增数据类
# ============================================================================


@dataclass
class StableAgentToolResult:
    """统一 MCP 工具返回结构。

    所有 V5 工具均返回此对象，确保工具调用结果的一致性和可追踪性。

    Attributes:
        ok: 工具执行是否成功。
        run_id: 所属运行 ID。
        tool_call_id: 工具调用 ID。
        tool_name: 工具完整名称（如 "stableagent.memory.retrieve"）。
        data: 结构化返回数据。
        plain_text: 人类可读的纯文本结果。
        plain_text_zh: 中文结果描述。
        plain_text_en: 英文结果描述。
        dashboard_url: Dashboard 链接。
        warnings: 执行过程中产生的警告信息列表。
        next_actions: 建议的后续操作列表。
        trace_url: 可选的 trace 查看 URL。
        is_error: 是否为错误返回。
    """

    ok: bool = False
    run_id: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    data: dict = field(default_factory=dict)
    plain_text: str = ""
    plain_text_zh: str = field(default="")
    plain_text_en: str = field(default="")
    dashboard_url: str = field(default="")
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    trace_url: str = ""
    is_error: bool = False


# ============================================================================
# V6 新增数据类
# ============================================================================


@dataclass
class UserFeedbackSignal:
    """用户反馈信号。

    记录用户对系统输出的实时反馈，用于调整 Agent 行为策略。

    Attributes:
        feedback_id: 反馈唯一标识（UUID）。
        run_id: 所属运行 ID。
        signal_type: 信号类型。
            - "aligned": 用户确认方向正确
            - "partial": 部分认可，有调整建议
            - "off_track": 方向偏离
            - "too_technical": 内容过于技术化
            - "too_generic": 内容过于泛化
            - "not_specific": 不够具体
            - "no_executable_plan": 缺少可执行计划
        label_zh: 中文标签/描述。
        label_en: 英文标签/描述。
        comment: 用户附加评论。
        timestamp: 反馈时间戳（time.time() 格式）。
        processed: 是否已被系统处理。
    """

    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    signal_type: str = ""
    label_zh: str = ""
    label_en: str = ""
    comment: str = ""
    timestamp: float = field(default_factory=time.time)
    processed: bool = False


@dataclass
class TraceEvent:
    """追踪事件。

    记录一次运行中的关键事件，用于可观测性和决策审计。

    Attributes:
        run_id: 所属运行 ID。
        span_id: 关联的 Span ID。
        event_type: 事件类型标识字符串。
        payload: 事件携带的数据负载。
        plain_text: 人类可读的事件描述。
        importance: 事件重要性等级。
        decision_trace: 决策追踪数据，None 表示非决策事件。
        timestamp: 事件发生时间戳（time.time() 格式）。
    """

    run_id: str = ""
    span_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    plain_text: str = ""
    importance: EventImportance = "normal"
    decision_trace: Optional[dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
