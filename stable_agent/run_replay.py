"""StableAgent OS Run 回放器模块。

本模块提供 RunReplay 类，从 storage 加载历史 run 的 trace
并按时间顺序回放，用于调试、审计和行为分析。

模块职责：
- 列出历史 runs
- 按时间顺序回放 trace spans
- 生成 run 摘要（task/status/duration/tokens/cost/score）
"""

from __future__ import annotations

import time
from typing import Any, Optional

from stable_agent.models import RunRecord, TraceSpan
from stable_agent.plain_language import PlainLanguageExplainer
from stable_agent.storage import StableAgentStorage


class RunReplay:
    """Run 回放器。

    从 storage 加载历史 run 的 trace 并按时间顺序回放，
    提供 run 列表、trace 回放和摘要查询功能。

    Attributes:
        storage: StableAgentStorage 持久化实例。
        _explainer: PlainLanguageExplainer 实例。
    """

    def __init__(self, storage: StableAgentStorage) -> None:
        """初始化 Run 回放器。

        Args:
            storage: StableAgentStorage 实例，用于查询历史 run 数据。
        """
        self.storage: StableAgentStorage = storage
        self._explainer: PlainLanguageExplainer = PlainLanguageExplainer()

        # 确保数据库已初始化
        self.storage.init_db()

    def get_run_list(self, limit: int = 20) -> list[RunRecord]:
        """列出历史 runs。

        Args:
            limit: 返回数量上限，默认 20。

        Returns:
            RunRecord 列表，按 started_at 降序排列。
        """
        return self.storage.list_runs(limit=limit)

    def replay_trace(self, run_id: str) -> list[dict]:
        """按时间顺序回放 trace spans。

        从 storage 加载指定 run 的所有 spans，按 started_at 升序排列，
        并为每个 span 生成大白话解释。

        Args:
            run_id: 运行 ID。

        Returns:
            回放列表，每项为 {"span": dict, "plain_text": str, "explanation": str}。
        """
        spans: list[TraceSpan] = self.storage.load_spans(run_id)

        if not spans:
            return []

        result: list[dict] = []
        for span in spans:
            span_dict: dict = {
                "span_id": span.span_id,
                "run_id": span.run_id,
                "parent_span_id": span.parent_span_id,
                "name": span.name,
                "type": span.type,
                "status": span.status,
                "started_at": span.started_at,
                "ended_at": span.ended_at,
                "latency_ms": span.latency_ms,
                "input_tokens": span.input_tokens,
                "output_tokens": span.output_tokens,
                "cost_estimate": span.cost_estimate,
                "plain_text": span.plain_text,
            }

            # 生成大白话解释
            event_type = f"{span.type}:{span.status}"
            explanation = self._explainer.explain(event_type)

            result.append({
                "span": span_dict,
                "plain_text": span.plain_text,
                "explanation": explanation,
            })

        return result

    def get_run_summary(self, run_id: str) -> dict:
        """获取 run 摘要。

        包含 task、status、duration、tokens、cost、score 等信息。

        Args:
            run_id: 运行 ID。

        Returns:
            摘要字典，包含以下字段：
            - run_id: 运行 ID。
            - task: 用户任务描述。
            - task_type: 任务类型。
            - status: 运行状态。
            - duration_seconds: 运行耗时（秒），-1 表示未结束。
            - total_input_tokens: 总输入 token 数。
            - total_output_tokens: 总输出 token 数。
            - total_tokens: 总 token 数（输入+输出）。
            - cost_estimate: 预估成本（美元）。
            - overall_score: 综合评分，None 表示未评估。
            - span_count: Span 数量。
            - found: 是否找到该 run。
        """
        record: Optional[RunRecord] = self.storage.get_run(run_id)
        if record is None:
            return {
                "run_id": run_id,
                "task": "",
                "task_type": "",
                "status": "not_found",
                "duration_seconds": -1,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "cost_estimate": 0.0,
                "overall_score": None,
                "span_count": 0,
                "found": False,
            }

        # 计算耗时
        duration: float = -1.0
        if record.ended_at is not None:
            duration = round(record.ended_at - record.started_at, 2)

        # 加载 spans
        spans: list[TraceSpan] = self.storage.load_spans(run_id)
        span_count: int = len(spans)

        return {
            "run_id": record.run_id,
            "task": record.user_task,
            "task_type": record.task_type.value,
            "status": record.status,
            "duration_seconds": duration,
            "total_input_tokens": record.total_input_tokens,
            "total_output_tokens": record.total_output_tokens,
            "total_tokens": record.total_input_tokens + record.total_output_tokens,
            "cost_estimate": record.total_cost_estimate,
            "overall_score": record.overall_score,
            "span_count": span_count,
            "found": True,
        }
