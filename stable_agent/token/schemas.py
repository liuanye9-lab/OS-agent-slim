"""Token Budget Ledger — TokenRunRecord 数据模型定义。

定义一次运行的完整 token 预算记录，包括基线估算、上下文各阶段
token 消耗、压缩节省量和风险评估。

所有字段 JSON serializable，可直接用于 API 返回。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenRunRecord:
    """一次运行的 Token 预算记录。

    记录从基线估算到最终输出的完整 token 消耗链路，
    包括去重、检索、保护、注入、丢弃等各阶段的 token 数。

    Attributes:
        record_id: 记录唯一标识（tok_ 前缀）。
        run_id: 关联的运行 ID。
        created_at: 创建时间戳（time.time() 格式）。
        baseline_tokens_estimated: 基线 token 估算值（原始上下文大小）。
        raw_context_tokens: 原始上下文 token 数。
        deduped_tokens: 去重后 token 数。
        retrieved_tokens: 检索到的 token 数。
        protected_tokens: 受保护的 token 数。
        injected_tokens: 最终注入的 token 数。
        dropped_tokens: 被丢弃的 token 数。
        output_tokens_estimated: 输出 token 估算值。
        saved_tokens_estimated: 节省的 token 估算值。
        saving_ratio: 节省比例（0.0~1.0）。
        risk_level: 风险等级（low/medium/high）。
        protected_items: 受保护条目列表。
        dropped_items: 被丢弃条目列表。
        summary_zh: 中文摘要。
    """

    record_id: str = field(default_factory=lambda: f"tok_{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    created_at: float = field(default_factory=time.time)
    baseline_tokens_estimated: int = 0
    raw_context_tokens: int = 0
    deduped_tokens: int = 0
    retrieved_tokens: int = 0
    protected_tokens: int = 0
    injected_tokens: int = 0
    dropped_tokens: int = 0
    output_tokens_estimated: int = 0
    saved_tokens_estimated: int = 0
    saving_ratio: float = 0.0
    risk_level: str = "low"
    protected_items: list[dict[str, Any]] = field(default_factory=list)
    dropped_items: list[dict[str, Any]] = field(default_factory=list)
    summary_zh: str = ""

    def __post_init__(self) -> None:
        """验证 risk_level 合法性。"""
        valid_levels = {"low", "medium", "high"}
        if self.risk_level not in valid_levels:
            raise ValueError(
                f"risk_level must be one of {valid_levels}, got '{self.risk_level}'"
            )

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON serializable 字典。

        Returns:
            包含所有字段的字典。
        """
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "baseline_tokens_estimated": self.baseline_tokens_estimated,
            "raw_context_tokens": self.raw_context_tokens,
            "deduped_tokens": self.deduped_tokens,
            "retrieved_tokens": self.retrieved_tokens,
            "protected_tokens": self.protected_tokens,
            "injected_tokens": self.injected_tokens,
            "dropped_tokens": self.dropped_tokens,
            "output_tokens_estimated": self.output_tokens_estimated,
            "saved_tokens_estimated": self.saved_tokens_estimated,
            "saving_ratio": self.saving_ratio,
            "risk_level": self.risk_level,
            "protected_items": self.protected_items,
            "dropped_items": self.dropped_items,
            "summary_zh": self.summary_zh,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenRunRecord:
        """从字典创建 TokenRunRecord 实例。

        Args:
            data: 包含字段值的字典。

        Returns:
            TokenRunRecord 实例。
        """
        return cls(
            record_id=data.get("record_id", ""),
            run_id=data.get("run_id", ""),
            created_at=data.get("created_at", time.time()),
            baseline_tokens_estimated=data.get("baseline_tokens_estimated", 0),
            raw_context_tokens=data.get("raw_context_tokens", 0),
            deduped_tokens=data.get("deduped_tokens", 0),
            retrieved_tokens=data.get("retrieved_tokens", 0),
            protected_tokens=data.get("protected_tokens", 0),
            injected_tokens=data.get("injected_tokens", 0),
            dropped_tokens=data.get("dropped_tokens", 0),
            output_tokens_estimated=data.get("output_tokens_estimated", 0),
            saved_tokens_estimated=data.get("saved_tokens_estimated", 0),
            saving_ratio=data.get("saving_ratio", 0.0),
            risk_level=data.get("risk_level", "low"),
            protected_items=data.get("protected_items", []),
            dropped_items=data.get("dropped_items", []),
            summary_zh=data.get("summary_zh", ""),
        )
