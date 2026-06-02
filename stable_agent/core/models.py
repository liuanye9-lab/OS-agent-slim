"""stable_agent/core/models.py — 核心数据模型。

定义 TaskSpec、RunTrace、ToolRunResult 等核心数据类，
用于在 Executor、Curator、Validator 之间传递数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskSpec:
    """任务规格定义。

    从 MCP 工具参数解析而来，传递给 Executor 执行。
    """
    task_input: str
    mode: str = "auto"
    run_id: str | None = None
    open_dashboard: bool = True
    force_eval_failed: bool = False
    force_failure_mode: str | None = None
    force_regression_case: bool = False
    force_skill_patch: bool = False
    force_validation_passed: bool | None = None
    dry_run_learning: bool = True
    project_id: str | None = None
    agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_args(cls, args: dict[str, Any]) -> TaskSpec:
        """从 MCP 工具参数字典构建 TaskSpec。"""
        return cls(
            task_input=args.get("task_input", ""),
            mode=args.get("mode", "auto"),
            run_id=args.get("run_id"),
            open_dashboard=args.get("open_dashboard", True),
            force_eval_failed=args.get("force_eval_failed", False),
            force_failure_mode=args.get("force_failure_mode"),
            force_regression_case=args.get("force_regression_case", False),
            force_skill_patch=args.get("force_skill_patch", False),
            force_validation_passed=args.get("force_validation_passed", None),
            dry_run_learning=args.get("dry_run_learning", True),
            project_id=args.get("project_id"),
            agent_id=args.get("agent_id"),
        )


@dataclass
class RunTrace:
    """运行轨迹。

    Executor 执行完毕后输出，供 Curator 分析。
    """
    run_id: str
    ok: bool
    status: str
    eval_passed: bool
    eval_score: float | None
    events: list[dict[str, Any]]
    output_text: str
    artifacts: dict[str, Any]
    si_report: dict[str, Any] | None

    @property
    def is_learning_worthy(self) -> bool:
        """判断本次运行是否值得学习。"""
        if self.eval_score is not None and self.eval_score < 0.75:
            return True
        if self.artifacts.get("force_eval_failed"):
            return True
        if self.artifacts.get("user_feedback"):
            return True
        if self.artifacts.get("missing_required_events"):
            return True
        if self.artifacts.get("dashboard_replay_ok") is False:
            return True
        return False


@dataclass
class ToolRunResult:
    """工具运行结果。

    最终返回给 MCP 客户端的数据结构。
    必须与 stableagent.task.os_agent 的外部契约一致。
    """
    ok: bool
    run_id: str
    dashboard_url: str
    observer_url: str
    event_sync_ok: bool
    event_api_ok: bool
    dashboard_replay_ok: bool
    api_event_count: int
    emitted_event_count: int
    missing_required_events: list[str]
    api_missing_required_events: list[str]
    eval_passed: bool
    eval_score: float | None
    si_report: dict[str, Any] | None
    progress_pct: int
    current_stage: str
    # 扩展字段
    understanding_trace: dict[str, Any] | None = None
    token_report: dict[str, Any] | None = None
    dry_run_learning: bool = True
    force_validation_passed: bool | None = None
    sync_errors: list[str] = field(default_factory=list)
    task_type: str = "unknown"
    workflow_state: str = "completed"


@dataclass
class SkillCandidate:
    """技能候选。

    Curator 从 RunTrace 中提炼，等待 ValidationGate 验证。
    """
    candidate_id: str
    source_run_id: str
    failure_mode: str
    evidence_events: list[str]
    proposed_rule: str
    when_to_use: str
    do_not_use_when: str
    validation_plan: str
    risk_level: str = "low"
    status: str = "draft"
    domain: str = "general"
    created_at: str = ""
    reward_proxy_score: float = 0.0


@dataclass
class ValidationResult:
    """验证结果。"""
    passed: bool
    schema_valid: bool = False
    regression_count: int = 0
    score_delta: float = 0.0
    event_completeness: float = 1.0
    token_delta: float = 0.0
    reason: str = ""
    validations_count: int = 0
