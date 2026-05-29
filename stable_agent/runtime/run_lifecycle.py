"""Unified Run Lifecycle — 生产级 Agent 任务生命周期管理。

定义 20 个标准阶段，统一 Dashboard / MCP / EventStream 的状态源。
每个阶段带有进度百分比、中英文标签、头像状态、解释和下一步指引。

Usage:
    from stable_agent.runtime.run_lifecycle import RunStage, get_stage_meta

    meta = get_stage_meta(RunStage.PLANNING)
    ctx.progress_pct = meta.progress_pct
    ctx.status_text_zh = meta.status_text_zh
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RunStage(StrEnum):
    """Agent 任务的标准执行阶段。"""

    CREATED = "created"
    RECEIVED = "received"
    INTENT_PARSING = "intent_parsing"
    CONTEXT_BUDGETING = "context_budgeting"
    MEMORY_RETRIEVING = "memory_retrieving"
    RAG_RETRIEVING = "rag_retrieving"
    CONTEXT_BUILDING = "context_building"
    PLANNING = "planning"
    ACTING = "acting"
    OBSERVING = "observing"
    EVALUATING = "evaluating"
    FAILURE_ATTRIBUTION = "failure_attribution"
    REGRESSION_GENERATION = "regression_generation"
    SKILL_PATCH_PROPOSAL = "skill_patch_proposal"
    VALIDATION = "validation"
    HUMAN_REVIEW = "human_review"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RunStageMeta:
    """阶段的完整元信息。"""

    stage: RunStage
    progress_pct: int
    status_text_zh: str
    status_text_en: str
    avatar_state: str
    default_why_zh: str
    default_next_step_zh: str


RUN_STAGE_META: dict[RunStage, RunStageMeta] = {
    RunStage.CREATED: RunStageMeta(
        RunStage.CREATED, 0, "已创建", "Created", "idle",
        "任务刚创建。", "等待接收任务。",
    ),
    RunStage.RECEIVED: RunStageMeta(
        RunStage.RECEIVED, 5, "接收任务", "Received", "listening",
        "系统收到新的 Agent 任务。", "下一步理解任务意图。",
    ),
    RunStage.INTENT_PARSING: RunStageMeta(
        RunStage.INTENT_PARSING, 10, "理解需求", "Parsing intent", "thinking",
        "需要先判断用户真正要解决什么问题。", "下一步计算上下文预算。",
    ),
    RunStage.CONTEXT_BUDGETING: RunStageMeta(
        RunStage.CONTEXT_BUDGETING, 20, "计算预算", "Budgeting context", "calculating",
        "避免把无关信息塞进上下文，浪费 token。", "下一步检索相关记忆。",
    ),
    RunStage.MEMORY_RETRIEVING: RunStageMeta(
        RunStage.MEMORY_RETRIEVING, 30, "查找记忆", "Retrieving memory", "reading_notes",
        "需要参考历史经验，避免从零开始。", "下一步检索项目资料。",
    ),
    RunStage.RAG_RETRIEVING: RunStageMeta(
        RunStage.RAG_RETRIEVING, 40, "查找资料", "Retrieving knowledge", "searching_books",
        "需要从项目资料里找当前任务相关信息。", "下一步构建上下文包。",
    ),
    RunStage.CONTEXT_BUILDING: RunStageMeta(
        RunStage.CONTEXT_BUILDING, 50, "整理上下文", "Building context", "organizing",
        "把有用信息压缩成模型能用的上下文。", "下一步规划执行步骤。",
    ),
    RunStage.PLANNING: RunStageMeta(
        RunStage.PLANNING, 60, "规划步骤", "Planning", "planning",
        "复杂任务需要先拆步骤，避免跑偏。", "下一步开始执行。",
    ),
    RunStage.ACTING: RunStageMeta(
        RunStage.ACTING, 70, "执行任务", "Acting", "tooling",
        "现在开始调用工具或执行任务。", "下一步观察执行结果。",
    ),
    RunStage.OBSERVING: RunStageMeta(
        RunStage.OBSERVING, 78, "观察结果", "Observing", "watching",
        "需要看工具返回是否符合预期。", "下一步评估输出质量。",
    ),
    RunStage.EVALUATING: RunStageMeta(
        RunStage.EVALUATING, 85, "评估结果", "Evaluating", "grading",
        "需要判断任务是否完成、是否跑偏。", "下一步做失败归因。",
    ),
    RunStage.FAILURE_ATTRIBUTION: RunStageMeta(
        RunStage.FAILURE_ATTRIBUTION, 90, "分析失败", "Attributing failure", "diagnosing",
        "如果结果不好，需要知道错在哪里。", "下一步生成回归用例。",
    ),
    RunStage.REGRESSION_GENERATION: RunStageMeta(
        RunStage.REGRESSION_GENERATION, 93, "生成错题", "Generating regression", "writing_case",
        "失败案例要变成以后可重复测试的用例。", "下一步提出 skill patch。",
    ),
    RunStage.SKILL_PATCH_PROPOSAL: RunStageMeta(
        RunStage.SKILL_PATCH_PROPOSAL, 95, "提出改法", "Proposing skill patch", "learning",
        "把稳定经验变成可审查的 skill 修改建议。", "下一步进入验证门。",
    ),
    RunStage.VALIDATION: RunStageMeta(
        RunStage.VALIDATION, 97, "验证改法", "Validating", "grading",
        "新规则必须证明比旧规则更好。", "下一步进入人工审核。",
    ),
    RunStage.HUMAN_REVIEW: RunStageMeta(
        RunStage.HUMAN_REVIEW, 98, "等待审核", "Human review", "waiting_approval",
        "高影响修改必须由人确认。", "下一步决定是否导出。",
    ),
    RunStage.EXPORTING: RunStageMeta(
        RunStage.EXPORTING, 99, "导出规则", "Exporting", "archiving",
        "审核通过后才能导出 best_skill.md。", "下一步完成任务。",
    ),
    RunStage.COMPLETED: RunStageMeta(
        RunStage.COMPLETED, 100, "完成任务", "Completed", "done",
        "任务已经完成。", "可以查看总结。",
    ),
    RunStage.FAILED: RunStageMeta(
        RunStage.FAILED, -1, "任务失败", "Failed", "failed",
        "任务失败，需要记录原因。", "请查看错误详情。",
    ),
    RunStage.CANCELLED: RunStageMeta(
        RunStage.CANCELLED, -1, "已取消", "Cancelled", "failed",
        "任务被取消。", "无需继续执行。",
    ),
}


def get_stage_meta(stage: str | RunStage) -> RunStageMeta:
    """根据 stage 名称获取完整元信息。

    Args:
        stage: 阶段名称或 RunStage 枚举值。

    Returns:
        RunStageMeta: 阶段元信息。如 stage 不存在则返回 CREATED。
    """
    try:
        s = RunStage(stage) if isinstance(stage, str) else stage
    except ValueError:
        return RUN_STAGE_META[RunStage.CREATED]
    return RUN_STAGE_META.get(s, RUN_STAGE_META[RunStage.CREATED])


# Backward compat: 导出为字典格式，兼容旧 RunLifecycle
STAGE_PROGRESS: dict[str, int] = {
    s.value: m.progress_pct for s, m in RUN_STAGE_META.items()
}
STAGE_LABEL_ZH: dict[str, str] = {
    s.value: m.status_text_zh for s, m in RUN_STAGE_META.items()
}
STAGE_AVATAR: dict[str, str] = {
    s.value: m.avatar_state for s, m in RUN_STAGE_META.items()
}
