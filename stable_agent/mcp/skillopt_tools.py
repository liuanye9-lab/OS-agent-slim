"""V4 SkillOpt MCP 工具层。
# frozen: V5.6 — 仅兼容保留，严禁新增能力
# @deprecated V6.0: 所有 SkillOpt 工具已迁移到 gateway/unified_tool_registry.py
#   的 _h_skillopt_* handler。本模块计划在 V7.0 移除。

提供 10 个与 Skill 优化相关的 MCP 工具，供 MCP 客户端通过
/mcp/tools/skillopt/ 端点调用。

统一返回结构：
    {"ok": bool, "data": ..., "plain_text": str, "warnings": list}

plain_text 使用中文大白话描述操作结果。
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from stable_agent.skill_optimizer.skill_optimization_engine import (
        SkillOptimizationEngine,
    )

logger = logging.getLogger(__name__)


# ============================================================================
# SkillOptMCPTools — SkillOpt MCP 工具注册中心
# ============================================================================


class SkillOptMCPTools:
    """SkillOpt MCP 工具注册中心。

    将 SkillOptimizationEngine 的方法封装成标准 MCP 工具，
    统一返回 {ok, data, plain_text, warnings} 结构。

    Attributes:
        _engine: SkillOptimizationEngine 实例。
    """

    def __init__(self, engine: SkillOptimizationEngine | None = None) -> None:
        """初始化 MCP 工具层。

        注入 SkillOptimizationEngine；None 时自动创建默认实例。

        Args:
            engine: SkillOptimizationEngine 实例，可选。
        """
        if engine is None:
            from stable_agent.skill_optimizer.skill_optimization_engine import (
                SkillOptimizationEngine,
            )
            engine = SkillOptimizationEngine()
        self._engine: SkillOptimizationEngine = engine

    # ------------------------------------------------------------------
    # 1. get_current_skill
    # ------------------------------------------------------------------

    def get_current_skill(self) -> dict:
        """获取当前 skill 文档内容和版本。

        Returns:
            {ok, data: {version, content, status}, plain_text}
        """
        try:
            skill = self._engine.doc_store.load_current_skill()
            return {
                "ok": True,
                "data": {
                    "version": skill.version,
                    "content": skill.content,
                    "status": skill.status,
                },
                "plain_text": f"当前技能文档版本 {skill.version}，状态 {skill.status}。",
                "warnings": [],
            }
        except FileNotFoundError:
            return {
                "ok": False,
                "data": None,
                "plain_text": "当前技能文档不存在，请先初始化技能文档。",
                "warnings": ["current_skill.md not found"],
            }
        except Exception as e:
            logger.error("get_current_skill 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"获取当前技能文档失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 2. get_best_skill
    # ------------------------------------------------------------------

    def get_best_skill(self) -> dict:
        """获取 best skill 文档。

        Returns:
            {ok, data: {version, content}, plain_text}
        """
        try:
            skill = self._engine.doc_store.load_best_skill()
            if skill is None:
                return {
                    "ok": True,
                    "data": None,
                    "plain_text": "还没有最优技能文档，请先运行一轮优化。",
                    "warnings": ["best skill not yet generated"],
                }
            return {
                "ok": True,
                "data": {
                    "version": skill.version,
                    "content": skill.content,
                },
                "plain_text": f"最优技能文档版本 {skill.version}，已验证通过。",
                "warnings": [],
            }
        except Exception as e:
            logger.error("get_best_skill 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"获取最优技能文档失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 3. submit_user_feedback
    # ------------------------------------------------------------------

    def submit_user_feedback(self, run_id: str, feedback: str) -> dict:
        """提交用户反馈到指定 run。

        用于标记 accepted/edited/rejected。

        Args:
            run_id: 运行 ID。
            feedback: 反馈内容（"accepted", "edited", "rejected"）。

        Returns:
            {ok, plain_text}
        """
        if not run_id:
            return {
                "ok": False,
                "data": None,
                "plain_text": "run_id 不能为空。",
                "warnings": ["missing run_id"],
            }
        if feedback not in ("accepted", "edited", "rejected"):
            return {
                "ok": False,
                "data": None,
                "plain_text": (
                    f"反馈类型「{feedback}」无效，"
                    f"支持：accepted, edited, rejected。"
                ),
                "warnings": [f"invalid feedback type: {feedback}"],
            }

        try:
            # 通过 optimizer_memory 记录反馈
            self._engine.optimizer_memory.record_feedback(
                run_id=run_id, feedback=feedback
            )
            feedback_map = {
                "accepted": "已采纳",
                "edited": "已编辑",
                "rejected": "已拒绝",
            }
            return {
                "ok": True,
                "data": {"run_id": run_id, "feedback": feedback},
                "plain_text": (
                    f"用户对运行 {run_id} 的反馈已记录："
                    f"{feedback_map.get(feedback, feedback)}。"
                ),
                "warnings": [],
            }
        except Exception as e:
            logger.error("submit_user_feedback 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"记录用户反馈失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 4. collect_rollout
    # ------------------------------------------------------------------

    def collect_rollout(self, run_id: str) -> dict:
        """从指定 run 采集轨迹。

        Args:
            run_id: 运行 ID。

        Returns:
            {ok, data: {trajectory}, plain_text}
        """
        if not run_id:
            return {
                "ok": False,
                "data": None,
                "plain_text": "run_id 不能为空。",
                "warnings": ["missing run_id"],
            }

        try:
            if self._engine.rollout_collector is not None:
                trajectory = (
                    self._engine.rollout_collector.collect_by_run(run_id)
                )
                if trajectory is not None:
                    return {
                        "ok": True,
                        "data": {
                            "trajectory": {
                                "id": trajectory.id,
                                "task_input": trajectory.task_input,
                                "task_type": trajectory.task_type,
                                "user_feedback": trajectory.user_feedback,
                                "eval_scores": trajectory.eval_scores,
                            }
                        },
                        "plain_text": (
                            f"已采集运行 {run_id} 的轨迹，"
                            f"反馈类型：{trajectory.user_feedback}。"
                        ),
                        "warnings": [],
                    }
            return {
                "ok": False,
                "data": None,
                "plain_text": f"未找到运行 {run_id} 的轨迹数据。",
                "warnings": ["trajectory not found"],
            }
        except Exception as e:
            logger.error("collect_rollout 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"采集轨迹失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 5. run_skill_optimization_epoch
    # ------------------------------------------------------------------

    def run_skill_optimization_epoch(
        self, max_rollouts: int = 40
    ) -> dict:
        """运行一个完整的 Skill 优化 epoch。

        Args:
            max_rollouts: 最大 rollout 数，默认 40。

        Returns:
            {ok, data: {validation_result}, plain_text}
        """
        try:
            result = self._engine.run_epoch(max_rollouts=max_rollouts)

            if result is None:
                return {
                    "ok": True,
                    "data": {
                        "validation_result": None,
                        "skipped": True,
                    },
                    "plain_text": (
                        "优化回合已跳过：数据不足（需要至少 10 条轨迹）"
                        "或当前技能文档不存在。"
                    ),
                    "warnings": ["epoch skipped: insufficient data"],
                }

            return {
                "ok": True,
                "data": {
                    "validation_result": {
                        "passed": result.passed,
                        "baseline_score": result.baseline_score,
                        "candidate_score": result.candidate_score,
                        "score_delta": result.score_delta,
                        "candidate_skill_version": (
                            result.candidate_skill_version
                        ),
                        "regression_cases": result.regression_cases,
                    }
                },
                "plain_text": (
                    f"优化回合完成！"
                    f"验证{'通过 ✅' if result.passed else '未通过 ❌'}，"
                    f"基线评分 {result.baseline_score:.2f}，"
                    f"候选评分 {result.candidate_score:.2f}，"
                    f"变化 {result.score_delta:+.2f}。"
                ),
                "warnings": [],
            }
        except Exception as e:
            logger.error("run_skill_optimization_epoch 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"运行优化回合失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 6. validate_candidate_skill
    # ------------------------------------------------------------------

    def validate_candidate_skill(
        self, candidate_version: str
    ) -> dict:
        """验证候选 skill 版本。

        Args:
            candidate_version: 候选版本号。

        Returns:
            {ok, data: {validation_result}, plain_text}
        """
        if not candidate_version:
            return {
                "ok": False,
                "data": None,
                "plain_text": "candidate_version 不能为空。",
                "warnings": ["missing candidate_version"],
            }

        try:
            current_skill = self._engine.doc_store.load_current_skill()
            candidate_skill = self._engine.doc_store.load_candidate_skill(
                candidate_version
            )
            if candidate_skill is None:
                return {
                    "ok": False,
                    "data": None,
                    "plain_text": (
                        f"候选版本 {candidate_version} 不存在。"
                    ),
                    "warnings": ["candidate version not found"],
                }

            result = self._engine.validation_gate.validate(
                current_skill, candidate_skill
            )

            return {
                "ok": True,
                "data": {
                    "validation_result": {
                        "passed": result.passed,
                        "baseline_score": result.baseline_score,
                        "candidate_score": result.candidate_score,
                        "score_delta": result.score_delta,
                    }
                },
                "plain_text": (
                    f"验证{'通过 ✅' if result.passed else '未通过 ❌'}，"
                    f"基线 {result.baseline_score:.2f} → "
                    f"候选 {result.candidate_score:.2f}"
                    f"（{result.score_delta:+.2f}）。"
                ),
                "warnings": [],
            }
        except Exception as e:
            logger.error("validate_candidate_skill 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"验证候选技能失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 7. export_best_skill
    # ------------------------------------------------------------------

    def export_best_skill(self) -> dict:
        """导出 best_skill.md。

        Returns:
            {ok, data: {path}, plain_text}
        """
        try:
            path = self._engine.export_best_skill()
            if path is None:
                return {
                    "ok": False,
                    "data": None,
                    "plain_text": "导出失败：没有可导出的最优技能文档。",
                    "warnings": ["no best skill to export"],
                }
            return {
                "ok": True,
                "data": {"path": path},
                "plain_text": f"最优技能文档已导出到 {path}。",
                "warnings": [],
            }
        except Exception as e:
            logger.error("export_best_skill 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"导出失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 8. get_skill_diff
    # ------------------------------------------------------------------

    def get_skill_diff(
        self, old_version: str, new_version: str
    ) -> dict:
        """获取两个版本之间的 diff。

        Args:
            old_version: 旧版本号。
            new_version: 新版本号。

        Returns:
            {ok, data: {diff}, plain_text}
        """
        if not old_version or not new_version:
            return {
                "ok": False,
                "data": None,
                "plain_text": "old_version 和 new_version 都不能为空。",
                "warnings": ["missing version parameters"],
            }

        try:
            diff = self._engine.doc_store.compute_diff(
                old_version, new_version
            )
            return {
                "ok": True,
                "data": {"diff": diff},
                "plain_text": (
                    f"已计算版本 {old_version} → {new_version} 的差异。"
                ),
                "warnings": [],
            }
        except Exception as e:
            logger.error("get_skill_diff 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"计算差异失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 9. list_rejected_edits
    # ------------------------------------------------------------------

    def list_rejected_edits(self) -> dict:
        """列出被拒绝的编辑。

        Returns:
            {ok, data: {edits}, plain_text}
        """
        try:
            edits = self._engine.rejected_buffer.list_rejected()
            return {
                "ok": True,
                "data": {
                    "edits": [
                        {
                            "id": e.id,
                            "op": e.op,
                            "target": e.target,
                            "reason": getattr(e, "reason", ""),
                        }
                        for e in edits
                    ],
                    "count": len(edits),
                },
                "plain_text": (
                    f"共有 {len(edits)} 条被拒绝的编辑记录在废纸篓中。"
                ),
                "warnings": [],
            }
        except Exception as e:
            logger.error("list_rejected_edits 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"获取被拒绝编辑列表失败：{e}",
                "warnings": [str(e)],
            }

    # ------------------------------------------------------------------
    # 10. get_optimization_status
    # ------------------------------------------------------------------

    def get_optimization_status(self) -> dict:
        """获取优化引擎状态摘要。

        Returns:
            {ok, data: {total_rollouts, last_epoch, best_version, ...},
             plain_text}
        """
        try:
            total_epochs = self._engine._epoch_count
            accepted_count = len(self._engine._accepted_patches)
            rejected_count = len(self._engine._rejected_patches)
            longitudinal_count = len(
                self._engine._longitudinal_results
            )

            # 尝试获取 best skill 版本
            best_version = "未生成"
            try:
                best = self._engine.doc_store.load_best_skill()
                if best is not None:
                    best_version = best.version
            except Exception as e:
                logger.warning("获取 skill 版本失败，使用默认值: %s", e)
                pass

            # 尝试获取当前 skill 版本
            current_version = "未知"
            try:
                current = self._engine.doc_store.load_current_skill()
                current_version = current.version
            except Exception as e:
                logger.warning("获取 skill 版本失败，使用默认值: %s", e)
                pass

            return {
                "ok": True,
                "data": {
                    "total_epochs": total_epochs,
                    "accepted_patches": accepted_count,
                    "rejected_patches": rejected_count,
                    "longitudinal_entries": longitudinal_count,
                    "best_version": best_version,
                    "current_version": current_version,
                },
                "plain_text": (
                    f"SkillOpt 引擎状态：已运行 {total_epochs} 个优化回合，"
                    f"通过 {accepted_count} 次、拒绝 {rejected_count} 次。"
                    f"当前版本 {current_version}，"
                    f"最优版本 {best_version}。"
                ),
                "warnings": [],
            }
        except Exception as e:
            logger.error("get_optimization_status 失败: %s", e)
            return {
                "ok": False,
                "data": None,
                "plain_text": f"获取优化状态失败：{e}",
                "warnings": [str(e)],
            }
