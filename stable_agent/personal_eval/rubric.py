"""personal_eval.rubric — 评分维度管理器。

V11 新增：管理 Rubric 的加载、更新和默认维度定义。
默认 rubric: vibe_coding_default。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from stable_agent.personal_eval.schemas import Rubric

logger = logging.getLogger(__name__)

# 默认 rubric 定义
_DEFAULT_RUBRIC = Rubric(
    rubric_id="vibe_coding_default",
    dimensions={
        "goal_alignment": 0.30,
        "minimal_change": 0.20,
        "test_passed": 0.20,
        "style_consistency": 0.10,
        "token_efficiency": 0.10,
        "user_preference_match": 0.10,
    },
)


class RubricManager:
    """评分维度管理器。

    管理 Rubric 的加载、更新。Rubric 可从文件加载或使用内置默认值。

    Attributes:
        capsule_path: capsule 目录路径（用于查找 rubric 文件）。
        _rubrics: 已加载的 rubric 缓存。
    """

    def __init__(self, capsule_path: str | None = None) -> None:
        """初始化评分维度管理器。

        Args:
            capsule_path: capsule 目录路径，默认 capsule/。
        """
        self.capsule_path: str = capsule_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "capsule",
        )
        self._rubrics: dict[str, Rubric] = {
            _DEFAULT_RUBRIC.rubric_id: _DEFAULT_RUBRIC,
        }

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def load_rubric(
        self,
        rubric_id: str = "vibe_coding_default",
        capsule_path: str | None = None,
    ) -> Rubric:
        """加载评分维度定义。

        优先从 capsule 目录的 rubric JSON 文件加载，
        不存在时返回内置默认值。

        Args:
            rubric_id: 评分维度集 ID。
            capsule_path: 可选的 capsule 路径覆盖。

        Returns:
            Rubric 实例。
        """
        # 已缓存
        if rubric_id in self._rubrics:
            return self._rubrics[rubric_id]

        # 尝试从文件加载
        base = capsule_path or self.capsule_path
        rubric_file = os.path.join(base, "evals", f"rubric_{rubric_id}.json")
        if os.path.exists(rubric_file):
            try:
                with open(rubric_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                rubric = Rubric.from_dict(data)
                self._rubrics[rubric_id] = rubric
                logger.info("Loaded rubric %s from file", rubric_id)
                return rubric
            except Exception as e:
                logger.warning("Failed to load rubric %s: %s", rubric_id, e)

        # 返回默认值
        if rubric_id == "vibe_coding_default":
            return _DEFAULT_RUBRIC

        # 未知 rubric_id，返回默认值并缓存
        logger.info("Unknown rubric %s, returning default", rubric_id)
        return _DEFAULT_RUBRIC

    def update_rubric(
        self,
        rubric_id: str,
        dimensions: dict[str, float],
    ) -> Rubric:
        """更新评分维度定义。

        如果 rubric 不存在则创建新的。同时持久化到文件。

        Args:
            rubric_id: 评分维度集 ID。
            dimensions: 新的维度名称 → 权重映射。

        Returns:
            更新后的 Rubric 实例。
        """
        rubric = Rubric(rubric_id=rubric_id, dimensions=dimensions)
        self._rubrics[rubric_id] = rubric

        # 持久化
        try:
            evals_dir = os.path.join(self.capsule_path, "evals")
            os.makedirs(evals_dir, exist_ok=True)
            rubric_file = os.path.join(evals_dir, f"rubric_{rubric_id}.json")
            with open(rubric_file, "w", encoding="utf-8") as f:
                json.dump(rubric.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("Persisted rubric %s to %s", rubric_id, rubric_file)
        except Exception as e:
            logger.warning("Failed to persist rubric %s: %s", rubric_id, e)

        return rubric
