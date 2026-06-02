"""stable_agent/skills/lifecycle.py — Skill 生命周期管理。

管理 skill 状态转换和生命周期规则。
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.skills.models import SkillStatus, VALID_TRANSITIONS

logger = logging.getLogger(__name__)


class SkillLifecycle:
    """Skill 生命周期管理器。"""

    @staticmethod
    def can_transition(from_status: SkillStatus, to_status: SkillStatus) -> bool:
        """检查状态转换是否合法。

        Args:
            from_status: 当前状态。
            to_status: 目标状态。

        Returns:
            True 表示转换合法。
        """
        return to_status in VALID_TRANSITIONS.get(from_status, set())

    @staticmethod
    def get_valid_transitions(status: SkillStatus) -> set[SkillStatus]:
        """获取合法的目标状态。

        Args:
            status: 当前状态。

        Returns:
            合法的目标状态集合。
        """
        return VALID_TRANSITIONS.get(status, set())

    @staticmethod
    def is_terminal(status: SkillStatus) -> bool:
        """检查是否为终态。

        Args:
            status: 状态。

        Returns:
            True 表示终态。
        """
        return status == SkillStatus.ARCHIVED

    @staticmethod
    def is_retrievable(status: SkillStatus) -> bool:
        """检查是否可被检索。

        只有 promoted 才进入默认检索。

        Args:
            status: 状态。

        Returns:
            True 表示可检索。
        """
        return status == SkillStatus.PROMOTED

    @staticmethod
    def get_status_description(status: SkillStatus) -> str:
        """获取状态描述。

        Args:
            status: 状态。

        Returns:
            中文描述。
        """
        descriptions = {
            SkillStatus.DRAFT: "草稿",
            SkillStatus.CANDIDATE: "候选",
            SkillStatus.VALIDATED: "已验证",
            SkillStatus.PROMOTED: "已晋升",
            SkillStatus.DEPRECATED: "已废弃",
            SkillStatus.ARCHIVED: "已归档",
        }
        return descriptions.get(status, "未知")
