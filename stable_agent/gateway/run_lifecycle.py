"""Run Lifecycle — 统一状态机 (Commercial SaaS P0)。

定义 20 个标准 RunStage 及对应进度百分比。
所有模块必须使用此状态，禁止前端自己猜进度。

用法::

    from stable_agent.gateway.run_lifecycle import RunStage, STAGE_PROGRESS
    ctx.update_stage(RunStage.PLANNING)
    progress_pct = STAGE_PROGRESS[RunStage.PLANNING]
"""

from __future__ import annotations

from typing import Literal

# ------------------------------------------------------------------
# 统一 RunStage
# ------------------------------------------------------------------

RunStage = Literal[
    "created",
    "received",
    "intent_parsing",
    "context_budgeting",
    "memory_retrieving",
    "rag_retrieving",
    "context_building",
    "planning",
    "acting",
    "observing",
    "evaluating",
    "failure_attribution",
    "regression_generation",
    "skill_patch_proposal",
    "validation",
    "human_review",
    "exporting",
    "completed",
    "failed",
    "cancelled",
]

# ------------------------------------------------------------------
# 阶段 → 进度百分比
# ------------------------------------------------------------------

STAGE_PROGRESS: dict[str, int] = {
    "created": 0,
    "received": 5,
    "intent_parsing": 10,
    "context_budgeting": 20,
    "memory_retrieving": 30,
    "rag_retrieving": 40,
    "context_building": 50,
    "planning": 60,
    "acting": 70,
    "observing": 78,
    "evaluating": 85,
    "failure_attribution": 90,
    "regression_generation": 93,
    "skill_patch_proposal": 95,
    "validation": 97,
    "human_review": 98,
    "exporting": 99,
    "completed": 100,
    "failed": -1,
    "cancelled": -1,
}

# ------------------------------------------------------------------
# 阶段 → 中文描述
# ------------------------------------------------------------------

STAGE_LABEL_ZH: dict[str, str] = {
    "created": "已创建",
    "received": "已接收任务",
    "intent_parsing": "理解意图",
    "context_budgeting": "估算 Token 预算",
    "memory_retrieving": "检索相关记忆",
    "rag_retrieving": "检索项目资料",
    "context_building": "构建上下文包",
    "planning": "规划执行步骤",
    "acting": "执行中",
    "observing": "观察结果",
    "evaluating": "评估质量",
    "failure_attribution": "分析失败原因",
    "regression_generation": "生成回归用例",
    "skill_patch_proposal": "生成 Skill 补丁",
    "validation": "验证补丁效果",
    "human_review": "等待人工审核",
    "exporting": "导出 best_skill.md",
    "completed": "完成",
    "failed": "失败",
    "cancelled": "已取消",
}

# ------------------------------------------------------------------
# 阶段 → 头像状态
# ------------------------------------------------------------------

STAGE_AVATAR: dict[str, str] = {
    "created": "listening",
    "received": "listening",
    "intent_parsing": "thinking",
    "context_budgeting": "calculating",
    "memory_retrieving": "reading_notes",
    "rag_retrieving": "searching_books",
    "context_building": "organizing",
    "planning": "planning",
    "acting": "tooling",
    "observing": "tooling",
    "evaluating": "grading",
    "failure_attribution": "grading",
    "regression_generation": "learning",
    "skill_patch_proposal": "learning",
    "validation": "grading",
    "human_review": "waiting_approval",
    "exporting": "archiving",
    "completed": "done",
    "failed": "failed",
    "cancelled": "failed",
}


def get_stage_progress(stage: str) -> int:
    """获取阶段对应的进度百分比。"""
    return STAGE_PROGRESS.get(stage, 0)


def get_stage_label(stage: str, locale: str = "zh") -> str:
    """获取阶段的中/英文标签。"""
    if locale == "zh":
        return STAGE_LABEL_ZH.get(stage, stage)
    return stage.replace("_", " ").title()


def get_stage_avatar(stage: str) -> str:
    """获取阶段对应的头像动画状态。"""
    return STAGE_AVATAR.get(stage, "listening")
