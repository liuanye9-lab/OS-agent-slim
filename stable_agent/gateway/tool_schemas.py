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
    # V6.5: /os-agent 快捷入口
    "stableagent.task.os_agent": {
        "name": "stableagent.task.os_agent",
        "title": "OS Agent 自优化工作流",
        "description": "启动 StableAgent OS 自优化工作流，将执行过程实时同步到可视化面板。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {
                    "type": "string",
                    "description": "用户希望 OS Agent 执行或优化的任务",
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "diagnose", "optimize", "skillopt", "observe"],
                    "default": "auto",
                    "description": "运行模式",
                },
                "open_dashboard": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否返回 Dashboard 链接",
                },
                "run_id": {
                    "type": "string",
                    "description": "可选，已有 run_id",
                },
            },
            "required": ["task_input"],
        },
        "risk_level": "medium",
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
    "workflow.step.started": "tooling",
    "planning.started": "planning",
    "eval.completed": "grading",
    "skillopt.patch.proposed": "learning",
    "skillopt.validation.running": "grading",
    "skillopt.exported": "archiving",
    "tool.failed": "failed",
    "task.completed": "done",
    "default": "listening",
}

# ---------------------------------------------------------------------------
# 13 语义场景映射 —— 头像状态 → 场景/道具/标签
# ---------------------------------------------------------------------------

AVATAR_SCENE_MAP: dict[str, dict[str, str]] = {
    "listening": {
        "scene": "desk",
        "prop": "task_card",
        "label_zh": "正在接收任务",
        "label_en": "Receiving task",
    },
    "thinking": {
        "scene": "thinking_board",
        "prop": "magnifier",
        "label_zh": "正在理解你的需求",
        "label_en": "Understanding your intent",
    },
    "reading_notes": {
        "scene": "memory_wall",
        "prop": "memory_cards",
        "label_zh": "正在找以前的经验",
        "label_en": "Retrieving prior memory",
    },
    "searching_books": {
        "scene": "library",
        "prop": "bookshelf",
        "label_zh": "正在查找项目资料",
        "label_en": "Searching project knowledge",
    },
    "calculating": {
        "scene": "budget_panel",
        "prop": "abacus",
        "label_zh": "正在计算 token 成本",
        "label_en": "Estimating token budget",
    },
    "planning": {
        "scene": "map_table",
        "prop": "route_map",
        "label_zh": "正在规划执行步骤",
        "label_en": "Planning execution steps",
    },
    "tooling": {
        "scene": "tool_bench",
        "prop": "wrench",
        "label_zh": "正在调用工具",
        "label_en": "Calling a tool",
    },
    "safety_check": {
        "scene": "checkpoint",
        "prop": "helmet",
        "label_zh": "正在做安全检查",
        "label_en": "Running safety check",
    },
    "waiting_approval": {
        "scene": "approval_gate",
        "prop": "red_card",
        "label_zh": "等待你确认",
        "label_en": "Waiting for approval",
    },
    "grading": {
        "scene": "exam_table",
        "prop": "score_sheet",
        "label_zh": "正在评估结果",
        "label_en": "Evaluating output",
    },
    "learning": {
        "scene": "skill_book",
        "prop": "notebook",
        "label_zh": "正在总结经验",
        "label_en": "Learning from this run",
    },
    "archiving": {
        "scene": "archive_cabinet",
        "prop": "best_skill_file",
        "label_zh": "正在更新 best_skill.md",
        "label_en": "Updating best_skill.md",
    },
    "done": {
        "scene": "delivery_desk",
        "prop": "done_stamp",
        "label_zh": "任务完成",
        "label_en": "Task completed",
    },
    "failed": {
        "scene": "error_board",
        "prop": "warning_sign",
        "label_zh": "任务失败，正在记录原因",
        "label_en": "Task failed, recording reason",
    },
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


def get_scene_for_state(state: str) -> dict[str, str]:
    """根据头像状态名获取对应的语义场景配置。

    Args:
        state: 头像状态名，如 "listening"、"thinking" 等。

    Returns:
        包含 scene, prop, label_zh, label_en 的字典。
        如果未找到，返回 listening 的默认场景。
    """
    return AVATAR_SCENE_MAP.get(state, AVATAR_SCENE_MAP["listening"])


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
