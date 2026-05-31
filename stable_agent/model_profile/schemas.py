"""stable_agent.model_profile.schemas — 模型画像数据结构。

定义 ModelProfile dataclass，描述单个 LLM 模型的能力特征、风险和适配规则。
所有字段支持 JSON 序列化。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextBudgetHint:
    """上下文注入预算提示。

    Attributes:
        max_injected_tokens: 该模型建议的最大注入 token 数。
        prefer_short_context: 是否倾向于短上下文（影响压缩策略）。
    """

    max_injected_tokens: int = 12000
    prefer_short_context: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_injected_tokens": self.max_injected_tokens,
            "prefer_short_context": self.prefer_short_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextBudgetHint:
        return cls(
            max_injected_tokens=data.get("max_injected_tokens", 12000),
            prefer_short_context=data.get("prefer_short_context", False),
        )


@dataclass
class ToolCallingHint:
    """工具调用风格提示。

    Attributes:
        requires_strict_json: 是否要求严格 JSON schema（影响 prompt 构造）。
        avoid_parallel_tool_calls: 是否应避免并行工具调用。
    """

    requires_strict_json: bool = True
    avoid_parallel_tool_calls: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "requires_strict_json": self.requires_strict_json,
            "avoid_parallel_tool_calls": self.avoid_parallel_tool_calls,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallingHint:
        return cls(
            requires_strict_json=data.get("requires_strict_json", True),
            avoid_parallel_tool_calls=data.get("avoid_parallel_tool_calls", False),
        )


@dataclass
class ModelProfile:
    """模型画像。

    描述单个 LLM 模型的能力特征、已知风险、适用场景和 prompt 适配规则。
    用于 ModelRouter 做任务-模型匹配，以及 AdapterLoader 生成注入配置。

    Attributes:
        model_id: 模型标识，如 "claude" / "gpt" / "qwen" / "gemini" / "generic"。
        display_name: 人类可读名称。
        strengths: 已知优势列表。
        risks: 已知风险/限制列表。
        best_for: 最适合的任务类型列表。
        avoid_for: 应避免使用的任务类型列表。
        prompt_adapter_rules: prompt 适配规则列表（注入 system prompt 的指令片段）。
        context_budget_hint: 上下文注入预算提示。
        tool_calling_hint: 工具调用风格提示。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    model_id: str = "generic"
    display_name: str = "Generic"
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    best_for: list[str] = field(default_factory=list)
    avoid_for: list[str] = field(default_factory=list)
    prompt_adapter_rules: list[str] = field(default_factory=list)
    context_budget_hint: ContextBudgetHint = field(default_factory=ContextBudgetHint)
    tool_calling_hint: ToolCallingHint = field(default_factory=ToolCallingHint)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 可序列化字典。"""
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "strengths": list(self.strengths),
            "risks": list(self.risks),
            "best_for": list(self.best_for),
            "avoid_for": list(self.avoid_for),
            "prompt_adapter_rules": list(self.prompt_adapter_rules),
            "context_budget_hint": self.context_budget_hint.to_dict(),
            "tool_calling_hint": self.tool_calling_hint.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelProfile:
        """从字典创建 ModelProfile。"""
        return cls(
            model_id=data.get("model_id", "generic"),
            display_name=data.get("display_name", "Generic"),
            strengths=data.get("strengths", []),
            risks=data.get("risks", []),
            best_for=data.get("best_for", []),
            avoid_for=data.get("avoid_for", []),
            prompt_adapter_rules=data.get("prompt_adapter_rules", []),
            context_budget_hint=ContextBudgetHint.from_dict(
                data.get("context_budget_hint", {})
            ),
            tool_calling_hint=ToolCallingHint.from_dict(
                data.get("tool_calling_hint", {})
            ),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
