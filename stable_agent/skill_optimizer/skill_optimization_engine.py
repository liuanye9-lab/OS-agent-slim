"""V4 总控引擎（SkillOptimizationEngine）。

管理 Skill Optimization 优化循环的完整流程，协调所有子组件。
支持完整 epoch 运行和单步运行两种模式。
"""

from __future__ import annotations

import logging
import statistics
import time
import uuid
from datetime import datetime
from typing import Any, TYPE_CHECKING

from stable_agent.skill_optimizer.models import (
    RolloutTrajectory,
    SkillDocument,
    SkillPatch,
    ValidationResult,
)
from stable_agent.models import Event

if TYPE_CHECKING:
    from stable_agent.skill_optimizer.skill_document_store import (
        SkillDocumentStore,
    )
    from stable_agent.skill_optimizer.patch_merger import PatchMerger
    from stable_agent.skill_optimizer.patch_ranker import PatchRanker
    from stable_agent.skill_optimizer.patch_applier import PatchApplier
    from stable_agent.skill_optimizer.validation_gate import ValidationGate
    from stable_agent.skill_optimizer.rejected_edit_buffer import (
        RejectedEditBuffer,
    )
    from stable_agent.skill_optimizer.slow_meta_update import SlowMetaUpdater
    from stable_agent.skill_optimizer.optimizer_memory import OptimizerMemory
    from stable_agent.skill_optimizer.skill_exporter import SkillExporter
    from stable_agent.trace_event_bus import EventBus

logger = logging.getLogger(__name__)


class SkillOptimizationEngine:
    """V4 总控引擎。

    管理 SkillOpt 优化循环的完整流程：

    回合流程：
    1. 加载 current_skill
    2. 加载最近 rollout
    3. 分成功/失败
    4. 失败分析 → failure_patch
    5. 成功分析 → success_patch
    6. 合并 patch
    7. 排序截断（edit_budget）
    8. 应用 patch → candidate_skill
    9. 用 validation gate 验证
    10. 通过则 promote current/best
    11. 不通过则写入 rejected buffer
    12. 周期性生成 slow/meta update
    13. 导出 best_skill.md
    """

    def __init__(
        self,
        doc_store: SkillDocumentStore | None = None,
        rollout_collector: Any = None,
        intent_extractor: Any = None,
        analyzer: Any = None,
        merger: PatchMerger | None = None,
        ranker: PatchRanker | None = None,
        applier: PatchApplier | None = None,
        validation_gate: ValidationGate | None = None,
        rejected_buffer: RejectedEditBuffer | None = None,
        slow_updater: SlowMetaUpdater | None = None,
        optimizer_memory: OptimizerMemory | None = None,
        skill_exporter: SkillExporter | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """初始化引擎，所有依赖通过构造函数注入。

        None 时自动创建默认实例。

        Args:
            doc_store: SkillDocumentStore 实例。
            rollout_collector: RolloutCollector 实例（T02 实现）。
            intent_extractor: IntentSignalExtractor 实例（T02 实现）。
            analyzer: SuccessFailureAnalyzer 实例（T03 实现）。
            merger: PatchMerger 实例。
            ranker: PatchRanker 实例。
            applier: PatchApplier 实例。
            validation_gate: ValidationGate 实例。
            rejected_buffer: RejectedEditBuffer 实例。
            slow_updater: SlowMetaUpdater 实例。
            optimizer_memory: OptimizerMemory 实例。
            skill_exporter: SkillExporter 实例。
            event_bus: EventBus 实例。
        """
        # 核心依赖（延迟导入避免循环）
        if doc_store is None:
            from stable_agent.skill_optimizer.skill_document_store import (
                SkillDocumentStore,
            )
            doc_store = SkillDocumentStore()
        if merger is None:
            from stable_agent.skill_optimizer.patch_merger import PatchMerger
            merger = PatchMerger()
        if ranker is None:
            from stable_agent.skill_optimizer.patch_ranker import PatchRanker
            ranker = PatchRanker()
        if applier is None:
            from stable_agent.skill_optimizer.patch_applier import PatchApplier
            applier = PatchApplier()
        if validation_gate is None:
            from stable_agent.skill_optimizer.validation_gate import (
                ValidationGate,
            )
            validation_gate = ValidationGate()
        if rejected_buffer is None:
            from stable_agent.skill_optimizer.rejected_edit_buffer import (
                RejectedEditBuffer,
            )
            rejected_buffer = RejectedEditBuffer()
        if slow_updater is None:
            from stable_agent.skill_optimizer.slow_meta_update import (
                SlowMetaUpdater,
            )
            slow_updater = SlowMetaUpdater()
        if optimizer_memory is None:
            from stable_agent.skill_optimizer.optimizer_memory import (
                OptimizerMemory,
            )
            optimizer_memory = OptimizerMemory()
        if skill_exporter is None:
            from stable_agent.skill_optimizer.skill_exporter import (
                SkillExporter,
            )
            skill_exporter = SkillExporter(doc_store)

        self.doc_store: SkillDocumentStore = doc_store
        self.rollout_collector: Any = rollout_collector
        self.intent_extractor: Any = intent_extractor
        self.analyzer: Any = analyzer
        self.merger: PatchMerger = merger
        self.ranker: PatchRanker = ranker
        self.applier: PatchApplier = applier
        self.validation_gate: ValidationGate = validation_gate
        self.rejected_buffer: RejectedEditBuffer = rejected_buffer
        self.slow_updater: SlowMetaUpdater = slow_updater
        self.optimizer_memory: OptimizerMemory = optimizer_memory
        self.skill_exporter: SkillExporter = skill_exporter
        self.event_bus: EventBus | None = event_bus

        # 内部状态
        self._epoch_count: int = 0
        self._longitudinal_results: list[dict] = []
        self._accepted_patches: list[SkillPatch] = []
        self._rejected_patches: list[SkillPatch] = []

    # ------------------------------------------------------------------
    # 完整 Epoch
    # ------------------------------------------------------------------

    def run_epoch(
        self,
        max_rollouts: int = 40,
        reflection_batch_size: int = 8,
        edit_budget: int = 4,
    ) -> ValidationResult | None:
        """完整运行一个优化 epoch。

        不足 10 条轨迹时不执行。

        Args:
            max_rollouts: 最大收集的 rollout 数。
            reflection_batch_size: 反思批次大小。
            edit_budget: 编辑预算（保留编辑数）。

        Returns:
            ValidationResult 如果成功执行，None 如果数据不足跳过。
        """
        self._epoch_count += 1
        epoch_id = self._epoch_count

        logger.info(
            "=== Epoch %d 开始 (max_rollouts=%d, edit_budget=%d) ===",
            epoch_id, max_rollouts, edit_budget,
        )

        self._publish_event("skillopt.epoch_started", {
            "epoch": epoch_id,
            "max_rollouts": max_rollouts,
            "edit_budget": edit_budget,
        })

        # 步骤 1: 加载 current skill
        try:
            current_skill = self.doc_store.load_current_skill()
        except FileNotFoundError:
            logger.error("current_skill.md 不存在，无法运行 epoch")
            return None

        # 步骤 2: 加载最近 rollout
        rollouts = self._collect_rollouts(max_rollouts)
        self._publish_event("skillopt.rollouts_collected", {
            "epoch": epoch_id,
            "count": len(rollouts),
        })

        # 不足时跳过
        if len(rollouts) < 10:
            logger.info(
                "Epoch %d 跳过：rollout 数量不足（%d < 10）",
                epoch_id, len(rollouts),
            )
            return None

        # 步骤 3-11: 运行核心循环
        result = self.run_step(rollouts, edit_budget)

        # 步骤 12: 周期性慢更新
        if result is not None:
            self._try_slow_update(current_skill, result)

        # 步骤 13: 导出
        if result is not None and result.passed:
            self._publish_event("skillopt.best_skill_exported", {
                "epoch": epoch_id,
                "version": result.candidate_skill_version,
            })
            self.skill_exporter.export()

        logger.info("=== Epoch %d 结束 ===", epoch_id)
        return result

    # ------------------------------------------------------------------
    # 单步运行
    # ------------------------------------------------------------------

    def run_step(
        self,
        rollouts: list[RolloutTrajectory],
        edit_budget: int = 4,
    ) -> ValidationResult | None:
        """单步运行（使用已收集的 rollouts，不重新加载）。

        用于测试和手动控制场景。

        Args:
            rollouts: 已收集的 RolloutTrajectory 列表。
            edit_budget: 编辑预算。

        Returns:
            ValidationResult 或 None。
        """
        if not rollouts:
            logger.warning("run_step: 无 rollout 数据")
            return None

        # 加载 current skill
        try:
            current_skill = self.doc_store.load_current_skill()
        except FileNotFoundError:
            logger.error("current_skill.md 不存在")
            return None

        # 步骤 3: 分成功/失败
        failures, successes = self._split_rollouts(rollouts)

        # 步骤 4: 失败分析
        failure_patch = self._analyze_failures(failures)
        if failure_patch is not None:
            self._publish_event("skillopt.failures_analyzed", {
                "failure_count": len(failures),
                "edit_count": len(failure_patch.edits),
            })

        # 步骤 5: 成功分析
        success_patch = self._analyze_successes(successes)
        if success_patch is not None:
            self._publish_event("skillopt.successes_analyzed", {
                "success_count": len(successes),
                "edit_count": len(success_patch.edits),
            })

        # 步骤 6: 合并
        merged_patch = self.merger.merge(failure_patch, success_patch)
        self._publish_event("skillopt.patch_merged", {
            "edit_count": len(merged_patch.edits),
        })

        # 步骤 7: 排序截断
        ranked_patch = self.ranker.rank(merged_patch, edit_budget)
        self._publish_event("skillopt.patch_ranked", {
            "original_count": len(merged_patch.edits),
            "ranked_count": len(ranked_patch.edits),
            "budget": edit_budget,
        })

        # 步骤 8: 应用 patch
        candidate_skill = self.applier.apply(current_skill, ranked_patch)
        self._publish_event("skillopt.candidate_created", {
            "version": candidate_skill.version,
            "edit_count": len(ranked_patch.edits),
        })

        # 步骤 9: 验证
        result = self.validation_gate.validate(current_skill, candidate_skill)

        if result.passed:
            # 步骤 10a: 通过 → promote
            self._publish_event("skillopt.validation_passed", {
                "baseline_score": result.baseline_score,
                "candidate_score": result.candidate_score,
                "score_delta": result.score_delta,
            })

            # 保存候选版本
            candidate_skill.status = "best"
            self.doc_store.save_candidate_skill(candidate_skill)
            # 提升为 best
            self.doc_store.promote_to_best(candidate_skill.version)

            self._accepted_patches.append(ranked_patch)
        else:
            # 步骤 10b: 不通过 → rejected buffer
            self._publish_event("skillopt.validation_failed", {
                "baseline_score": result.baseline_score,
                "candidate_score": result.candidate_score,
                "score_delta": result.score_delta,
                "regression_cases": result.regression_cases,
            })

            self.rejected_buffer.add_rejected(
                ranked_patch.edits, result
            )
            self._publish_event("skillopt.rejected_buffer_updated", {
                "rejected_count": len(ranked_patch.edits),
            })

            self._rejected_patches.append(ranked_patch)

        # 记录纵向结果
        self._record_longitudinal_result(result)

        return result

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export_best_skill(self) -> str | None:
        """导出 best_skill.md 的路径。

        Returns:
            导出文件的绝对路径，或 None（如果不存在）。
        """
        try:
            return self.skill_exporter.export()
        except Exception as e:
            logger.error("导出 best_skill 失败: %s", e)
            return None

    # ------------------------------------------------------------------
    # 内部：Rollout 收集
    # ------------------------------------------------------------------

    def _collect_rollouts(
        self, max_count: int
    ) -> list[RolloutTrajectory]:
        """收集最近 rollouts。

        如果 rollout_collector 已注入，使用它；否则返回空列表。

        Args:
            max_count: 最大收集数。

        Returns:
            RolloutTrajectory 列表。
        """
        if self.rollout_collector is not None:
            try:
                return self.rollout_collector.collect(max_count=max_count)
            except Exception as e:
                logger.error("RolloutCollector 收集失败: %s", e)
                return []

        # 无 collector 时尝试从 data/rollouts 目录加载
        return self._load_rollouts_from_disk(max_count)

    @staticmethod
    def _load_rollouts_from_disk(
        max_count: int,
    ) -> list[RolloutTrajectory]:
        """从磁盘加载 rollouts（回退策略）。

        Args:
            max_count: 最大加载数。

        Returns:
            RolloutTrajectory 列表。
        """
        import json
        import os
        from pathlib import Path

        rollouts_dir = Path("data/rollouts")
        if not rollouts_dir.exists():
            return []

        rollouts: list[RolloutTrajectory] = []
        jsonl_files = sorted(
            rollouts_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for jsonl_file in jsonl_files:
            if len(rollouts) >= max_count:
                break
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if len(rollouts) >= max_count:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            rollout = RolloutTrajectory(
                                id=data.get("id", str(uuid.uuid4())),
                                task_input=data.get("task_input", ""),
                                task_type=data.get("task_type", ""),
                                user_intent_guess=data.get(
                                    "user_intent_guess", ""
                                ),
                                context_pack=data.get("context_pack", ""),
                                skill_version=data.get("skill_version", ""),
                                model_output=data.get("model_output", ""),
                                user_feedback=data.get(
                                    "user_feedback", "unknown"
                                ),
                                eval_scores=data.get("eval_scores", {}),
                                trace_events=data.get("trace_events", []),
                                token_usage=data.get("token_usage", {}),
                            )
                            rollouts.append(rollout)
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception as e:
                logger.warning("读取 rollout 文件失败: %s - %s", jsonl_file, e)
                continue

        return rollouts[:max_count]

    # ------------------------------------------------------------------
    # 内部：分成功/失败
    # ------------------------------------------------------------------

    @staticmethod
    def _split_rollouts(
        rollouts: list[RolloutTrajectory],
    ) -> tuple[list[RolloutTrajectory], list[RolloutTrajectory]]:
        """将 rollouts 分为失败和成功两组。

        失败 = user_feedback 为 "rejected" 或 "edited"
        成功 = user_feedback 为 "accepted" 或 "unknown"（偏向乐观）

        Args:
            rollouts: RolloutTrajectory 列表。

        Returns:
            (failures, successes) 元组。
        """
        failures: list[RolloutTrajectory] = []
        successes: list[RolloutTrajectory] = []

        for r in rollouts:
            if r.user_feedback in ("rejected", "edited"):
                failures.append(r)
            else:
                successes.append(r)

        return failures, successes

    # ------------------------------------------------------------------
    # 内部：分析
    # ------------------------------------------------------------------

    def _analyze_failures(
        self, rollouts: list[RolloutTrajectory]
    ) -> SkillPatch | None:
        """分析失败 rollouts，生成 failure_patch。

        如果 analyzer 已注入，使用它；否则返回 None。

        Args:
            rollouts: 失败的 RolloutTrajectory 列表。

        Returns:
            SkillPatch 或 None。
        """
        if not rollouts:
            return None

        if self.analyzer is not None:
            try:
                return self.analyzer.analyze_failures(rollouts)
            except Exception as e:
                logger.error("失败分析失败: %s", e)
                return None

        return None

    def _analyze_successes(
        self, rollouts: list[RolloutTrajectory]
    ) -> SkillPatch | None:
        """分析成功 rollouts，生成 success_patch。

        如果 analyzer 已注入，使用它；否则返回 None。

        Args:
            rollouts: 成功的 RolloutTrajectory 列表。

        Returns:
            SkillPatch 或 None。
        """
        if not rollouts:
            return None

        if self.analyzer is not None:
            try:
                return self.analyzer.analyze_successes(rollouts)
            except Exception as e:
                logger.error("成功分析失败: %s", e)
                return None

        return None

    # ------------------------------------------------------------------
    # 内部：慢更新
    # ------------------------------------------------------------------

    def _try_slow_update(
        self,
        current_skill: SkillDocument,
        result: ValidationResult,
    ) -> None:
        """尝试生成慢更新。

        条件：
        - 有足够的纵向数据
        - 结果稳定
        - 存在长期模式

        Args:
            current_skill: 当前 skill。
            result: 本轮验证结果。
        """
        if len(self._longitudinal_results) < self.slow_updater.min_epochs:
            return

        # 加载 previous skill（上一个版本的 best skill 或 current）
        previous_skill = self.doc_store.load_best_skill()
        if previous_skill is None:
            previous_skill = current_skill

        slow_patch = self.slow_updater.generate_slow_update(
            previous_skill=previous_skill,
            current_skill=current_skill,
            longitudinal_results=self._longitudinal_results,
        )

        if slow_patch is not None:
            self._publish_event("skillopt.slow_update_created", {
                "edit_count": len(slow_patch.edits),
                "epoch": self._epoch_count,
            })

            # 应用慢更新到 current skill
            updated_skill = self.applier.apply(current_skill, slow_patch)
            self.doc_store.save_candidate_skill(updated_skill)
            logger.info("慢更新已应用，版本 %s", updated_skill.version)

    # ------------------------------------------------------------------
    # 内部：纵向记录
    # ------------------------------------------------------------------

    def _record_longitudinal_result(
        self, result: ValidationResult
    ) -> None:
        """记录本 epoch 的结果用于纵向分析。

        Args:
            result: 验证结果。
        """
        entry = {
            "epoch": self._epoch_count,
            "accepted_count": 1 if result.passed else 0,
            "rejected_count": 0 if result.passed else 1,
            "avg_score": result.candidate_score,
            "score_delta": result.score_delta,
        }
        self._longitudinal_results.append(entry)

    # ------------------------------------------------------------------
    # 内部：事件发布
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: dict) -> None:
        """通过 event_bus 发布事件。

        如果 event_bus 为 None，静默跳过。

        Args:
            event_type: 事件类型字符串。
            payload: 事件负载。
        """
        if self.event_bus is None:
            return

        try:
            event = Event(
                timestamp=time.time(),
                type=event_type,
                payload=payload,
            )
            self.event_bus.publish(event)
        except Exception as e:
            logger.debug("事件发布失败 (%s): %s", event_type, e)
