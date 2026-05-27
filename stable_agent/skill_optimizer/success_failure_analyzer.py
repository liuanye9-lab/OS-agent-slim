"""成功/失败分析器。

分析成功和失败轨迹，生成修复/强化补丁。
使用共性模式发现（≥2 条轨迹出现相同问题）→ 生成 SkillEdit。
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from stable_agent.skill_optimizer.models import (
    RolloutTrajectory,
    SkillDocument,
    SkillEdit,
    SkillPatch,
)

logger = logging.getLogger(__name__)


class SuccessFailureAnalyzer:
    """分析成功和失败轨迹，生成补丁。

    从失败轨迹中发现共性模式生成修复 patch，
    从成功轨迹中发现共性模式生成强化 patch。

    Attributes:
        patch_merger: PatchMerger 实例（可选）。
        patch_ranker: PatchRanker 实例（可选）。
    """

    def __init__(self, patch_merger: Any = None, patch_ranker: Any = None) -> None:
        """初始化分析器。

        Args:
            patch_merger: PatchMerger 实例（可选），用于后续合并。
            patch_ranker: PatchRanker 实例（可选），用于后续排序。
        """
        self.patch_merger = patch_merger
        self.patch_ranker = patch_ranker
        logger.info("SuccessFailureAnalyzer 已初始化")

    def analyze_failures(
        self,
        trajectories: list[RolloutTrajectory],
        current_skill: SkillDocument,
        edit_budget: int = 4,
    ) -> SkillPatch:
        """分析失败轨迹的共性模式生成修复 patch。

        规则：
        1. 只找共性失败（≥2 条轨迹出现相同问题）→ 不为单条轨迹写死规则
        2. 按问题频率排序
        3. 输出不超过 edit_budget 条的 SkillEdit
        4. 每条 edit 的 source_type = "failure"

        Args:
            trajectories: 失败轨迹列表。
            current_skill: 当前技能文档。
            edit_budget: 最大编辑数量，默认 4。

        Returns:
            包含修复编辑的 SkillPatch。
        """
        if not trajectories:
            return SkillPatch(
                id=str(uuid.uuid4()),
                edits=[],
                reasoning="无失败轨迹，跳过分析。",
                source_rollout_ids=[],
            )

        # 使用 _find_pattern 查找共性失败模式
        patterns = self._find_pattern(trajectories, key="failures", min_count=2)

        if not patterns:
            return SkillPatch(
                id=str(uuid.uuid4()),
                edits=[],
                reasoning="未发现共性失败模式（所有问题均为孤立出现）。",
                source_rollout_ids=[t.id for t in trajectories],
            )

        # 按频率排序（降序）
        patterns.sort(key=lambda p: p["count"], reverse=True)

        # 限制 edit 数量
        patterns = patterns[:edit_budget]

        edits: list[SkillEdit] = []
        for pattern in patterns:
            edit = self._generate_edit(pattern, source_type="failure")
            edits.append(edit)

        source_ids = [t.id for t in trajectories]

        return SkillPatch(
            id=str(uuid.uuid4()),
            edits=edits,
            reasoning=(
                f"从 {len(trajectories)} 条失败轨迹中发现 "
                f"{len(patterns)} 个共性模式，生成 {len(edits)} 条修复编辑。"
            ),
            source_rollout_ids=source_ids,
            estimated_impact=0.05 * len(edits),
            estimated_risk=0.0,
        )

    def analyze_successes(
        self,
        trajectories: list[RolloutTrajectory],
        current_skill: SkillDocument,
        edit_budget: int = 4,
    ) -> SkillPatch:
        """分析成功轨迹的共性模式生成强化 patch。

        规则：
        1. 只保留多次复现（≥2 条）的成功模式
        2. 成功模式的 edit 是 append 类型（追加到 skill 末尾）
        3. source_type = "success"

        Args:
            trajectories: 成功轨迹列表。
            current_skill: 当前技能文档。
            edit_budget: 最大编辑数量，默认 4。

        Returns:
            包含强化编辑的 SkillPatch。
        """
        if not trajectories:
            return SkillPatch(
                id=str(uuid.uuid4()),
                edits=[],
                reasoning="无成功轨迹，跳过分析。",
                source_rollout_ids=[],
            )

        # 使用 _find_pattern 查找共性成功模式
        patterns = self._find_pattern(trajectories, key="successes", min_count=2)

        if not patterns:
            return SkillPatch(
                id=str(uuid.uuid4()),
                edits=[],
                reasoning="未发现共性成功模式（所有成功特征均为孤立出现）。",
                source_rollout_ids=[t.id for t in trajectories],
            )

        # 按频率排序（降序）
        patterns.sort(key=lambda p: p["count"], reverse=True)

        # 限制 edit 数量
        patterns = patterns[:edit_budget]

        edits: list[SkillEdit] = []
        for pattern in patterns:
            edit = self._generate_edit(pattern, source_type="success")
            edits.append(edit)

        source_ids = [t.id for t in trajectories]

        return SkillPatch(
            id=str(uuid.uuid4()),
            edits=edits,
            reasoning=(
                f"从 {len(trajectories)} 条成功轨迹中发现 "
                f"{len(patterns)} 个共性模式，生成 {len(edits)} 条强化编辑。"
            ),
            source_rollout_ids=source_ids,
            estimated_impact=0.03 * len(edits),
            estimated_risk=0.0,
        )

    # ------------------------------------------------------------------
    # 模式发现
    # ------------------------------------------------------------------

    def _find_pattern(
        self,
        trajectories: list[RolloutTrajectory],
        key: str,
        min_count: int = 2,
    ) -> list[dict[str, Any]]:
        """通用模式查找。

        对失败轨迹：查看 eval_scores 中哪些维度最低，统计共性。
        对成功轨迹：查看哪些特征多次出现。

        Args:
            trajectories: 轨迹列表。
            key: "failures" 或 "successes"。
            min_count: 最小出现次数阈值，默认 2。

        Returns:
            模式列表，每个元素为 {pattern, count, example_ids}。
        """
        if not trajectories:
            return []

        if key == "failures":
            return self._find_failure_patterns(trajectories, min_count)
        else:
            return self._find_success_patterns(trajectories, min_count)

    def _find_failure_patterns(
        self,
        trajectories: list[RolloutTrajectory],
        min_count: int,
    ) -> list[dict[str, Any]]:
        """从失败轨迹中发现共性低分维度。

        Args:
            trajectories: 失败轨迹列表。
            min_count: 最小出现次数。

        Returns:
            失败模式列表。
        """
        # 统计所有轨迹中每个维度的低分情况
        dimension_low_counts: Counter = Counter()
        dimension_examples: dict[str, list[str]] = defaultdict(list)

        low_threshold = 0.5  # 低于此值视为低分

        for traj in trajectories:
            for dim, score in traj.eval_scores.items():
                if score < low_threshold:
                    dimension_low_counts[dim] += 1
                    dimension_examples[dim].append(traj.id)

        patterns: list[dict[str, Any]] = []
        for dim, count in dimension_low_counts.most_common():
            if count >= min_count:
                # 构建人类可读的描述
                dim_descriptions = {
                    "overall_score": "综合评分偏低",
                    "completion_rate": "任务完成率不足",
                    "context_hit_rate": "上下文命中率低",
                    "token_efficiency": "Token 效率低",
                    "hallucination_score": "幻觉问题",
                    "user_preference_score": "用户偏好匹配度低",
                    "retrieval_quality": "检索质量不足",
                    "memory_quality": "记忆质量不足",
                    "tool_quality": "工具使用质量不足",
                    "format_quality": "输出格式质量不足",
                    "safety_score": "安全问题",
                    "token_roi": "Token 投资回报率低",
                }

                description = dim_descriptions.get(dim, f"维度 '{dim}' 评分偏低")

                patterns.append({
                    "pattern": description,
                    "count": count,
                    "example_ids": dimension_examples[dim][:3],
                    "dimension": dim,
                })

        return patterns

    def _find_success_patterns(
        self,
        trajectories: list[RolloutTrajectory],
        min_count: int,
    ) -> list[dict[str, Any]]:
        """从成功轨迹中发现共性成功模式。

        检查维度高分、task_type 共性、输出长度特征等。

        Args:
            trajectories: 成功轨迹列表。
            min_count: 最小出现次数。

        Returns:
            成功模式列表。
        """
        patterns: list[dict[str, Any]] = []

        # 1. 检查高分维度共性
        dimension_high_counts: Counter = Counter()
        dimension_examples: dict[str, list[str]] = defaultdict(list)
        high_threshold = 0.85

        for traj in trajectories:
            for dim, score in traj.eval_scores.items():
                if score >= high_threshold:
                    dimension_high_counts[dim] += 1
                    dimension_examples[dim].append(traj.id)

        for dim, count in dimension_high_counts.most_common():
            if count >= min_count:
                dim_descriptions = {
                    "overall_score": "综合评分始终较高",
                    "completion_rate": "任务完成率较高",
                    "context_hit_rate": "上下文命中率较高",
                    "token_efficiency": "Token 效率较高",
                    "format_quality": "输出格式质量较高",
                    "safety_score": "安全评分较高",
                }

                description = dim_descriptions.get(dim, f"维度 '{dim}' 持续高分")

                patterns.append({
                    "pattern": description,
                    "count": count,
                    "example_ids": dimension_examples[dim][:3],
                    "dimension": dim,
                })

        # 2. 检查 task_type 聚类
        type_counts: Counter = Counter()
        type_examples: dict[str, list[str]] = defaultdict(list)
        for traj in trajectories:
            tt = traj.task_type or "unknown"
            type_counts[tt] += 1
            type_examples[tt].append(traj.id)

        for tt, count in type_counts.most_common():
            if count >= min_count and tt != "unknown":
                patterns.append({
                    "pattern": f"在 '{tt}' 类型任务上表现稳定",
                    "count": count,
                    "example_ids": type_examples[tt][:3],
                    "task_type": tt,
                })

        return patterns

    # ------------------------------------------------------------------
    # 编辑生成
    # ------------------------------------------------------------------

    def _generate_edit(
        self, pattern: dict[str, Any], source_type: str
    ) -> SkillEdit:
        """基于模式生成编辑。格式化为自然语言规则。

        Args:
            pattern: 模式字典（来自 _find_pattern）。
            source_type: "failure" 或 "success"。

        Returns:
            生成的 SkillEdit 实例。
        """
        pattern_text = pattern.get("pattern", "未知模式")
        count = pattern.get("count", 0)
        example_ids = pattern.get("example_ids", [])
        example_ids_str = ", ".join(example_ids[:3])

        if source_type == "failure":
            content = (
                f"## 已知问题修复（基于 {count} 条轨迹分析）\n\n"
                f"**问题描述**：{pattern_text}\n\n"
                f"**改进建议**：\n"
                f"- 检查并优化相关维度的处理逻辑\n"
                f"- 参考成功案例中的对应做法进行调整\n\n"
                f"**来源轨迹**：{example_ids_str}"
            )
            reason = (
                f"失败分析：{pattern_text}（{count} 条轨迹，"
                f"示例：{example_ids_str}）"
            )
        else:
            content = (
                f"## 成功模式强化（基于 {count} 条轨迹分析）\n\n"
                f"**成功模式**：{pattern_text}\n\n"
                f"**建议**：保持并强化此模式，考虑在类似场景中推广\n\n"
                f"**来源轨迹**：{example_ids_str}"
            )
            reason = (
                f"成功分析：{pattern_text}（{count} 条轨迹，"
                f"示例：{example_ids_str}）"
            )

        return SkillEdit(
            id=str(uuid.uuid4()),
            op="append",
            target=None,
            content=content,
            reason=reason,
            source_type=source_type,  # type: ignore[arg-type]
            support_count=count,
            risk_level="low",
            created_at=datetime.now(),
        )
