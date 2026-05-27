"""偏好漂移检测器。

检测用户偏好是否发生漂移（旧偏好已过期）。
比较最近信号与旧画像，判断是否需要更新 skill。
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.intent.user_intent_profile import UserIntentProfile

logger = logging.getLogger(__name__)


class PreferenceDriftDetector:
    """检测用户偏好是否发生漂移。

    通过比较最近 N 条意图信号与旧用户画像，判断偏好是否发生了
    显著变化（漂移），从而触发 skill 更新。

    Attributes:
        window_size: 最近信号窗口大小，默认 20。
        drift_threshold: 漂移检测阈值，默认 0.3（差异超过此值视为漂移）。
    """

    def __init__(self, window_size: int = 20) -> None:
        """初始化检测器。

        Args:
            window_size: 用于检测的最近信号数量，默认 20。
        """
        self.window_size = window_size
        logger.info(
            "PreferenceDriftDetector 已初始化，window_size=%d", window_size
        )

    def detect(
        self,
        recent_signals: list[dict[str, Any]],
        old_profile: UserIntentProfile,
    ) -> dict[str, Any]:
        """比较最近信号与旧画像，检测偏好漂移。

        分析维度：
        - depth_drift: 深度偏好是否变化
        - structure_drift: 结构偏好是否变化
        - task_type_drift: 任务类型分布是否变化
        - intent_drift: 隐性意图是否变化
        - rejection_drift: 拒绝模式是否变化

        Args:
            recent_signals: 最近的意图信号列表（来自 IntentSignalExtractor.extract()）。
            old_profile: 旧用户画像。

        Returns:
            检测结果字典：
            - drifted_dimensions: 发生漂移的维度列表
            - confidence: 漂移置信度（0~1）
            - detail: 各维度详细对比
        """
        if not recent_signals:
            return {
                "drifted_dimensions": [],
                "confidence": 0.0,
                "detail": {},
            }

        # 只使用最近 window_size 条
        signals = recent_signals[-self.window_size:]

        # 从最近信号中聚合偏好
        recent_depth = self._aggregate_depth(signals)
        recent_structure = self._aggregate_structure(signals)
        recent_task_types = self._aggregate_task_types(signals)

        drifted_dimensions: list[str] = []
        detail: dict[str, Any] = {}

        # 深度漂移检测
        depth_delta = abs(recent_depth - old_profile.preferred_depth)
        detail["depth"] = {
            "old": old_profile.preferred_depth,
            "recent": recent_depth,
            "delta": depth_delta,
        }
        if depth_delta > 0.3:
            drifted_dimensions.append("depth")

        # 结构漂移检测
        structure_delta = abs(recent_structure - old_profile.preferred_structure)
        detail["structure"] = {
            "old": old_profile.preferred_structure,
            "recent": recent_structure,
            "delta": structure_delta,
        }
        if structure_delta > 0.3:
            drifted_dimensions.append("structure")

        # 任务类型漂移检测
        old_task_types = old_profile.common_task_types
        if recent_task_types and old_task_types:
            task_type_overlap = self._jaccard_similarity(
                set(recent_task_types.keys()),
                set(old_task_types.keys()),
            )
            detail["task_type"] = {
                "recent": recent_task_types,
                "old": old_task_types,
                "overlap": task_type_overlap,
            }
            if task_type_overlap < 0.5:
                drifted_dimensions.append("task_type")

        # 计算总体置信度
        confidence = len(drifted_dimensions) / 5.0  # 最多 5 个维度

        return {
            "drifted_dimensions": drifted_dimensions,
            "confidence": round(confidence, 4),
            "detail": detail,
        }

    def should_update_skill(
        self, drift_result: dict[str, Any], threshold: float = 0.3
    ) -> bool:
        """判断是否需要更新 skill 以反映偏好漂移。

        判断逻辑：
        - 如果 drifted_dimensions 非空且 confidence >= threshold → 需要更新
        - 否则不需要

        Args:
            drift_result: detect() 返回的结果字典。
            threshold: 置信度阈值，默认 0.3。

        Returns:
            True 如果需要更新 skill。
        """
        drifted = drift_result.get("drifted_dimensions", [])
        confidence = drift_result.get("confidence", 0.0)

        should_update = len(drifted) > 0 and confidence >= threshold

        if should_update:
            logger.info(
                "检测到偏好漂移（维度: %s，置信度: %.2f），建议更新 skill",
                drifted,
                confidence,
            )
        else:
            logger.debug("未检测到显著偏好漂移")

        return should_update

    # ------------------------------------------------------------------
    # 聚合方法
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_depth(signals: list[dict[str, Any]]) -> float:
        """从最近信号聚合深度偏好。

        Args:
            signals: 意图信号列表。

        Returns:
            聚合后的深度偏好（0~1）。
        """
        depth_map = {"concise": 0.2, "moderate": 0.5, "detailed": 0.8}

        values: list[float] = []
        for sig in signals:
            pref = sig.get("output_preference", {})
            if isinstance(pref, dict):
                depth_str = pref.get("depth", "moderate")
                if isinstance(depth_str, str) and depth_str in depth_map:
                    values.append(depth_map[depth_str])

        if not values:
            return 0.5

        return sum(values) / len(values)

    @staticmethod
    def _aggregate_structure(signals: list[dict[str, Any]]) -> float:
        """从最近信号聚合结构偏好。

        Args:
            signals: 意图信号列表。

        Returns:
            聚合后的结构偏好（0~1）。
        """
        structure_map = {
            "free_form": 0.2, "neutral": 0.5,
            "moderate": 0.5, "structured": 0.8, "code_heavy": 0.9,
        }

        values: list[float] = []
        for sig in signals:
            pref = sig.get("output_preference", {})
            if isinstance(pref, dict):
                struct_str = pref.get("structure", "moderate")
                if isinstance(struct_str, str) and struct_str in structure_map:
                    values.append(structure_map[struct_str])

        if not values:
            return 0.5

        return sum(values) / len(values)

    @staticmethod
    def _aggregate_task_types(
        signals: list[dict[str, Any]],
    ) -> dict[str, int]:
        """从最近信号聚合任务类型分布。

        Args:
            signals: 意图信号列表。

        Returns:
            {task_category: count} 字典。
        """
        counts: dict[str, int] = {}
        for sig in signals:
            tc = sig.get("task_category", "qa")
            if isinstance(tc, str):
                counts[tc] = counts.get(tc, 0) + 1
        return counts

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        """计算两个集合的 Jaccard 相似度。

        Args:
            set_a: 集合 A。
            set_b: 集合 B。

        Returns:
            0~1 的相似度值。
        """
        if not set_a and not set_b:
            return 1.0
        union = set_a | set_b
        if not union:
            return 1.0
        intersection = set_a & set_b
        return len(intersection) / len(union)
