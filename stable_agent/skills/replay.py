"""stable_agent.skills.replay — GroupedReplayLite 分组重放。

不做 RL，但复刻 SkillOS 的 task grouping 思想。
使用关键词 + Jaccard + tags 进行分组。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GroupedEpisode:
    """分组重放集。"""

    group_id: str = ""
    runs: list[str] = field(default_factory=list)
    shared_tags: dict[str, list[str]] = field(default_factory=dict)
    reason: str = ""
    skill_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "runs": self.runs,
            "shared_tags": self.shared_tags,
            "reason": self.reason,
            "skill_candidates": self.skill_candidates,
        }


class GroupedReplayLite:
    """分组重放。

    按 task_type、tags、trigger phrases、相似表达分组。
    每组至少 2 个 run。
    生成 skill curation replay report。

    Attributes:
        runs: 历史 run 记录。
    """

    def __init__(self, runs: list[dict[str, Any]] | None = None) -> None:
        """初始化分组重放。

        Args:
            runs: 历史 run 记录列表。
        """
        self.runs = runs or []

    def group_runs(
        self,
        days: int = 7,
        min_group_size: int = 2,
    ) -> list[GroupedEpisode]:
        """对 run 进行分组。

        Args:
            days: 回溯天数。
            min_group_size: 最小分组大小。

        Returns:
            分组列表。
        """
        if not self.runs:
            return []

        # 按 task_type 分组
        type_groups: dict[str, list[dict[str, Any]]] = {}
        for run in self.runs:
            task_type = run.get("task_type", "general")
            if task_type not in type_groups:
                type_groups[task_type] = []
            type_groups[task_type].append(run)

        episodes: list[GroupedEpisode] = []
        group_counter = 0

        # 对每个 task_type 分组进行细分
        for task_type, runs_in_type in type_groups.items():
            # 按 tags 细分
            tag_groups = self._group_by_tags(runs_in_type)

            for tag_key, runs_in_tag in tag_groups.items():
                if len(runs_in_tag) < min_group_size:
                    continue

                group_counter += 1
                shared_tags = self._extract_shared_tags(runs_in_tag)
                reason = self._generate_reason(task_type, tag_key, runs_in_tag)

                episodes.append(GroupedEpisode(
                    group_id=f"group_{group_counter:03d}",
                    runs=[r.get("run_id", "") for r in runs_in_tag],
                    shared_tags=shared_tags,
                    reason=reason,
                    skill_candidates=[],
                ))

        return episodes

    def _group_by_tags(
        self,
        runs: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """按 tags 分组。"""
        groups: dict[str, list[dict[str, Any]]] = {}

        for run in runs:
            tags = run.get("tags", [])
            # 使用 Jaccard 相似度分组
            placed = False
            for group_key in list(groups.keys()):
                group_tags = set(group_key.split(","))
                run_tags = set(tags)
                jaccard = self._jaccard_similarity(group_tags, run_tags)
                if jaccard > 0.3:
                    groups[group_key].append(run)
                    placed = True
                    break

            if not placed:
                key = ",".join(sorted(tags)) if tags else "no_tags"
                if key not in groups:
                    groups[key] = []
                groups[key].append(run)

        return groups

    def _jaccard_similarity(self, set_a: set, set_b: set) -> float:
        """计算 Jaccard 相似度。"""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _extract_shared_tags(
        self,
        runs: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """提取共享 tags。"""
        tag_counts: dict[str, int] = {}
        for run in runs:
            for tag in run.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # 只保留超过半数 run 共享的 tag
        threshold = len(runs) / 2
        shared = {tag: count for tag, count in tag_counts.items() if count >= threshold}

        return {
            "shared_tags": list(shared.keys()),
            "tag_counts": {str(v): k for k, v in shared.items()},
        }

    def _generate_reason(
        self,
        task_type: str,
        tag_key: str,
        runs: list[dict[str, Any]],
    ) -> str:
        """生成分组原因。"""
        run_count = len(runs)
        outcomes = [r.get("outcome", "") for r in runs]
        success_count = outcomes.count("success")
        failure_count = outcomes.count("failure")

        parts = [f"task_type={task_type}"]
        if tag_key != "no_tags":
            parts.append(f"tags=[{tag_key}]")
        parts.append(f"{run_count} runs ({success_count} success, {failure_count} failure)")

        return "; ".join(parts)

    def generate_replay_report(
        self,
        episodes: list[GroupedEpisode],
    ) -> dict[str, Any]:
        """生成重放报告。

        Args:
            episodes: 分组列表。

        Returns:
            重放报告。
        """
        return {
            "ok": True,
            "generated_at": time.time(),
            "total_groups": len(episodes),
            "total_runs": sum(len(ep.runs) for ep in episodes),
            "episodes": [ep.to_dict() for ep in episodes],
        }
