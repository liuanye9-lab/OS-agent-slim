"""Understanding Trace 数据结构定义。

定义 V11 阶段 3 所需的核心数据结构:
- UnderstandingTrace: 语义理解轨迹
- ExpressionProfile: 用户表达习惯
- CorrectionRecord: 纠正记录
- AssumptionRecord: 假设记录

所有字段支持 JSON 序列化 (dataclass + 基础类型)。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class TaskType(StrEnum):
    """语义层面的任务类型（区别于 models.TaskType 的工作流分类）。"""

    CODING = "coding"
    DEBUGGING = "debugging"
    REVIEW = "review"
    REFACTOR = "refactor"
    DESIGN = "design"
    PRODUCT = "product"
    UNKNOWN = "unknown"


class ExpressionScope(StrEnum):
    """表达习惯的作用域。"""

    GLOBAL = "global"
    DESIGN = "design"
    CODING = "coding"
    PRODUCT = "product"


@dataclass
class UnderstandingTrace:
    """语义理解轨迹。

    记录一次用户输入的完整语义解析结果，包括:
    - 原始输入和解读目标
    - 任务类型分类
    - 假设、保护约束和不确定性
    - 表达习惯匹配和语义风险
    - 置信度和是否需要确认

    Attributes:
        trace_id: 轨迹唯一标识。
        run_id: 关联的运行 ID。
        user_original_input: 用户原始输入。
        interpreted_goal: 系统解读的目标。
        task_type: 识别的任务类型。
        assumptions: 假设列表。
        protected_constraints: 保护性约束列表。
        uncertainties: 不确定性列表。
        expression_matches: 匹配的表达习惯。
        semantic_risk_flags: 语义风险标记。
        confidence: 整体置信度 0.0~1.0。
        needs_user_confirmation: 是否需要用户确认。
        created_at: 创建时间戳。
    """

    trace_id: str = field(default_factory=lambda: f"ut_{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    user_original_input: str = ""
    interpreted_goal: str = ""
    task_type: str = TaskType.UNKNOWN
    assumptions: list[str] = field(default_factory=list)
    protected_constraints: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    expression_matches: list[dict] = field(default_factory=list)
    semantic_risk_flags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    needs_user_confirmation: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """转换为 JSON 可序列化字典。"""
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "user_original_input": self.user_original_input,
            "interpreted_goal": self.interpreted_goal,
            "task_type": self.task_type,
            "assumptions": self.assumptions,
            "protected_constraints": self.protected_constraints,
            "uncertainties": self.uncertainties,
            "expression_matches": self.expression_matches,
            "semantic_risk_flags": self.semantic_risk_flags,
            "confidence": self.confidence,
            "needs_user_confirmation": self.needs_user_confirmation,
            "created_at": self.created_at,
        }


@dataclass
class ExpressionProfile:
    """用户表达习惯。

    记录用户常用的表达方式及其标准化含义，用于提升语义理解准确度。

    Attributes:
        phrase: 用户表达短语。
        normalized_meaning: 标准化含义列表。
        scope: 作用域。
        confirmed_by_user: 是否经用户确认。
        confidence: 置信度 0.0~1.0。
        examples: 示例列表。
    """

    phrase: str = ""
    normalized_meaning: list[str] = field(default_factory=list)
    scope: str = ExpressionScope.GLOBAL
    confirmed_by_user: bool = False
    confidence: float = 0.5
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为 JSON 可序列化字典。"""
        return {
            "phrase": self.phrase,
            "normalized_meaning": self.normalized_meaning,
            "scope": self.scope,
            "confirmed_by_user": self.confirmed_by_user,
            "confidence": self.confidence,
            "examples": self.examples,
        }


@dataclass
class CorrectionRecord:
    """纠正记录。

    记录用户对系统理解的纠正，可转化为 ExpressionProfile。

    Attributes:
        correction_id: 纠正记录唯一标识。
        run_id: 关联的运行 ID。
        wrong_interpretation: 错误解读。
        correct_interpretation: 正确解读。
        trigger_phrase: 触发纠正的短语。
        created_at: 创建时间戳。
        converted_to_expression_rule: 是否已转化为表达规则。
    """

    correction_id: str = field(default_factory=lambda: f"cr_{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    wrong_interpretation: str = ""
    correct_interpretation: str = ""
    trigger_phrase: str = ""
    created_at: float = field(default_factory=time.time)
    converted_to_expression_rule: bool = False

    def to_dict(self) -> dict:
        """转换为 JSON 可序列化字典。"""
        return {
            "correction_id": self.correction_id,
            "run_id": self.run_id,
            "wrong_interpretation": self.wrong_interpretation,
            "correct_interpretation": self.correct_interpretation,
            "trigger_phrase": self.trigger_phrase,
            "created_at": self.created_at,
            "converted_to_expression_rule": self.converted_to_expression_rule,
        }


@dataclass
class AssumptionRecord:
    """假设记录。

    Attributes:
        assumption_id: 假设唯一标识。
        trace_id: 关联的 trace ID。
        assumption: 假设内容。
        confidence: 置信度 0.0~1.0。
        confirmed: 是否已确认。
        created_at: 创建时间戳。
    """

    assumption_id: str = field(default_factory=lambda: f"ar_{uuid.uuid4().hex[:12]}")
    trace_id: str = ""
    assumption: str = ""
    confidence: float = 0.5
    confirmed: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """转换为 JSON 可序列化字典。"""
        return {
            "assumption_id": self.assumption_id,
            "trace_id": self.trace_id,
            "assumption": self.assumption,
            "confidence": self.confidence,
            "confirmed": self.confirmed,
            "created_at": self.created_at,
        }
