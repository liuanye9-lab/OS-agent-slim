"""V6.5 Observation 层 — 运行时可观测性。

本包提供运行时的观察与追踪能力：
- RunStore: 按 run_id 索引的内存存储，管理事件和运行状态
- EventStream: 异步事件流，支持按 run_id 的多订阅者发布/订阅
- DecisionTraceBuilder: 从 event payload 构建 DecisionTrace
- RunInsightGenerator: 任务结束后生成用户可读总结
- LearningEvidence: SkillOpt 学习证据
- DashboardProjection: DecisionTrace → 前端 Dashboard V2 投影
"""

from __future__ import annotations

from stable_agent.observation.event_stream import EventStream
from stable_agent.observation.run_store import RunStore
from stable_agent.observation.dashboard_sync import DashboardSync
from stable_agent.observation.decision_trace import (
    DecisionTrace, DecisionEvidence, DecisionStage, RunInsight,
)
from stable_agent.observation.decision_trace_builder import DecisionTraceBuilder
from stable_agent.observation.run_insight import RunInsightGenerator
from stable_agent.observation.learning_evidence import LearningEvidence
from stable_agent.observation.dashboard_projection import DashboardProjection
from stable_agent.observation.user_feedback_signal import (
    UserFeedbackSignal, FEEDBACK_TYPES, FEEDBACK_LABELS,
)
# V6.2: ProgressModel 已移除导出 — 被 runtime/run_lifecycle.py 的 22 阶段 RunLifecycle 替代

__all__ = [
    "RunStore",
    "EventStream",
    "DashboardSync",
    "DecisionTrace",
    "DecisionEvidence",
    "DecisionStage",
    "RunInsight",
    "DecisionTraceBuilder",
    "RunInsightGenerator",
    "LearningEvidence",
    "DashboardProjection",
    "UserFeedbackSignal",
    "FEEDBACK_TYPES",
    "FEEDBACK_LABELS",
]
