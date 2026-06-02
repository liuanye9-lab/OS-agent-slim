"""Tool Profile Router — 三级工具暴露策略。

根据 STABLE_AGENT_TOOL_PROFILE 环境变量控制 MCP tools/list 返回的工具集。

- minimal: 只暴露 8-12 个核心工具 (默认)
- default: 核心 + eval/skill 调试工具
- full: 暴露所有旧工具 (兼容旧行为)

用法::

    export STABLE_AGENT_TOOL_PROFILE=minimal
    # 或在 .env / docker-compose 中设置
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Any


class ToolProfile(StrEnum):
    """工具暴露级别。"""

    MINIMAL = "minimal"
    DEFAULT = "default"
    FULL = "full"


# ── minimal: 只暴露核心闭环工具 (10 个) ──────────────────────
MINIMAL_TOOLS: set[str] = {
    "stableagent.task.os_agent",              # 主入口
    "stableagent.trace.get_run",              # 运行轨迹查询
    "stableagent.feedback.correct_and_remember",  # 纠正并记住
    "stableagent.feedback.remember",          # 记住这个
    "stableagent.feedback.dont_do_this_again",    # 下次别这样
    "stableagent.token.report",               # Token 报告
    "stableagent.capsule.status",             # 胶囊状态
    "stableagent.capsule.doctor",             # 胶囊健康检查
    "stableagent.memory.health",              # 记忆健康
    "stableagent.token.summary",              # Token 摘要
}

# ── default: 核心 + eval/skill 调试工具 (+7 个) ──────────────
DEFAULT_EXTRA_TOOLS: set[str] = {
    "stableagent.eval.case.create",           # 创建评估用例
    "stableagent.eval.case.list",             # 列出评估用例
    "stableagent.eval.run_ab",                # A/B 回归测试
    "stableagent.eval.evaluate",              # 评测输出质量
    "stableagent.skill.validate",             # 验证 Skill
    "stableagent.skill.export_best",          # 导出最佳 Skill
    "stableagent.memory.search",              # 记忆检索 (如果存在)
    "stableagent.memory.retrieve",            # 记忆检索
    "stableagent.skillopt.status",            # SkillOpt 状态
    "stableagent.skillopt.get_current_skill", # 当前技能文档
}

# ── full: 所有旧工具 (55 个) ─────────────────────────────────
# full 模式不做过滤，返回 TOOLS 字典中的所有工具


def get_tool_profile() -> ToolProfile:
    """从环境变量读取当前 profile，未设置时默认 minimal。"""
    raw = os.environ.get("STABLE_AGENT_TOOL_PROFILE", "minimal").strip().lower()
    try:
        return ToolProfile(raw)
    except ValueError:
        return ToolProfile.MINIMAL


def should_expose_tool(tool_name: str) -> bool:
    """判断指定工具是否在当前 profile 下应该暴露。

    Args:
        tool_name: 工具全限定名，如 "stableagent.task.os_agent"。

    Returns:
        True 表示应该暴露，False 表示隐藏。
    """
    profile = get_tool_profile()

    if profile == ToolProfile.FULL:
        return True

    if profile == ToolProfile.MINIMAL:
        return tool_name in MINIMAL_TOOLS

    # DEFAULT = MINIMAL + DEFAULT_EXTRA_TOOLS
    return tool_name in MINIMAL_TOOLS or tool_name in DEFAULT_EXTRA_TOOLS


def filter_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """根据当前 profile 过滤工具列表。

    Args:
        tools: 完整工具列表 (来自 TOOLS 字典)。

    Returns:
        过滤后的工具列表。
    """
    profile = get_tool_profile()

    if profile == ToolProfile.FULL:
        return tools

    return [t for t in tools if should_expose_tool(t.get("name", ""))]


def get_profile_tool_count() -> dict[str, int]:
    """返回各 profile 级别的工具数量 (用于测试/诊断)。"""
    return {
        "minimal": len(MINIMAL_TOOLS),
        "default": len(MINIMAL_TOOLS) + len(DEFAULT_EXTRA_TOOLS),
    }
