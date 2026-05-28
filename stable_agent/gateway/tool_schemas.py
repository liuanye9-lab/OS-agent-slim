"""统一 MCP 工具 Schema 定义。

定义 V5 所有 14 个 stableagent.* 命名空间工具的 JSON Schema，
以及对应的头像状态映射（AVATAR_STATE_MAP）。

所有工具遵循统一的命名约定：stableagent.<domain>.<action>
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 14 个统一命名工具的 JSON Schema
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict[str, Any]] = {
    "stableagent.task.process": {
        "name": "stableagent.task.process",
        "title": "处理任务",
        "description": "端到端处理一个用户任务",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {
                    "type": "string",
                    "description": "用户任务描述",
                }
            },
            "required": ["task_input"],
        },
        "risk_level": "medium",
    },
    "stableagent.context.build": {
        "name": "stableagent.context.build",
        "title": "构建上下文包",
        "description": "整合记忆+RAG+规则构建上下文包",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.context.estimate_budget": {
        "name": "stableagent.context.estimate_budget",
        "title": "估算预算",
        "description": "估算任务所需 Token 预算",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.memory.retrieve": {
        "name": "stableagent.memory.retrieve",
        "title": "检索记忆",
        "description": "检索相关记忆条目",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.memory.write_candidate": {
        "name": "stableagent.memory.write_candidate",
        "title": "写入候选记忆",
        "description": "将一条经验写入记忆候选队列",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "item_type": {"type": "string", "default": "success_case"},
                "source": {"type": "string"},
            },
            "required": ["content", "source"],
        },
        "risk_level": "low",
    },
    "stableagent.rag.retrieve": {
        "name": "stableagent.rag.retrieve",
        "title": "RAG 检索",
        "description": "从知识库检索相关文档",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "risk_level": "low",
    },
    "stableagent.eval.evaluate": {
        "name": "stableagent.eval.evaluate",
        "title": "评测输出",
        "description": "评测模型输出质量",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
                "input_context": {"type": "string"},
                "output": {"type": "string"},
            },
            "required": ["task_input", "input_context", "output"],
        },
        "risk_level": "low",
    },
    "stableagent.badcase.record": {
        "name": "stableagent.badcase.record",
        "title": "记录失败案例",
        "description": "记录一个失败案例供后续改进",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
                "input_context": {"type": "string"},
                "output": {"type": "string"},
                "evaluation": {"type": "object"},
            },
            "required": ["task_input", "input_context", "output"],
        },
        "risk_level": "low",
    },
    "stableagent.skillopt.status": {
        "name": "stableagent.skillopt.status",
        "title": "SkillOpt 状态",
        "description": "获取技能优化引擎状态",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "low",
    },
    "stableagent.skillopt.get_current_skill": {
        "name": "stableagent.skillopt.get_current_skill",
        "title": "获取当前技能",
        "description": "获取当前技能文档内容和版本",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "low",
    },
    "stableagent.skillopt.run_epoch": {
        "name": "stableagent.skillopt.run_epoch",
        "title": "运行优化回合",
        "description": "运行一轮技能优化",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_rollouts": {"type": "integer", "default": 40},
            },
        },
        "risk_level": "medium",
    },
    "stableagent.skillopt.export_best": {
        "name": "stableagent.skillopt.export_best",
        "title": "导出最优技能",
        "description": "导出 best_skill.md",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "medium",
    },
    "stableagent.trace.get_run": {
        "name": "stableagent.trace.get_run",
        "title": "获取运行轨迹",
        "description": "获取指定 run 的完整 trace",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
            },
            "required": ["run_id"],
        },
        "risk_level": "low",
    },
    "stableagent.approval.respond": {
        "name": "stableagent.approval.respond",
        "title": "响应审批",
        "description": "批准或拒绝一个待审批操作",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["approve", "reject"],
                },
                "reason": {"type": "string"},
            },
            "required": ["request_id", "action"],
        },
        "risk_level": "high",
    },
}

# ---------------------------------------------------------------------------
# 头像状态映射 —— 事件类型 → 头像动画状态
# ---------------------------------------------------------------------------

AVATAR_STATE_MAP: dict[str, str] = {
    "mcp.call.received": "listening",
    "task.classified": "thinking",
    "context.budgeted": "calculating",
    "memory.retrieved": "reading_notes",
    "rag.retrieved": "searching_books",
    "tool.risk_checked": "safety_check",
    "approval.required": "waiting_approval",
    "workflow.step.started": "working",
    "eval.completed": "grading",
    "skillopt.patch.proposed": "writing_rule",
    "skillopt.validation.running": "examining",
    "skillopt.exported": "archiving",
    "tool.failed": "sweating",
    "task.completed": "celebrating",
    "default": "idle",
}

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def get_tool_names() -> list[str]:
    """返回所有已注册工具的完整名称列表。"""
    return list(TOOLS.keys())


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """按名称获取单个工具的定义。如果未找到则返回 None。"""
    return TOOLS.get(name)


def get_avatar_state(event_type: str) -> str:
    """根据事件类型获取对应的头像状态。

    如果未找到精确匹配，返回默认状态 "idle"。

    Args:
        event_type: 事件类型字符串，如 "mcp.call.received"。

    Returns:
        对应的头像动画状态名称。
    """
    return AVATAR_STATE_MAP.get(event_type, AVATAR_STATE_MAP["default"])


def get_risk_level(tool_name: str) -> str:
    """获取指定工具的风险等级。

    Args:
        tool_name: 工具完整名称。

    Returns:
        风险等级字符串（"low"/"medium"/"high"），如果工具未注册则返回 "low"。
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        return "low"
    return tool.get("risk_level", "low")
