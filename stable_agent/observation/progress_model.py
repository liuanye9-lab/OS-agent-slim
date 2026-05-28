"""progress_model — 后端统一进度模型。

V6.5: 每个 OS Agent 任务有 11 个标准化阶段，每个阶段有固定百分比、
语义场景、中英文状态文本。进度只能由后端生成，前端不可猜测。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProgressStage:
    """一个标准化的任务进度阶段。"""
    key: str
    label_zh: str
    label_en: str
    pct: int
    avatar_state: str
    avatar_scene: str
    status_text_zh: str
    status_text_en: str


PROGRESS_STAGES: list[ProgressStage] = [
    ProgressStage("mcp_received",    "接收任务",   "Task received",         5,  "listening",       "desk",           "正在接收任务",     "Receiving task"),
    ProgressStage("intent_parse",    "理解意图",   "Understanding intent", 10,  "thinking",        "thinking_board",  "正在理解需求",     "Understanding intent"),
    ProgressStage("context_budget",  "计算预算",   "Estimating budget",    20,  "calculating",     "budget_panel",    "正在计算 token 预算", "Estimating token budget"),
    ProgressStage("memory_retrieval","查找记忆",   "Retrieving memory",    30,  "reading_notes",   "memory_wall",     "正在查找记忆",     "Retrieving memory"),
    ProgressStage("rag_retrieval",   "查找资料",   "Searching knowledge",  40,  "searching_books", "library",         "正在查找项目资料", "Searching project knowledge"),
    ProgressStage("context_build",   "整理上下文", "Building context",     50,  "organizing",      "context_table",   "正在整理上下文",   "Building context"),
    ProgressStage("planning",        "规划步骤",   "Planning steps",       60,  "planning",        "map_table",       "正在规划执行步骤", "Planning execution steps"),
    ProgressStage("tool_call",       "调用工具",   "Calling tools",        75,  "tooling",         "tool_bench",      "正在调用工具",     "Calling tools"),
    ProgressStage("evaluation",      "评估结果",   "Evaluating result",    90,  "grading",         "exam_table",      "正在评估结果",     "Evaluating output"),
    ProgressStage("learning",        "总结经验",   "Learning",             96,  "learning",        "skill_book",      "正在总结经验",     "Learning from this run"),
    ProgressStage("completed",       "完成任务",   "Completed",           100,  "done",            "delivery_desk",   "任务完成",         "Task completed"),
]

_STAGE_MAP: dict[str, ProgressStage] = {s.key: s for s in PROGRESS_STAGES}


class ProgressTracker:
    """根据阶段 key 查找进度信息。"""

    def get_stage(self, key: str) -> ProgressStage:
        """获取指定阶段的完整信息。"""
        return _STAGE_MAP.get(key, PROGRESS_STAGES[0])

    def pct_for(self, key: str) -> int:
        """获取指定阶段的百分比。"""
        s = _STAGE_MAP.get(key)
        return s.pct if s else 0

    def build_event_fields(self, key: str) -> dict[str, Any]:
        """构建 TraceEvent 中的进度相关字段。"""
        s = self.get_stage(key)
        idx = [ps.key for ps in PROGRESS_STAGES].index(key) if key in _STAGE_MAP else 0
        return {
            "stage": s.key,
            "stage_label_zh": s.label_zh,
            "stage_label_en": s.label_en,
            "status_text_zh": s.status_text_zh,
            "status_text_en": s.status_text_en,
            "progress_pct": s.pct,
            "avatar_state": s.avatar_state,
            "avatar_scene": s.avatar_scene,
            "stage_index": idx,
            "stage_total": len(PROGRESS_STAGES),
        }

    def get_stage_for_event(self, event_type: str) -> ProgressStage:
        """根据事件类型映射到阶段。"""
        mapping = {
            "mcp.call.received":      "mcp_received",
            "task.classified":        "intent_parse",
            "intent.parsed":          "intent_parse",
            "context.budgeted":       "context_budget",
            "memory.retrieved":       "memory_retrieval",
            "rag.retrieved":          "rag_retrieval",
            "context.compressed":     "context_build",
            "context.built":          "context_build",
            "workflow.plan.created":  "planning",
            "tool.call.started":      "tool_call",
            "tool.call.completed":    "tool_call",
            "security.checked":       "tool_call",
            "approval.required":      "tool_call",
            "eval.completed":         "evaluation",
            "badcase.recorded":       "evaluation",
            "skillopt.rollout.collected": "learning",
            "skillopt.pattern.found":     "learning",
            "skillopt.patch.proposed":    "learning",
            "skillopt.validation.completed": "learning",
            "skillopt.exported":      "learning",
            "task.completed":         "completed",
            "task.failed":            "completed",
        }
        key = mapping.get(event_type, "mcp_received")
        return self.get_stage(key)
