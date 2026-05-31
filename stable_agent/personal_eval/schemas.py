"""personal_eval.schemas — 个人评估数据模型定义。

V11 新增：定义 PersonalEvalCase, Rubric, ABRegressionResult, FeedbackRecord 等核心数据结构。
所有数据类使用 @dataclass，字段类型注解完整，JSON serializable。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PersonalEvalCase:
    """个人评估用例。

    用户定义的评估场景，用于 A/B 回归测试。

    Attributes:
        case_id: 唯一标识。
        task: 任务描述文本。
        task_type: 任务类型标签 (bug_fix, code_gen, ui_design 等)。
        must_keep: 新 skill 必须保留的关键词列表。
        must_avoid: 新 skill 必须避免的关键词/模式列表。
        success_criteria: 成功标准描述。
        failure_modes: 失败模式列表。
        source_bad_case_id: 来源 bad case ID（可选）。
        created_at: 创建时间戳。
    """

    case_id: str = field(default_factory=lambda: f"pec_{uuid.uuid4().hex[:12]}")
    task: str = ""
    task_type: str = "general"
    must_keep: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)
    success_criteria: str = ""
    failure_modes: list[str] = field(default_factory=list)
    source_bad_case_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（JSON serializable）。"""
        return {
            "case_id": self.case_id,
            "task": self.task,
            "task_type": self.task_type,
            "must_keep": self.must_keep,
            "must_avoid": self.must_avoid,
            "success_criteria": self.success_criteria,
            "failure_modes": self.failure_modes,
            "source_bad_case_id": self.source_bad_case_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonalEvalCase:
        """从字典反序列化。"""
        return cls(
            case_id=data.get("case_id", f"pec_{uuid.uuid4().hex[:12]}"),
            task=data.get("task", ""),
            task_type=data.get("task_type", "general"),
            must_keep=data.get("must_keep", []),
            must_avoid=data.get("must_avoid", []),
            success_criteria=data.get("success_criteria", ""),
            failure_modes=data.get("failure_modes", []),
            source_bad_case_id=data.get("source_bad_case_id", ""),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class Rubric:
    """评分维度定义。

    Attributes:
        rubric_id: 评分维度集 ID。
        dimensions: 维度名称 → 权重的映射，权重总和应为 1.0。
    """

    rubric_id: str = "vibe_coding_default"
    dimensions: dict[str, float] = field(default_factory=lambda: {
        "goal_alignment": 0.30,
        "minimal_change": 0.20,
        "test_passed": 0.20,
        "style_consistency": 0.10,
        "token_efficiency": 0.10,
        "user_preference_match": 0.10,
    })

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（JSON serializable）。"""
        return {
            "rubric_id": self.rubric_id,
            "dimensions": self.dimensions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rubric:
        """从字典反序列化。"""
        return cls(
            rubric_id=data.get("rubric_id", "vibe_coding_default"),
            dimensions=data.get("dimensions", {}),
        )


@dataclass
class ABRegressionResult:
    """A/B 回归测试结果。

    Attributes:
        case_id: 关联的评估用例 ID。
        old_skill_score: 旧 skill 评分。
        new_skill_score: 新 skill 评分。
        delta: 分数差异 (new - old)。
        passed: 是否通过（new > old + min_delta）。
        reason_zh: 中文说明。
        dimension_scores: 各维度评分详情。
    """

    case_id: str = ""
    old_skill_score: float = 0.0
    new_skill_score: float = 0.0
    delta: float = 0.0
    passed: bool = False
    reason_zh: str = ""
    dimension_scores: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（JSON serializable）。"""
        return {
            "case_id": self.case_id,
            "old_skill_score": self.old_skill_score,
            "new_skill_score": self.new_skill_score,
            "delta": self.delta,
            "passed": self.passed,
            "reason_zh": self.reason_zh,
            "dimension_scores": self.dimension_scores,
        }


@dataclass
class FeedbackRecord:
    """反馈记录。

    Attributes:
        feedback_id: 唯一标识。
        run_id: 关联的运行 ID。
        action: 反馈动作类型 (remember_this / dont_do_this_again / correct_and_remember)。
        user_note: 用户备注。
        target: 反馈目标（memory / bad_case / correction）。
        created_at: 创建时间戳。
    """

    feedback_id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    action: str = ""
    user_note: str = ""
    target: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（JSON serializable）。"""
        return {
            "feedback_id": self.feedback_id,
            "run_id": self.run_id,
            "action": self.action,
            "user_note": self.user_note,
            "target": self.target,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackRecord:
        """从字典反序列化。"""
        return cls(
            feedback_id=data.get("feedback_id", f"fb_{uuid.uuid4().hex[:12]}"),
            run_id=data.get("run_id", ""),
            action=data.get("action", ""),
            user_note=data.get("user_note", ""),
            target=data.get("target", ""),
            created_at=data.get("created_at", time.time()),
        )
