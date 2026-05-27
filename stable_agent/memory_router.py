"""记忆路由模块 — 记忆库底层存储与高级检索接口。

本模块提供两层抽象：
- MemoryBank: 底层记忆存储，负责 CRUD 操作和冲突检测
- MemoryRouter: 高级接口，封装任务感知的检索和添加逻辑

记忆系统是 StableAgent OS 的"长期记忆"，存储用户偏好、
项目约束、成功案例和失败案例，用于改进后续任务的执行质量。

模块职责：
- 记忆的增删改查
- 基于任务类型的相关性检索
- 记忆冲突检测
- 记忆生命周期管理（candidate → active → outdated）
- 分层检索（hot → warm → cold）
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional

from stable_agent.models import MemoryItem, TaskType


# ============================================================================
# MemoryBank — 底层记忆存储
# ============================================================================


class MemoryBank:
    """记忆库底层存储。

    使用内存中的 list 存储所有 MemoryItem。不提供持久化。
    （# STUB: 未来可迁移到向量数据库实现语义检索）

    Attributes:
        _items: 内部记忆条目列表。
    """

    def __init__(self) -> None:
        """初始化空的记忆库。"""
        self._items: list[MemoryItem] = []

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def add_item(self, item: MemoryItem) -> None:
        """添加或覆盖记忆条目。

        若 item.id 在库中已存在，则用新条目覆盖旧条目；
        否则追加到列表末尾。

        Args:
            item: 要添加的记忆条目。
        """
        for i, existing in enumerate(self._items):
            if existing.id == item.id:
                self._items[i] = item
                return
        self._items.append(item)

    def mark_outdated(self, item_id: str) -> None:
        """将指定记忆条目标记为过期。

        将 status 设为 "outdated" 后，该条目在 query_relevant
        中不再被返回，但不会被物理删除。

        Args:
            item_id: 要标记的记忆条目 ID。
        """
        for item in self._items:
            if item.id == item_id:
                item.status = "outdated"
                return

    def query_relevant(
        self,
        task: TaskType,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """查询与指定任务类型最相关的记忆条目。

        相关性计算：
        - 基础分为 priority（0~1）
        - BUG_FIX 时 bad_case 获得 +0.5 的 type_weight
        - UI_DESIGN 时 success_case 获得 +0.5 的 type_weight
        - 其他 type_weight 为 0
        - 最终分数 = priority * (1 + type_weight)

        # STUB: 未来可用向量相似度替代当前的关键词匹配策略。

        Args:
            task: 当前任务类型。
            top_k: 返回的最大条目数，默认 5。

        Returns:
            按相关性分数降序排列的记忆条目列表。
        """
        # 仅 active 条目参与检索
        active: list[MemoryItem] = [
            m for m in self._items if m.status == "active"
        ]

        if not active:
            return []

        def relevance_score(item: MemoryItem) -> float:
            """计算记忆条目对当前任务类型的相关性分数。"""
            type_weight: float = 0.0
            if task in (TaskType.BUG_FIX, TaskType.ARCH_REFACTOR):
                if item.type == "bad_case":
                    type_weight = 0.5
            elif task in (TaskType.UI_DESIGN, TaskType.PROMPT_OPTIMIZATION):
                if item.type == "success_case":
                    type_weight = 0.5
            return item.priority * (1.0 + type_weight)

        scored: list[tuple[MemoryItem, float]] = [
            (m, relevance_score(m)) for m in active
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)

        return [item for item, _ in scored[:top_k]]

    def detect_conflicts(
        self,
        new_item: MemoryItem,
    ) -> list[MemoryItem]:
        """检测新记忆条目与现有记忆的冲突。

        冲突检测基于 Jaccard 相似度：
        - 将每条记忆的 content 分词为词集合
        - 计算 new_item 与每条 active 记忆的 Jaccard 相似度
        - 相似度 > 0.3 视为冲突

        Args:
            new_item: 待检测的新记忆条目。

        Returns:
            与 new_item 冲突的现有记忆条目列表。
        """
        new_tokens: set[str] = self._tokenize(new_item.content)
        if not new_tokens:
            return []

        conflicts: list[MemoryItem] = []
        for item in self._items:
            if item.status != "active":
                continue
            if item.id == new_item.id:
                continue
            existing_tokens: set[str] = self._tokenize(item.content)
            if not existing_tokens:
                continue
            jaccard: float = self._jaccard(new_tokens, existing_tokens)
            if jaccard > 0.3:
                conflicts.append(item)

        return conflicts

    def compact_memory(self) -> dict:
        """记忆压缩：将 usage_count=0 且 priority<0.3 的 active 记忆降级为 cold。

        遍历所有 active 条目，将长时间未使用且低优先级的记忆
        标记为 cold 层，释放热记忆空间。

        Returns:
            {"demoted": count, "total": len(self._items)} 字典。

        Examples:
            >>> bank = MemoryBank()
            >>> item = MemoryItem(id="1", content="old", type="test", priority=0.1)
            >>> bank.add_item(item)
            >>> result = bank.compact_memory()
            >>> result["demoted"]
            1
            >>> item.layer
            'cold'
        """
        demoted_count: int = 0
        for item in self._items:
            if item.status == "active" and item.usage_count == 0 and item.priority < 0.3:
                item.layer = "cold"
                demoted_count += 1

        return {
            "demoted": demoted_count,
            "total": len(self._items),
        }

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """将文本拆分为词集合（基于空格和中文字符边界）。

        Args:
            text: 输入文本。

        Returns:
            词集合。
        """
        # 简单策略：按空格和标点分词，同时将中文字符拆为单字
        tokens: set[str] = set()
        # 先按非字母数字和非中文字符分割

        parts: list[str] = re.split(r"[^\w\u4e00-\u9fff]+", text.lower())
        for part in parts:
            if not part:
                continue
            # 纯英文/数字——作为整体 token
            if part.isascii():
                tokens.add(part)
            else:
                # 混合或纯中文——按字符拆
                tokens.update(part)
        return tokens

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        """计算两个集合的 Jaccard 相似度。

        Args:
            a: 集合 A。
            b: 集合 B。

        Returns:
            Jaccard 相似度，范围 [0, 1]。
        """
        union: set[str] = a | b
        if not union:
            return 0.0
        return len(a & b) / len(union)


# ============================================================================
# MemoryRouter — 高级记忆检索接口
# ============================================================================


class MemoryRouter:
    """记忆路由 — MemoryBank 的高级接口。

    封装任务感知的检索策略，对外提供简洁的查询和添加接口。
    通过依赖注入持有 MemoryBank 实例。

    Attributes:
        bank: 底层 MemoryBank 实例。
    """

    def __init__(self, bank: MemoryBank) -> None:
        """初始化记忆路由。

        Args:
            bank: 底层 MemoryBank 实例（依赖注入）。
        """
        self.bank: MemoryBank = bank

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def query_for_task(
        self,
        task_input: str,
        task_type: TaskType,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """根据任务输入和类型检索相关记忆。

        在 MemoryBank.query_relevant 的基础上，额外根据 task_input
        中的关键词对结果进行加权筛选：如果记忆的 content 中包含
        task_input 中的任意关键词，提升其排序位置。

        Args:
            task_input: 用户原始任务输入。
            task_type: 推断的任务类型。
            top_k: 返回的最大条目数。

        Returns:
            加权后的相关记忆列表。
        """
        candidates: list[MemoryItem] = self.bank.query_relevant(
            task_type, top_k=top_k * 2  # 多取一些候选再进行关键词加权
        )

        if not candidates:
            return []

        # 从 task_input 中提取关键词（长度 >= 2 的词）
        input_keywords: set[str] = self._extract_keywords(task_input)

        def keyword_boost(item: MemoryItem) -> float:
            """计算关键词命中加成。"""
            boost: float = 0.0
            content_lower: str = item.content.lower()
            for kw in input_keywords:
                if kw.lower() in content_lower:
                    boost += 0.1
            # 重新计算基础相关性分数
            type_weight: float = 0.0
            if task_type in (TaskType.BUG_FIX, TaskType.ARCH_REFACTOR):
                if item.type == "bad_case":
                    type_weight = 0.5
            elif task_type in (TaskType.UI_DESIGN, TaskType.PROMPT_OPTIMIZATION):
                if item.type == "success_case":
                    type_weight = 0.5
            return item.priority * (1.0 + type_weight) + boost

        boosted: list[tuple[MemoryItem, float]] = [
            (m, keyword_boost(m)) for m in candidates
        ]
        boosted.sort(key=lambda pair: pair[1], reverse=True)

        return [item for item, _ in boosted[:top_k]]

    def add_experience(
        self,
        content: str,
        item_type: str,
        priority: float,
        source: str,
    ) -> MemoryItem:
        """添加一条新的经验记忆。

        自动生成 UUID 和时间戳，创建 MemoryItem 并写入 MemoryBank。

        Args:
            content: 记忆文本内容。
            item_type: 记忆类型（user_pref / success_case / bad_case 等）。
            priority: 优先级 0.0~1.0。
            source: 来源标识（如工作流 ID）。

        Returns:
            创建的 MemoryItem 实例。

        Raises:
            ValueError: 如果 priority 不在 [0, 1] 范围内。
        """
        item: MemoryItem = MemoryItem(
            id=str(uuid.uuid4()),
            content=content,
            type=item_type,
            timestamp=time.time(),
            priority=priority,
            source=source,
            status="active",
        )
        self.bank.add_item(item)
        return item

    def add_memory_candidate(
        self,
        content: str,
        item_type: str,
        source: str,
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        """添加到 candidate 队列（lifecycle=candidate），待确认后升级。

        候选记忆需要经过 promote_candidate 才能变为 active。

        Args:
            content: 记忆文本内容。
            item_type: 记忆类型（user_pref / success_case / bad_case 等）。
            source: 来源标识。
            confidence: 置信度，0.0~1.0，默认 0.5。
            tags: 标签列表，None 视为空列表。

        Returns:
            创建的 MemoryItem 实例（状态为 active，lifecycle=candidate）。

        Raises:
            ValueError: 如果 confidence 不在 [0, 1] 范围内。
        """
        if tags is None:
            tags = []

        item: MemoryItem = MemoryItem(
            id=str(uuid.uuid4()),
            content=content,
            type=item_type,
            timestamp=time.time(),
            priority=confidence,
            source=source,
            status="active",
            lifecycle="candidate",
            confidence=confidence,
            tags=tags,
        )
        self.bank.add_item(item)
        return item

    def promote_candidate(self, memory_id: str) -> None:
        """将 candidate → active。

        将指定记忆的 lifecycle 从 candidate 升级为 active，
        同时更新 priority 为 confidence 值。

        Args:
            memory_id: 要升级的记忆条目 ID。
        """
        for i, item in enumerate(self.bank._items):
            if item.id == memory_id and item.lifecycle == "candidate":
                item.lifecycle = "active"
                item.priority = max(item.priority, item.confidence)
                return

    def demote_memory(self, memory_id: str, reason: str = "") -> None:
        """将 active → outdated，附带失效原因。

        将指定记忆的 lifecycle 从 active 降级为 outdated，
        设置 invalid_at 为当前时间戳。

        Args:
            memory_id: 要降级的记忆条目 ID。
            reason: 失效原因说明。
        """
        for i, item in enumerate(self.bank._items):
            if item.id == memory_id and item.lifecycle == "active":
                item.lifecycle = "outdated"
                item.status = "outdated"
                item.invalid_at = time.time()
                # 将原因追加到 content 末尾
                if reason:
                    item.content = f"{item.content} [已失效: {reason}]"
                return

    def retrieve_by_task(
        self,
        task_input: str,
        task_type: TaskType,
        budget: int = 2000,
    ) -> list[MemoryItem]:
        """按任务分层检索：优先 hot → warm → cold。

        策略：
        1. 从 bank 中取所有 active 条目
        2. 按 layer 排序：hot → warm → cold
        3. 在同一 layer 内按 priority 降序
        4. 累计选取直到 token 估算超过 budget

        Args:
            task_input: 用户原始任务输入。
            task_type: 任务类型。
            budget: token 预算上限，默认 2000。

        Returns:
            分层检索后的记忆条目列表。
        """
        # 取所有 active 条目
        active_items: list[MemoryItem] = [
            m for m in self.bank._items if m.status == "active"
        ]

        if not active_items:
            return []

        # 分层排序：hot(0) → warm(1) → cold(2)，同层内 priority 降序
        layer_order: dict[str, int] = {"hot": 0, "warm": 1, "cold": 2}

        def layer_sort_key(item: MemoryItem) -> tuple:
            layer_rank: int = layer_order.get(item.layer, 1)
            return (layer_rank, -item.priority)

        sorted_items: list[MemoryItem] = sorted(active_items, key=layer_sort_key)

        # 累计选取
        result: list[MemoryItem] = []
        total_tokens: int = 0

        for item in sorted_items:
            est_tokens: int = max(1, len(item.content) // 4)
            if total_tokens + est_tokens > budget:
                break
            result.append(item)
            total_tokens += est_tokens

        return result

    def update_usage(self, memory_ids: list[str]) -> None:
        """批量更新 last_used_at 和 usage_count。

        对每个 memory_id 找到对应 MemoryItem，设置 last_used_at 为
        当前时间戳，usage_count += 1。

        Args:
            memory_ids: 要更新的记忆 ID 列表。
        """
        now: float = time.time()
        id_set: set[str] = set(memory_ids)

        for item in self.bank._items:
            if item.id in id_set:
                item.last_used_at = now
                item.usage_count += 1

    def detect_and_report_conflicts(
        self,
        new_item: MemoryItem,
    ) -> list[MemoryItem]:
        """检测新记忆条目是否与现有记忆冲突并报告。

        委托给 MemoryBank.detect_conflicts。

        Args:
            new_item: 待检测的新记忆条目。

        Returns:
            冲突的现有记忆条目列表。
        """
        return self.bank.detect_conflicts(new_item)

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """从文本中提取关键词（长度 >= 2 的 token）。

        Args:
            text: 输入文本。

        Returns:
            关键词集合。
        """
        tokens: set[str] = MemoryBank._tokenize(text)
        return {t for t in tokens if len(t) >= 2}
