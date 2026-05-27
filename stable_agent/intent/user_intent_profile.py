"""用户意图画像。

定义 UserIntentProfile 数据结构及其管理器。
聚合多次交互中的意图信号，使用指数移动平均平滑更新。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserIntentProfile:
    """用户意图画像。

    聚合多次交互中的意图信号，反映用户长期偏好和行为模式。

    Attributes:
        user_id: 用户标识，默认 "default"。
        preferred_depth: 深度偏好，0=简洁 1=深入。
        preferred_structure: 结构化偏好，0=自由 1=结构化。
        common_task_types: 常见任务类型及其频次。
        top_implicit_intents: 最常见的隐性意图列表。
        rejection_patterns: 反复出现的拒绝模式。
    """

    user_id: str = "default"
    preferred_depth: float = 0.5
    preferred_structure: float = 0.5
    common_task_types: dict[str, int] = field(default_factory=dict)
    top_implicit_intents: list[str] = field(default_factory=list)
    rejection_patterns: list[str] = field(default_factory=list)


class UserIntentProfileManager:
    """管理用户意图画像。

    从意图信号提取器结果中增量更新画像。
    使用指数移动平均（EMA）平滑更新数值型字段，
    使用计数器累积更新分类型字段。

    Attributes:
        profile_path: 画像持久化文件路径。
        _profile: 内存中的 UserIntentProfile 实例。
    """

    # EMA 平滑因子（越大对新信号越敏感）
    EMA_ALPHA: float = 0.3

    def __init__(self, profile_path: str = "data/user_intent_profile.json") -> None:
        """初始化管理器。

        Args:
            profile_path: 画像 JSON 文件的路径。
        """
        self.profile_path = Path(profile_path).resolve()
        self._profile: UserIntentProfile | None = None
        logger.info(
            "UserIntentProfileManager 已初始化，路径=%s", self.profile_path
        )

    def update_from_signals(self, signals: dict[str, Any]) -> None:
        """从意图信号更新画像。使用指数移动平均平滑更新。

        更新规则：
        - preferred_depth: EMA 更新（从 output_preference.depth 提取）
        - preferred_structure: EMA 更新（从 output_preference.structure 提取）
        - common_task_types: 计数器 +1
        - top_implicit_intents: 去重追加，保留 top-5
        - rejection_patterns: 去重追加，保留 top-10

        Args:
            signals: extract() 返回的意图信号字典。
        """
        profile = self.load()

        # 更新深度偏好
        preference = signals.get("output_preference", {})
        depth_map = {"concise": 0.2, "moderate": 0.5, "detailed": 0.8}
        depth_str = preference.get("depth", "moderate")
        if isinstance(depth_str, str):
            target_depth = depth_map.get(depth_str, 0.5)
            profile.preferred_depth = (
                self.EMA_ALPHA * target_depth
                + (1 - self.EMA_ALPHA) * profile.preferred_depth
            )

        # 更新结构化偏好
        structure_map = {
            "free_form": 0.2, "neutral": 0.5,
            "moderate": 0.5, "structured": 0.8, "code_heavy": 0.9,
        }
        structure_str = preference.get("structure", "moderate")
        if isinstance(structure_str, str):
            target_structure = structure_map.get(structure_str, 0.5)
            profile.preferred_structure = (
                self.EMA_ALPHA * target_structure
                + (1 - self.EMA_ALPHA) * profile.preferred_structure
            )

        # 更新常见任务类型
        task_category = signals.get("task_category", "")
        if task_category:
            profile.common_task_types[task_category] = (
                profile.common_task_types.get(task_category, 0) + 1
            )

        # 更新隐性意图 top-5
        implicit = signals.get("implicit_intent", "")
        if implicit and implicit not in profile.top_implicit_intents:
            profile.top_implicit_intents.append(implicit)
            profile.top_implicit_intents = profile.top_implicit_intents[-5:]

        # 更新拒绝模式（去重）
        rejection_signals: list[str] = signals.get("rejection_signals", [])
        for sig in rejection_signals:
            if sig not in profile.rejection_patterns:
                profile.rejection_patterns.append(sig)
        profile.rejection_patterns = profile.rejection_patterns[-10:]

        self._profile = profile
        self.save()
        logger.debug("用户意图画像已更新")

    def load(self) -> UserIntentProfile:
        """加载画像，如果文件不存在则返回默认画像。

        Returns:
            UserIntentProfile 实例。
        """
        if self._profile is not None:
            return self._profile

        if not self.profile_path.exists():
            self._profile = UserIntentProfile()
            return self._profile

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._profile = UserIntentProfile(
                user_id=data.get("user_id", "default"),
                preferred_depth=data.get("preferred_depth", 0.5),
                preferred_structure=data.get("preferred_structure", 0.5),
                common_task_types=data.get("common_task_types", {}),
                top_implicit_intents=data.get("top_implicit_intents", []),
                rejection_patterns=data.get("rejection_patterns", []),
            )
            return self._profile

        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("加载画像失败，使用默认画像: %s", exc)
            self._profile = UserIntentProfile()
            return self._profile

    def save(self) -> None:
        """持久化画像到 JSON 文件。"""
        if self._profile is None:
            return

        self.profile_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "user_id": self._profile.user_id,
            "preferred_depth": self._profile.preferred_depth,
            "preferred_structure": self._profile.preferred_structure,
            "common_task_types": self._profile.common_task_types,
            "top_implicit_intents": self._profile.top_implicit_intents,
            "rejection_patterns": self._profile.rejection_patterns,
        }

        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.debug("画像已保存到 %s", self.profile_path)
