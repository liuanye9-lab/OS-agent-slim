"""Rollout 轨迹采集器。

从工作流运行中收集轨迹数据，负责采集、保存、拆分成功/失败。
成功/失败判断基于 overall_score 和 user_feedback。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from stable_agent.skill_optimizer.models import RolloutTrajectory

logger = logging.getLogger(__name__)


class RolloutCollector:
    """从工作流运行中收集轨迹数据。

    负责从 orchestrator 采集运行记录、TraceSpan 和评估结果，
    组装为完整的 RolloutTrajectory，持久化到磁盘并按成功/失败拆分。

    Attributes:
        storage_dir: 轨迹存储目录路径。
        storage_path: 存储目录的 Path 对象。
    """

    def __init__(self, storage_dir: str = "data/rollouts") -> None:
        """初始化存储目录，自动创建。

        Args:
            storage_dir: 轨迹文件存储目录的路径。
        """
        self.storage_dir = storage_dir
        self.storage_path = Path(storage_dir).resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info("RolloutCollector 存储目录已就绪: %s", self.storage_path)

    def collect_from_workflow_run(
        self, run_id: str, orchestrator: Any = None
    ) -> Optional[RolloutTrajectory]:
        """从现有 workflow run 采集轨迹数据。

        需要访问：
        - orchestrator.storage.get_run(run_id) → RunRecord
        - orchestrator.trace_event_bus.get_spans_by_run(run_id) → TraceSpan 列表
        - orchestrator 存储的上下文包和评估结果

        Args:
            run_id: 运行 ID。
            orchestrator: Orchestrator 实例，如果为 None 则创建最小轨迹。

        Returns:
            完整的 RolloutTrajectory 或 None（采集失败）。
        """
        if orchestrator is None:
            # 创建最小 RolloutTrajectory（使用当前时间戳作 id）
            trajectory = RolloutTrajectory(
                id=f"minimal-{uuid.uuid4().hex[:8]}",
                task_input="",
                task_type="general_qa",
                created_at=datetime.now(),
            )
            logger.info("orchestrator 为 None，创建最小轨迹: %s", trajectory.id)
            return trajectory

        try:
            # 1. 获取运行记录
            run_record = None
            if hasattr(orchestrator, "storage") and hasattr(orchestrator.storage, "get_run"):
                run_record = orchestrator.storage.get_run(run_id)

            # 2. 获取 TraceSpan 列表
            trace_events: list[dict[str, Any]] = []
            if hasattr(orchestrator, "trace_event_bus") and hasattr(
                orchestrator.trace_event_bus, "get_spans_by_run"
            ):
                spans = orchestrator.trace_event_bus.get_spans_by_run(run_id)
                for span in spans:
                    trace_events.append({
                        "span_id": getattr(span, "span_id", ""),
                        "name": getattr(span, "name", ""),
                        "type": getattr(span, "type", ""),
                        "status": getattr(span, "status", ""),
                        "latency_ms": getattr(span, "latency_ms", None),
                        "input_tokens": getattr(span, "input_tokens", 0),
                        "output_tokens": getattr(span, "output_tokens", 0),
                        "plain_text": getattr(span, "plain_text", ""),
                    })

            # 3. 提取核心字段
            task_input = ""
            task_type = "general_qa"
            user_feedback: str = "unknown"
            model_output = ""
            context_pack = ""
            skill_version = ""
            eval_scores: dict[str, float] = {}

            if run_record is not None:
                task_input = getattr(run_record, "user_task", "")
                task_type = getattr(run_record, "task_type", "general_qa")
                if hasattr(task_type, "value"):
                    task_type = task_type.value

                # 尝试从 context_pack 获取模型输出
                if hasattr(orchestrator, "context_pack"):
                    cp = orchestrator.context_pack
                    model_output = getattr(cp, "volatile_context", "") or ""

                # 尝试获取评估结果
                if hasattr(orchestrator, "evaluation_result"):
                    ev = orchestrator.evaluation_result
                    if ev is not None:
                        eval_scores = {
                            "completion_rate": getattr(ev, "completion_rate", 0.0),
                            "context_hit_rate": getattr(ev, "context_hit_rate", 0.0),
                            "token_efficiency": getattr(ev, "token_efficiency", 0.0),
                            "hallucination_score": getattr(ev, "hallucination_score", 0.0),
                            "user_preference_score": getattr(ev, "user_preference_score", 0.0),
                            "overall_score": getattr(ev, "overall_score", 0.0),
                            "retrieval_quality": getattr(ev, "retrieval_quality", 0.0),
                            "memory_quality": getattr(ev, "memory_quality", 0.0),
                            "tool_quality": getattr(ev, "tool_quality", 0.0),
                            "format_quality": getattr(ev, "format_quality", 0.0),
                            "safety_score": getattr(ev, "safety_score", 1.0),
                        }

            # 4. 计算 token_usage
            total_input = sum(e.get("input_tokens", 0) for e in trace_events)
            total_output = sum(e.get("output_tokens", 0) for e in trace_events)
            token_usage = {
                "total_input": total_input,
                "total_output": total_output,
            }

            trajectory = RolloutTrajectory(
                id=run_id,
                task_input=task_input,
                task_type=task_type,
                user_intent_guess="",
                context_pack=context_pack,
                skill_version=skill_version,
                model_output=model_output,
                user_feedback=user_feedback,  # type: ignore[arg-type]
                eval_scores=eval_scores,
                trace_events=trace_events,
                token_usage=token_usage,
                created_at=datetime.now(),
            )

            logger.info("从 workflow run %s 采集轨迹完成", run_id)
            return trajectory

        except Exception as exc:
            logger.error("从 workflow run %s 采集轨迹失败: %s", run_id, exc)
            return None

    def save_rollout(self, trajectory: RolloutTrajectory) -> None:
        """保存轨迹到 data/rollouts/<id>.json。

        Args:
            trajectory: 要保存的 RolloutTrajectory。
        """
        file_path = self.storage_path / f"{trajectory.id}.json"
        data = self._serialize_trajectory(trajectory)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("轨迹已保存: %s", file_path)

    def load_recent_rollouts(self, limit: int = 50) -> list[RolloutTrajectory]:
        """加载最近轨迹。按 created_at 降序。

        Args:
            limit: 最大加载数量，默认 50。

        Returns:
            按时间降序排列的 RolloutTrajectory 列表。
        """
        if not self.storage_path.exists():
            return []

        # 收集所有 JSON 文件
        json_files = sorted(
            self.storage_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        trajectories: list[RolloutTrajectory] = []
        for file_path in json_files[:limit]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                trajectory = self._deserialize_trajectory(data)
                trajectories.append(trajectory)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("跳过无效轨迹文件 %s: %s", file_path, exc)
                continue

        # 确保按 created_at 降序
        trajectories.sort(key=lambda t: t.created_at, reverse=True)
        return trajectories[:limit]

    def split_success_failure(
        self, rollouts: list[RolloutTrajectory]
    ) -> tuple[list[RolloutTrajectory], list[RolloutTrajectory]]:
        """拆分成功/失败轨迹。

        成功条件（任一满足）：
        - eval_scores 中 overall_score >= 0.8
        - user_feedback == "accepted"

        失败条件（任一满足）：
        - eval_scores 中 overall_score < 0.65
        - user_feedback == "rejected"

        中间态不进入任何一组。

        Args:
            rollouts: 要拆分的轨迹列表。

        Returns:
            (successes, failures) 元组。
        """
        successes: list[RolloutTrajectory] = []
        failures: list[RolloutTrajectory] = []

        for rollout in rollouts:
            # 先检查 user_feedback
            if rollout.user_feedback == "accepted":
                successes.append(rollout)
                continue
            if rollout.user_feedback == "rejected":
                failures.append(rollout)
                continue

            # 再检查 eval_scores
            overall = rollout.eval_scores.get("overall_score")
            if overall is not None:
                if overall >= 0.8:
                    successes.append(rollout)
                    continue
                if overall < 0.65:
                    failures.append(rollout)
                    continue

            # 中间态：不进入任何一组
            logger.debug(
                "轨迹 %s 为中间态（user_feedback=%s, overall_score=%s），已跳过",
                rollout.id,
                rollout.user_feedback,
                overall,
            )

        return successes, failures

    # ------------------------------------------------------------------
    # 序列化辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_trajectory(trajectory: RolloutTrajectory) -> dict[str, Any]:
        """将 RolloutTrajectory 序列化为可 JSON 序列化的字典。

        Args:
            trajectory: 要序列化的轨迹。

        Returns:
            JSON 兼容的字典。
        """
        return {
            "id": trajectory.id,
            "task_input": trajectory.task_input,
            "task_type": trajectory.task_type,
            "user_intent_guess": trajectory.user_intent_guess,
            "context_pack": trajectory.context_pack,
            "skill_version": trajectory.skill_version,
            "model_output": trajectory.model_output,
            "user_feedback": trajectory.user_feedback,
            "eval_scores": trajectory.eval_scores,
            "trace_events": trajectory.trace_events,
            "token_usage": trajectory.token_usage,
            "created_at": trajectory.created_at.isoformat(),
        }

    @staticmethod
    def _deserialize_trajectory(data: dict[str, Any]) -> RolloutTrajectory:
        """从字典反序列化 RolloutTrajectory。

        Args:
            data: JSON 反序列化后的字典。

        Returns:
            重建的 RolloutTrajectory 实例。
        """
        created_at_str = data.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except (ValueError, TypeError):
            created_at = datetime.now()

        return RolloutTrajectory(
            id=data.get("id", str(uuid.uuid4())),
            task_input=data.get("task_input", ""),
            task_type=data.get("task_type", ""),
            user_intent_guess=data.get("user_intent_guess", ""),
            context_pack=data.get("context_pack", ""),
            skill_version=data.get("skill_version", ""),
            model_output=data.get("model_output", ""),
            user_feedback=data.get("user_feedback", "unknown"),
            eval_scores=data.get("eval_scores", {}),
            trace_events=data.get("trace_events", []),
            token_usage=data.get("token_usage", {}),
            created_at=created_at,
        )
