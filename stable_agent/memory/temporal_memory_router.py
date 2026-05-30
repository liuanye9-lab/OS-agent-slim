"""TemporalMemoryRouter — 时间感知记忆路由器。

在上下文压缩之前检索按时间戳相关的记忆，防止压缩过程中
丢失关键历史约束。支持：
- 按时间窗口过滤
- 过期记忆自动过滤
- 记忆冲突标记
- 召回原因解释（reason_zh）

排序逻辑：
    final_score = relevance * 0.55 + recency * 0.20 + confidence * 0.20 + source_quality * 0.05
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TemporalMemoryQuery:
    """时间记忆查询参数。"""

    task_input: str
    current_time: float = field(default_factory=time.time)
    time_window_days: int | None = None
    project_id: str | None = None
    intent_keywords: list[str] = field(default_factory=list)
    top_k: int = 8


@dataclass
class TemporalMemoryHit:
    """单条时间记忆命中。"""

    memory_id: str
    content: str
    created_at: float
    updated_at: float
    valid_from: float | None = None
    valid_until: float | None = None
    confidence: float = 0.5
    relevance_score: float = 0.0
    recency_score: float = 0.0
    source: str = ""
    reason_zh: str = ""
    tags: list[str] = field(default_factory=list)
    source_quality: float = 0.5

    def is_expired(self, now: float | None = None) -> bool:
        """检查记忆是否已过期。"""
        if self.valid_until is None:
            return False
        now = now or time.time()
        return now > self.valid_until

    def is_not_yet_valid(self, now: float | None = None) -> bool:
        """检查记忆是否尚未生效。"""
        if self.valid_from is None:
            return False
        now = now or time.time()
        return now < self.valid_from


class TemporalMemoryRouter:
    """时间感知记忆路由器。

    在上下文压缩前，基于时间戳和相关性检索相关记忆。
    防止压缩过程丢失关键历史约束。

    Attributes:
        _memories: 内存记忆存储（dict: memory_id → TemporalMemoryHit）
    """

    def __init__(self) -> None:
        """初始化空记忆库。"""
        self._memories: dict[str, TemporalMemoryHit] = {}

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def add(self, hit: TemporalMemoryHit) -> None:
        """添加或覆盖一条时间记忆。

        Args:
            hit: TemporalMemoryHit 实例。
        """
        self._memories[hit.memory_id] = hit

    def add_batch(self, hits: list[TemporalMemoryHit]) -> None:
        """批量添加时间记忆。

        Args:
            hits: TemporalMemoryHit 列表。
        """
        for hit in hits:
            self._memories[hit.memory_id] = hit

    def retrieve(self, query: TemporalMemoryQuery) -> list[TemporalMemoryHit]:
        """按时间戳和相关性检索记忆。

        检索流程：
        1. 过滤过期和未生效记忆
        2. 可选：按时间窗口过滤
        3. 计算 relevance 分数（关键词匹配）
        4. 计算 recency 分数（时间衰减）
        5. 加权合成 final_score
        6. 排序返回 top_k

        Args:
            query: 查询参数。

        Returns:
            按 final_score 降序排列的 TemporalMemoryHit 列表。
        """
        now = query.current_time
        candidates: list[TemporalMemoryHit] = []

        for hit in self._memories.values():
            # 跳过过期
            if hit.is_expired(now):
                continue
            # 跳过未生效
            if hit.is_not_yet_valid(now):
                continue

            # 可选：时间窗口过滤
            if query.time_window_days is not None:
                window_seconds = query.time_window_days * 86400
                if now - hit.created_at > window_seconds:
                    continue

            # 可选：项目过滤
            if query.project_id is not None:
                if query.project_id not in hit.tags:
                    continue

            # 计算 relevance（关键词匹配）
            relevance = self._compute_relevance(hit, query)

            # 计算 recency（时间衰减）
            recency = self._compute_recency(hit, now)

            # 加权合成
            final_score = (
                relevance * 0.55
                + recency * 0.20
                + hit.confidence * 0.20
                + hit.source_quality * 0.05
            )

            # 生成 reason_zh
            reason_parts = []
            if relevance > 0.3:
                reason_parts.append("关键词匹配")
            if recency > 0.7:
                reason_parts.append("最近更新")
            if hit.confidence > 0.8:
                reason_parts.append("高置信度")
            if not reason_parts:
                reason_parts.append(f"来源: {hit.source}")

            hit.relevance_score = round(relevance, 4)
            hit.recency_score = round(recency, 4)
            hit.reason_zh = "，".join(reason_parts) if reason_parts else "被动召回"

            if final_score > 0:
                candidates.append(hit)

        # 按 final_score 降序，取 top_k
        candidates.sort(
            key=lambda h: (
                h.relevance_score * 0.55
                + h.recency_score * 0.20
                + h.confidence * 0.20
                + h.source_quality * 0.05
            ),
            reverse=True,
        )

        return candidates[: query.top_k]

    def detect_conflicts(self, hit: TemporalMemoryHit) -> list[TemporalMemoryHit]:
        """检测与现有记忆的冲突（按 content Jaccard 相似度 > 0.3）。

        Args:
            hit: 待检测的 TemporalMemoryHit。

        Returns:
            冲突的记忆列表。
        """
        import re

        def tokenize(text: str) -> set[str]:
            parts = re.split(r"[^\w\u4e00-\u9fff]+", text.lower())
            result: set[str] = set()
            for part in parts:
                if not part:
                    continue
                if part.isascii():
                    result.add(part)
                else:
                    result.update(part)
            return result

        new_tokens = tokenize(hit.content)
        if not new_tokens:
            return []

        conflicts: list[TemporalMemoryHit] = []
        for existing in self._memories.values():
            if existing.memory_id == hit.memory_id:
                continue
            existing_tokens = tokenize(existing.content)
            if not existing_tokens:
                continue
            union = new_tokens | existing_tokens
            jaccard = len(new_tokens & existing_tokens) / len(union) if union else 0
            if jaccard > 0.3:
                conflicts.append(existing)

        return conflicts

    def clear(self) -> None:
        """清空所有记忆。"""
        self._memories.clear()

    @property
    def size(self) -> int:
        """返回记忆总数。"""
        return len(self._memories)

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_relevance(hit: TemporalMemoryHit, query: TemporalMemoryQuery) -> float:
        """计算内容相关性分数（0~1）。

        基于关键词匹配：hit.content / tags 与 query.task_input / intent_keywords
        中的关键词命中比例。

        Args:
            hit: 记忆条目。
            query: 查询参数。

        Returns:
            相关性分数 0.0~1.0。
        """
        if not query.intent_keywords and not query.task_input:
            return 0.1  # 无意图关键词时低分召回

        search_text = query.task_input.lower()
        keywords = set(kw.lower() for kw in query.intent_keywords)

        # 从 task_input 中额外提取关键词
        import re
        input_tokens = set(
            t.lower() for t in re.split(r"[^\w\u4e00-\u9fff]+", search_text)
            if len(t) >= 2
        )
        all_keywords = keywords | input_tokens

        if not all_keywords:
            return 0.1

        content_lower = hit.content.lower()
        tags_lower = [t.lower() for t in hit.tags]

        hits = 0
        for kw in all_keywords:
            if kw in content_lower or any(kw in t for t in tags_lower):
                hits += 1

        return min(1.0, hits / max(1, len(all_keywords)))

    @staticmethod
    def _compute_recency(hit: TemporalMemoryHit, now: float) -> float:
        """计算时间衰减分数（0~1）。

        使用指数衰减：24小时内优先，7天后衰减至 0.3。
        记忆的 updated_at 优先于 created_at。

        Args:
            hit: 记忆条目。
            now: 当前时间戳。

        Returns:
            时间衰减分数。
        """
        age_seconds = now - max(hit.updated_at, hit.created_at)
        age_hours = age_seconds / 3600.0

        # 24小时内：近乎满分
        if age_hours <= 24:
            return max(0.5, 1.0 - age_hours / 48.0)

        # 7天内：逐渐衰减
        if age_hours <= 168:  # 7天
            return max(0.2, 0.8 - (age_hours - 24) / 360.0)

        # 超过7天：低分
        return max(0.05, 0.2 - (age_hours - 168) / 7200.0)
