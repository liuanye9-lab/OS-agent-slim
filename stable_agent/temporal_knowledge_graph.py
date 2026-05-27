"""时间知识图谱模块。

本模块提供 TemporalKnowledgeGraph 类，实现带时间维度的知识图谱，
支持事实的时间范围查询和冲突检测。

V3 升级：
- invalidate_fact: 标记事实失效
- query_current_facts: 查询当前生效的事实
- from_memory_item: 从 MemoryItem 生成事实
- add_or_update_fact: 添加或更新事实（自动失效旧版本）

模块职责：
- 存储带时间戳的事实三元组
- 支持时间范围查询
- 检测时间重叠的冲突事实
- 事实生命周期管理（生效/失效）
- 与 MemoryItem 的互操作
"""

from __future__ import annotations

import re
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from stable_agent.models import MemoryItem


class TemporalKnowledgeGraph:
    """带时间维度的知识图谱。

    存储 (subject, predicate, object, start_time, end_time) 事实，
    支持时间范围查询和冲突检测。

    Attributes:
        facts: 事实列表，每个事实为包含 subject, predicate, obj,
               start_time, end_time, source, confidence 的字典。
    """

    # 三元组提取的分隔关键词
    _SPLIT_KEYWORDS: list[str] = [
        "的", "是", "使用", "采用", "基于", "依赖",
        "位于", "属于", "包含", "具有", "调用",
        "实现", "继承", "部署在",
    ]

    def __init__(self) -> None:
        """初始化空的事实列表。"""
        self.facts: list[dict] = []

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        start_time: float,
        end_time: Optional[float] = None,
    ) -> None:
        """添加一个事实到知识图谱中。

        Args:
            subject: 事实主语。
            predicate: 事实谓词/关系。
            obj: 事实宾语/值。
            start_time: 事实生效起始时间（time.time() float 格式）。
            end_time: 事实生效结束时间，None 表示持续有效至今。
        """
        fact: dict = {
            "subject": subject,
            "predicate": predicate,
            "obj": obj,
            "start_time": start_time,
            "end_time": end_time,
            "source": "",
            "confidence": 0.7,
        }
        self.facts.append(fact)

    def query_facts(
        self,
        entity: str,
        time_range: Optional[tuple[float, float]] = None,
    ) -> list[dict]:
        """查询与指定实体相关的事实。

        匹配 entity 作为 subject 或 object 的所有事实。
        如果指定 time_range，只返回在时间范围内生效的事实。

        事实在 [start_time, end_time) 区间内生效，end_time 为 None
        表示至今仍有效。

        Args:
            entity: 要查询的实体名称。
            time_range: 可选的时间范围 (start, end)，半开区间 [start, end)。

        Returns:
            匹配的事实列表。

        # STUB: 真实实现应使用 Graphiti/Zep 等图数据库，支持时间旅行查询。
        """
        results: list[dict] = []
        for fact in self.facts:
            # 检查实体匹配
            if fact["subject"] != entity and fact["obj"] != entity:
                continue

            # 检查时间范围
            if time_range is not None:
                query_start, query_end = time_range
                # 事实的生效区间：[start_time, end_time)
                # 事实的 end_time 为 None 表示至今有效
                fact_end = fact["end_time"] if fact["end_time"] is not None else float("inf")
                # 事实与查询区间有交集：fact_start < query_end and fact_end > query_start
                if fact["start_time"] >= query_end or fact_end <= query_start:
                    continue

            results.append(fact)

        return results

    def resolve_conflicts(self, entity: str) -> list[list[dict]]:
        """查找同一实体在时间上重叠的冲突事实。

        按 subject 分组，找到同一 predicate 但不同 obj 且在时间上有重叠的
        事实对。使用 O(n²) 遍历算法。

        Args:
            entity: 要检查冲突的实体名称。

        Returns:
            冲突对列表，每对包含 [fact1, fact2] 两个冲突的事实。
        """
        # 筛选与 entity 相关的事实
        entity_facts = [
            f for f in self.facts
            if f["subject"] == entity or f["obj"] == entity
        ]
        conflicts: list[list[dict]] = []
        n = len(entity_facts)

        for i in range(n):
            for j in range(i + 1, n):
                f1 = entity_facts[i]
                f2 = entity_facts[j]

                # 检查 predicate 是否相同
                if f1["predicate"] != f2["predicate"]:
                    continue

                # 检查 obj 是否不同
                if f1["obj"] == f2["obj"]:
                    continue

                # 检查时间是否重叠
                f1_end = f1["end_time"] if f1["end_time"] is not None else float("inf")
                f2_end = f2["end_time"] if f2["end_time"] is not None else float("inf")

                # 两段时间重叠：不是 f1_end <= f2_start 且不是 f2_end <= f1_start
                if f1_end > f2["start_time"] and f2_end > f1["start_time"]:
                    conflicts.append([f1, f2])

        return conflicts

    def get_facts_count(self) -> int:
        """返回事实总数。

        Returns:
            facts 列表中的事实数量。
        """
        return len(self.facts)

    def clear(self) -> None:
        """清空所有事实。"""
        self.facts.clear()

    # ------------------------------------------------------------------
    # V3 新增方法
    # ------------------------------------------------------------------

    def invalidate_fact(
        self,
        fact_index: int,
        invalid_at: float | None = None,
        reason: str = "",
    ) -> None:
        """将事实标记为失效（设置 end_time）。

        通过设置 end_time 来标记一个事实不再有效。
        如果 invalid_at 为 None，使用当前时间戳。

        Args:
            fact_index: 事实在 self.facts 中的索引。
            invalid_at: 失效时间戳，None 使用当前时间。
            reason: 失效原因说明，会追加到 source 字段。

        Raises:
            IndexError: 如果 fact_index 超出范围。

        Examples:
            >>> kg = TemporalKnowledgeGraph()
            >>> kg.add_fact("project_A", "uses", "Python3.10", time.time())
            >>> kg.invalidate_fact(0, reason="升级到 3.11")
            >>> kg.facts[0]["end_time"] is not None
            True
        """
        if invalid_at is None:
            invalid_at = time.time()

        self.facts[fact_index]["end_time"] = invalid_at
        if reason:
            existing_source: str = self.facts[fact_index].get("source", "")
            self.facts[fact_index]["source"] = (
                f"{existing_source} [失效原因: {reason}]".strip()
            )

    def query_current_facts(self, entity: str) -> list[dict]:
        """查询当前生效的事实（end_time 为 None 或 > now）。

        与 query_facts 的区别是自动使用当前时间作为时间范围上限。

        Args:
            entity: 要查询的实体名称。

        Returns:
            当前生效的事实列表。

        Examples:
            >>> kg = TemporalKnowledgeGraph()
            >>> kg.add_fact("service_A", "runs_on", "k8s", time.time())
            >>> current = kg.query_current_facts("service_A")
            >>> len(current)
            1
        """
        now: float = time.time()
        results: list[dict] = []
        for fact in self.facts:
            # 检查实体匹配
            if fact["subject"] != entity and fact["obj"] != entity:
                continue

            # 检查是否当前生效
            fact_end = fact["end_time"] if fact["end_time"] is not None else float("inf")
            if fact["start_time"] <= now < fact_end:
                results.append(fact)

        return results

    def from_memory_item(self, item: "MemoryItem") -> dict | None:
        """从 MemoryItem 生成事实字典。

        尝试从 content 提取 (subject, predicate, object) 三元组：
        - 简单规则：按"的"/"是"/"使用"等关键词拆分
        - 如果无法拆分，subject=item.id, predicate="note", obj=item.content
        - start_time=item.valid_at or item.timestamp
        - end_time=item.invalid_at

        Args:
            item: MemoryItem 实例。

        Returns:
            事实字典，包含 subject, predicate, obj, start_time, end_time,
            source, confidence 字段。如果无法提取有效三元组返回 None。

        Examples:
            >>> from stable_agent.models import MemoryItem
            >>> item = MemoryItem(id="m1", content="项目A使用Python3.10作为主要语言")
            >>> kg = TemporalKnowledgeGraph()
            >>> fact = kg.from_memory_item(item)
            >>> fact is not None
            True
            >>> fact["subject"]
            '项目A'
        """
        content: str = item.content
        if not content.strip():
            return None

        # 尝试按关键词拆分
        for kw in self._SPLIT_KEYWORDS:
            if kw in content:
                idx: int = content.index(kw)
                subject: str = content[:idx].strip()
                remaining: str = content[idx + len(kw):].strip()

                if subject and remaining:
                    # 进一步拆分 remaining：取第一个合理部分作为 object
                    # 按标点或中文句号截断
                    obj_end: int = len(remaining)
                    for sep in ("，", "。", "；", ",", ".", ";"):
                        pos: int = remaining.find(sep)
                        if 0 < pos < obj_end:
                            obj_end = pos
                    obj: str = remaining[:obj_end].strip()

                    if obj:
                        start_time: float = (
                            item.valid_at
                            if item.valid_at is not None
                            else item.timestamp
                        )
                        return {
                            "subject": subject,
                            "predicate": kw,
                            "obj": obj,
                            "start_time": start_time,
                            "end_time": item.invalid_at,
                            "source": item.source,
                            "confidence": item.confidence,
                        }

        # 无法拆分 → 退化为 note 类型
        start_time: float = (
            item.valid_at if item.valid_at is not None else item.timestamp
        )
        return {
            "subject": item.id,
            "predicate": "note",
            "obj": content,
            "start_time": start_time,
            "end_time": item.invalid_at,
            "source": item.source,
            "confidence": item.confidence,
        }

    def add_or_update_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        source: str = "",
        confidence: float = 0.7,
    ) -> dict:
        """添加或更新事实：如果同 subject+predicate 存在，先 invalidate 旧事实再添加。

        策略：
        1. 查找所有同 subject + predicate 的当前生效事实
        2. 将它们标记为失效
        3. 添加新事实

        Args:
            subject: 事实主语。
            predicate: 事实谓词。
            obj: 事实宾语。
            source: 来源标识。
            confidence: 置信度，0.0~1.0。

        Returns:
            新添加的事实字典。

        Examples:
            >>> kg = TemporalKnowledgeGraph()
            >>> kg.add_or_update_fact("project_A", "uses", "Python3.10")
            >>> kg.add_or_update_fact("project_A", "uses", "Python3.12")
            >>> kg.get_facts_count()
            2
            >>> current = kg.query_current_facts("project_A")
            >>> len(current)
            1
            >>> current[0]["obj"]
            'Python3.12'
        """
        now: float = time.time()

        # 失效同 subject + predicate 的当前生效事实
        for fact in self.facts:
            if fact["subject"] == subject and fact["predicate"] == predicate:
                fact_end = fact["end_time"] if fact["end_time"] is not None else float("inf")
                if fact["start_time"] <= now < fact_end:
                    fact["end_time"] = now

        # 添加新事实
        new_fact: dict = {
            "subject": subject,
            "predicate": predicate,
            "obj": obj,
            "start_time": now,
            "end_time": None,
            "source": source,
            "confidence": confidence,
        }
        self.facts.append(new_fact)
        return new_fact
