"""TemporalMemoryBridge — 连接旧 MemoryRouter → 新 TemporalMemoryRouter。

将现有 MemoryRouter / SaaSRepository / MemoryBank 中的记忆
转换成统一的 TemporalMemoryHit 格式，作为时间感知记忆路由的数据源。

V6.1: 新模块，为 TemporalMemoryRouter 提供数据供应层。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from stable_agent.memory.temporal_memory_router import (
    TemporalMemoryHit,
    TemporalMemoryQuery,
    TemporalMemoryRouter,
)

if TYPE_CHECKING:
    pass  # 生产导入为可选，支持优雅降级

logger = logging.getLogger(__name__)


class TemporalMemoryBridge:
    """连接旧 MemoryRouter / MemoryBank / Repository 到新 TemporalMemoryRouter。

    职责：
    1. 从旧记忆系统加载记忆条目
    2. 转换为 TemporalMemoryHit 统一格式
    3. 注入 TemporalMemoryRouter 供后续检索
    4. 支持 project_id 过滤

    Usage:
        bridge = TemporalMemoryBridge()
        bridge.load_for_project(project_id="proj-001")
        hits = router.retrieve(query)
    """

    def __init__(self) -> None:
        self._router = TemporalMemoryRouter()

    @property
    def router(self) -> TemporalMemoryRouter:
        """获取底层 TemporalMemoryRouter 实例。"""
        return self._router

    def load_for_project(
        self,
        project_id: str | None = None,
        existing_memories: list[dict[str, Any]] | None = None,
        bad_cases: list[dict[str, Any]] | None = None,
        skill_rules: list[dict[str, Any]] | None = None,
    ) -> list[TemporalMemoryHit]:
        """加载项目相关的记忆到路由器中。

        从三个来源加载：
        1. existing_memories: 旧 MemoryRouter / MemoryBank 中的记忆条目
        2. bad_cases: 失败案例（BadCaseManager 输出）
        3. skill_rules: 已验证的 skill 规则

        Args:
            project_id: 项目 ID，用于过滤。
            existing_memories: 现有记忆列表 [{"id": ..., "content": ..., ...}, ...]。
            bad_cases: 失败案例列表。
            skill_rules: Skill 规则列表。

        Returns:
            加载后的所有 TemporalMemoryHit。
        """
        self._router.clear()

        # 1. 从旧记忆系统加载
        if existing_memories:
            for mem in existing_memories:
                hit = self.from_memory_item(mem, project_id=project_id)
                if hit:
                    self._router.add(hit)

        # 2. 从失败案例加载（高优先级）
        if bad_cases:
            for case in bad_cases:
                hit = self.from_bad_case(case, project_id=project_id)
                if hit:
                    self._router.add(hit)

        # 3. 从 skill 规则加载（已验证的规则）
        if skill_rules:
            for rule in skill_rules:
                hit = self.from_skill_rule(rule, project_id=project_id)
                if hit:
                    self._router.add(hit)

        logger.info(
            "MemoryBridge loaded: memories=%d, bad_cases=%d, skill_rules=%d → total=%d",
            len(existing_memories or []),
            len(bad_cases or []),
            len(skill_rules or []),
            len(self._router._memories),
        )
        return list(self._router._memories.values())

    def retrieve(
        self,
        task_input: str,
        project_id: str | None = None,
        intent_keywords: list[str] | None = None,
        top_k: int = 8,
    ) -> list[TemporalMemoryHit]:
        """检索与任务相关的记忆。

        Args:
            task_input: 任务输入文本。
            project_id: 项目 ID。
            intent_keywords: 意图关键词。
            top_k: 返回最大条数。

        Returns:
            排序后的 TemporalMemoryHit 列表。
        """
        query = TemporalMemoryQuery(
            task_input=task_input,
            current_time=__import__("time").time(),
            project_id=project_id,
            intent_keywords=intent_keywords or [],
            top_k=top_k,
        )
        return self._router.retrieve(query)

    # ------------------------------------------------------------------
    # 转换器
    # ------------------------------------------------------------------

    @staticmethod
    def from_memory_item(
        item: dict[str, Any],
        project_id: str | None = None,
    ) -> TemporalMemoryHit | None:
        """从旧记忆条目转换为 TemporalMemoryHit。

        Args:
            item: 旧记忆字典 {"id", "content", "created_at", ...}。
            project_id: 项目 ID。

        Returns:
            TemporalMemoryHit 或 None（无法转换时）。
        """
        if not item.get("content"):
            return None

        now = __import__("time").time()
        return TemporalMemoryHit(
            memory_id=item.get("id", f"mem_{hash(item.get('content', ''))}"),
            content=str(item["content"]),
            created_at=item.get("created_at", now),
            updated_at=item.get("updated_at", now),
            project_id=project_id,
            valid_from=item.get("valid_from"),
            valid_until=item.get("valid_until"),
            confidence=float(item.get("confidence", 0.5)),
            source=item.get("source", "memory_bank"),
            tags=item.get("tags", []) if isinstance(item.get("tags"), list) else [],
            source_quality=0.6,
        )

    @staticmethod
    def from_bad_case(
        bad_case: dict[str, Any],
        project_id: str | None = None,
    ) -> TemporalMemoryHit | None:
        """从失败案例转换为 TemporalMemoryHit。

        失败案例具有更高的 source_quality (0.8) 和 confidence。

        Args:
            bad_case: 失败案例字典。
            project_id: 项目 ID。

        Returns:
            TemporalMemoryHit 或 None。
        """
        content = bad_case.get("description") or bad_case.get("summary") or bad_case.get("error")
        if not content:
            return None

        case_id = bad_case.get("id", bad_case.get("case_id", ""))
        now = __import__("time").time()

        return TemporalMemoryHit(
            memory_id=f"bad_{case_id}",
            content=f"[失败案例] {content}",
            created_at=bad_case.get("created_at", now),
            updated_at=now,
            project_id=project_id,
            confidence=float(bad_case.get("severity", 0.7)),
            source="bad_case",
            tags=["bad_case", "failure"] + (bad_case.get("tags", []) if isinstance(bad_case.get("tags"), list) else []),
            source_quality=0.8,
        )

    @staticmethod
    def from_skill_rule(
        skill_rule: dict[str, Any],
        project_id: str | None = None,
    ) -> TemporalMemoryHit | None:
        """从已验证的 skill 规则转换为 TemporalMemoryHit。

        已验证规则具有最高 source_quality (0.9)。

        Args:
            skill_rule: Skill 规则字典。
            project_id: 项目 ID。

        Returns:
            TemporalMemoryHit 或 None。
        """
        rule_content = skill_rule.get("rule") or skill_rule.get("content")
        if not rule_content:
            return None

        rule_id = skill_rule.get("id", skill_rule.get("rule_id", ""))
        now = __import__("time").time()

        return TemporalMemoryHit(
            memory_id=f"rule_{rule_id}",
            content=f"[已验证规则] {rule_content}",
            created_at=skill_rule.get("created_at", now),
            updated_at=skill_rule.get("updated_at", now),
            project_id=project_id,
            valid_from=skill_rule.get("valid_from"),
            valid_until=skill_rule.get("valid_until"),
            confidence=float(skill_rule.get("confidence", 0.9)),
            source="skill_rule_validated",
            tags=["skill_rule", "validated"] + (skill_rule.get("tags", []) if isinstance(skill_rule.get("tags"), list) else []),
            source_quality=0.9,
        )
