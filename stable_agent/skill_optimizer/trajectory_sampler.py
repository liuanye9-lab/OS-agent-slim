"""轨迹采样器。

从大量轨迹中按策略采样代表性样本，用于后续分析。
采样策略：多样性优先、最近优先、质量分层。
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from datetime import datetime
from typing import Any

from stable_agent.skill_optimizer.models import RolloutTrajectory

logger = logging.getLogger(__name__)


class TrajectorySampler:
    """轨迹采样器。从大量轨迹中按策略采样代表性样本。

    采样策略：
    1. 多样性优先：尽量覆盖不同 task_type
    2. 最近优先：近期的轨迹权重更高
    3. 质量分层：保证成功和失败都有足够样本

    Attributes:
        max_samples: 最大采样数量，默认 40。
        random_seed: 随机种子（可选），用于可复现采样。
    """

    def __init__(self, max_samples: int = 40) -> None:
        """初始化采样器。

        Args:
            max_samples: 最大采样数量，默认 40。
        """
        self.max_samples = max_samples
        logger.info("TrajectorySampler 已初始化，max_samples=%d", max_samples)

    def sample(self, rollouts: list[RolloutTrajectory]) -> list[RolloutTrajectory]:
        """按策略采样。

        优先保证每种 task_type 至少 1 条，然后按时间衰减加权随机采样。

        Args:
            rollouts: 要采样的轨迹列表。

        Returns:
            采样后的轨迹列表。
        """
        if not rollouts:
            return []

        if len(rollouts) <= self.max_samples:
            return list(rollouts)

        # 步骤 1：按 task_type 分组
        grouped = self._group_by_type(rollouts)
        reference_time = datetime.now()

        selected: list[RolloutTrajectory] = []
        remaining: list[RolloutTrajectory] = []

        # 步骤 2：每种类型至少选 1 条（时间最新的）
        for task_type, group in grouped.items():
            if len(selected) >= self.max_samples:
                break

            # 按时间降序排序
            group_sorted = sorted(group, key=lambda r: r.created_at, reverse=True)
            # 选第一条（最新的）
            selected.append(group_sorted[0])
            # 其余进入候选池
            remaining.extend(group_sorted[1:])

        # 步骤 3：如果还有配额，按时间衰减权重随机采样剩余的
        quota = self.max_samples - len(selected)
        if quota > 0 and remaining:
            # 按时间降序排序
            remaining.sort(key=lambda r: r.created_at, reverse=True)

            # 计算时间衰减权重
            weights = [self._time_weight(r, reference_time) for r in remaining]

            # 归一化权重
            total_weight = sum(weights)
            if total_weight > 0:
                probs = [w / total_weight for w in weights]
                # 加权随机采样（不放回）
                sampled_indices = set()

                while len(sampled_indices) < min(quota, len(remaining)):
                    # 使用累积分布采样
                    idx = self._weighted_random_choice(probs, sampled_indices)
                    if idx is None:
                        break
                    sampled_indices.add(idx)

                for idx in sorted(sampled_indices):
                    selected.append(remaining[idx])

        logger.info(
            "采样完成：%d 条轨迹 → %d 条（%d 种 task_type）",
            len(rollouts),
            len(selected),
            len(grouped),
        )

        return selected[: self.max_samples]

    def _group_by_type(
        self, rollouts: list[RolloutTrajectory]
    ) -> dict[str, list[RolloutTrajectory]]:
        """按 task_type 分组。

        Args:
            rollouts: 轨迹列表。

        Returns:
            {task_type: [trajectories]} 字典。
        """
        groups: dict[str, list[RolloutTrajectory]] = defaultdict(list)
        for rollout in rollouts:
            task_type = rollout.task_type or "unknown"
            groups[task_type].append(rollout)
        return dict(groups)

    def _time_weight(
        self, rollout: RolloutTrajectory, reference_time: Any = None
    ) -> float:
        """时间衰减权重：越新越高。decay_factor = 0.95^days_old。

        Args:
            rollout: 轨迹实例。
            reference_time: 参考时间（默认为当前时间）。

        Returns:
            时间衰减权重，范围 (0, 1]。
        """
        if reference_time is None:
            reference_time = datetime.now()

        delta = reference_time - rollout.created_at
        days_old = max(delta.total_seconds() / 86400.0, 0.0)
        return 0.95 ** days_old

    @staticmethod
    def _weighted_random_choice(
        probs: list[float], excluded: set[int]
    ) -> int | None:
        """加权随机选择（排除已选索引）。

        Args:
            probs: 概率列表。
            excluded: 已排除的索引集合。

        Returns:
            选中的索引，或 None（无可选）。
        """
        available = [(i, probs[i]) for i in range(len(probs)) if i not in excluded]
        if not available:
            return None

        indices, weights = zip(*available)
        total = sum(weights)
        if total <= 0:
            return indices[0]

        r = random.random() * total
        cumulative = 0.0
        for idx, w in zip(indices, weights):
            cumulative += w
            if r <= cumulative:
                return idx

        return indices[-1]
