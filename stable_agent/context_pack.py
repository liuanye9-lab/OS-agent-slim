"""StableAgent OS 上下文包构建模块。

本模块提供 ContextTriage（上下文筛选排序压缩）和 ContextPackBuilder
（ContextPack 工厂）两个核心类，负责将记忆、RAG 检索结果和规则
组装为符合 Token 预算的上下文包。

模块职责：
- 四阶段上下文构建：筛选 → 去重 → 排序 → 压缩
- 缓存/易变上下文分离
- 关键提醒提取
"""

from __future__ import annotations

import uuid
from typing import Optional

from stable_agent.models import ContextItem, ContextPack, MemoryItem, TaskType
from stable_agent.token_meter import TokenMeter


# ============================================================================
# ContextTriage — 上下文筛选排序压缩
# ============================================================================


class ContextTriage:
    """上下文筛选、排序与压缩器。

    将记忆、RAG 检索结果和规则按四阶段流程构建为 ContextPack：
    Stage 1: 筛选 — 删除低相关度条目
    Stage 2: 去重 — Jaccard 相似度去重
    Stage 3: 排序 — 按 placement 和来源类型排序
    Stage 4: 压缩 — 超预算时从尾部剔除低优先级条目

    Attributes:
        token_meter: Token 计量器实例，用于估算 token 数。
    """

    # 相关性最低阈值
    MIN_RELEVANCE_SCORE: float = 0.2
    # Jaccard 相似度去重阈值
    DEDUP_JACCARD_THRESHOLD: float = 0.8
    # 默认 placement
    DEFAULT_PLACEMENT: str = "middle"

    def __init__(self, token_meter: Optional[TokenMeter] = None) -> None:
        """初始化 ContextTriage。

        Args:
            token_meter: Token 计量器，None 时自动创建默认实例。
        """
        self.token_meter = token_meter if token_meter is not None else TokenMeter()

    # ------------------------------------------------------------------
    # Stage 1: 筛选
    # ------------------------------------------------------------------

    def _filter_memories(
        self, memories: list[MemoryItem]
    ) -> list[MemoryItem]:
        """筛选记忆：剔除 relevance_score < MIN_RELEVANCE_SCORE 的条目。

        每个 MemoryItem 的 relevance_score = priority * confidence。

        Args:
            memories: 原始记忆列表。

        Returns:
            筛选后的记忆列表。
        """
        filtered: list[MemoryItem] = []
        for mem in memories:
            relevance = mem.priority * mem.confidence
            if relevance >= self.MIN_RELEVANCE_SCORE:
                filtered.append(mem)
        return filtered

    def _filter_rag_chunks(self, rag_chunks: list[dict]) -> list[dict]:
        """筛选 RAG 块：剔除 score 字段 < MIN_RELEVANCE_SCORE 的条目。

        Args:
            rag_chunks: 原始 RAG 块列表。

        Returns:
            筛选后的 RAG 块列表。
        """
        filtered: list[dict] = []
        for chunk in rag_chunks:
            score = chunk.get("score", 0.0)
            if score >= self.MIN_RELEVANCE_SCORE:
                filtered.append(chunk)
        return filtered

    # ------------------------------------------------------------------
    # Stage 2: 去重
    # ------------------------------------------------------------------

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """计算两个文本的字符级 Jaccard 相似度。

        使用字符集合的交集大小 / 并集大小。

        Args:
            text_a: 文本 A。
            text_b: 文本 B。

        Returns:
            Jaccard 相似度，范围 [0.0, 1.0]。
        """
        if not text_a and not text_b:
            return 1.0
        set_a = set(text_a)
        set_b = set(text_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        intersection = len(set_a & set_b)
        return intersection / union

    @staticmethod
    def _get_memory_relevance(mem: MemoryItem) -> float:
        """获取 MemoryItem 的综合相关度分数。

        Args:
            mem: 记忆条目。

        Returns:
            priority * confidence 的值。
        """
        return mem.priority * mem.confidence

    @staticmethod
    def _get_rag_score(chunk: dict) -> float:
        """获取 RAG 块的分数。

        Args:
            chunk: RAG 块字典。

        Returns:
            score 字段值，默认 0.0。
        """
        return chunk.get("score", 0.0)

    @staticmethod
    def _get_item_content(item: MemoryItem | dict) -> str:
        """获取条目的文本内容。

        Args:
            item: MemoryItem 或 RAG 块字典。

        Returns:
            文本内容字符串。
        """
        if isinstance(item, MemoryItem):
            return item.content
        return item.get("content", "")

    def _deduplicate_items(
        self, items: list[MemoryItem | dict]
    ) -> list[MemoryItem | dict]:
        """基于内容 Jaccard 相似度去重。

        比较相邻条目，如果 Jaccard 相似度 > DEDUP_JACCARD_THRESHOLD，
        保留分数（relevance_score）更高的条目。

        Args:
            items: 待去重的条目列表（MemoryItem 或 RAG 块 dict）。

        Returns:
            去重后的条目列表。
        """
        if len(items) <= 1:
            return list(items)

        # 先按分数降序排列，使高分的排在前面
        sorted_items = sorted(
            items,
            key=lambda x: (
                self._get_memory_relevance(x)
                if isinstance(x, MemoryItem)
                else self._get_rag_score(x)
            ),
            reverse=True,
        )

        result: list[MemoryItem | dict] = [sorted_items[0]]
        for item in sorted_items[1:]:
            content = self._get_item_content(item)
            is_duplicate = False
            for existing in result:
                existing_content = self._get_item_content(existing)
                sim = self._jaccard_similarity(content, existing_content)
                if sim > self.DEDUP_JACCARD_THRESHOLD:
                    is_duplicate = True
                    break
            if not is_duplicate:
                result.append(item)

        return result

    # ------------------------------------------------------------------
    # Stage 3: 排序
    # ------------------------------------------------------------------

    def _to_context_items(
        self, memories: list[MemoryItem], rag_chunks: list[dict]
    ) -> list[ContextItem]:
        """将 MemoryItem 和 RAG 块统一转换为 ContextItem 列表。

        Args:
            memories: 筛选去重后的记忆列表。
            rag_chunks: 筛选去重后的 RAG 块列表。

        Returns:
            ContextItem 列表。
        """
        items: list[ContextItem] = []

        # 转换 MemoryItem → ContextItem
        for mem in memories:
            relevance = self._get_memory_relevance(mem)
            content = mem.content
            token_est = self.token_meter.estimate_tokens(content)
            placement = "top" if mem.layer == "hot" else self.DEFAULT_PLACEMENT
            item = ContextItem(
                id=f"mem:{mem.id}",
                content=content,
                source_type="memory",
                source_id=mem.id,
                priority=mem.priority,
                relevance_score=relevance,
                token_estimate=token_est,
                reason=f"记忆: {mem.type}",
                risk=None,
                placement=placement,
            )
            items.append(item)

        # 转换 RAG chunk → ContextItem
        for chunk in rag_chunks:
            content = chunk.get("content", "")
            token_est = self.token_meter.estimate_tokens(content)
            score = chunk.get("score", 0.0)
            chunk_id = chunk.get("chunk_id", str(uuid.uuid4())[:8])
            risk = chunk.get("risk", None)
            item = ContextItem(
                id=f"rag:{chunk_id}",
                content=content,
                source_type="rag",
                source_id=chunk.get("source_path", chunk_id),
                priority=score,
                relevance_score=score,
                token_estimate=token_est,
                reason=chunk.get("why_relevant", "RAG 检索结果"),
                risk=risk,
                placement=self.DEFAULT_PLACEMENT,
            )
            items.append(item)

        # 转换规则 → ContextItem
        for rule in []:  # rules will be added separately
            pass

        return items

    def _add_rule_items(
        self, items: list[ContextItem], rules: list[str]
    ) -> list[ContextItem]:
        """将规则字符串转换为 ContextItem 并追加到列表。

        规则条目默认 placement="bottom"。

        Args:
            items: 已有的 ContextItem 列表。
            rules: 规则字符串列表。

        Returns:
            追加规则后的 ContextItem 列表。
        """
        for i, rule_text in enumerate(rules):
            token_est = self.token_meter.estimate_tokens(rule_text)
            item = ContextItem(
                id=f"rule:{i}",
                content=rule_text,
                source_type="rule",
                source_id=f"rule:{i}",
                priority=0.9,  # 规则默认高优先级
                relevance_score=1.0,  # 规则总是相关
                token_estimate=token_est,
                reason="关键规则",
                risk=None,
                placement="bottom",
            )
            items.append(item)
        return items

    @staticmethod
    def _sort_items(items: list[ContextItem]) -> list[ContextItem]:
        """按 placement 和 source_type 排序。

        排序规则：
        1. placement="top" 排最前面
        2. placement="middle" 排中间
        3. placement="bottom" 排最后
        4. 同一 placement 内，memory 类型优先于 rag 类型

        Args:
            items: 待排序的 ContextItem 列表。

        Returns:
            排序后的 ContextItem 列表。
        """
        placement_order = {"top": 0, "middle": 1, "bottom": 2}
        source_order = {"memory": 0, "rag": 1, "rule": 2, "system": 3, "user": 4}

        def _sort_key(item: ContextItem) -> tuple:
            p = placement_order.get(item.placement, 1)
            s = source_order.get(item.source_type, 5)
            # 同 placement 同 source_type 时按 priority 降序
            return (p, s, -item.priority)

        return sorted(items, key=_sort_key)

    # ------------------------------------------------------------------
    # Stage 4: 压缩
    # ------------------------------------------------------------------

    def _compact_items(
        self, items: list[ContextItem], budget: int
    ) -> tuple[list[ContextItem], dict]:
        """超预算时从末尾剔除低优先级条目。

        按 token_estimate 累加，超过 budget 时从末尾剔除。
        剔除原因写入 compaction_report.reason。

        Args:
            items: 排序后的 ContextItem 列表。
            budget: Token 预算上限。

        Returns:
            (保留的条目列表, 压缩报告) 元组。
        """
        total_tokens = 0
        kept: list[ContextItem] = []
        removed_ids: list[str] = []
        removal_reasons: list[str] = []

        for item in items:
            new_total = total_tokens + item.token_estimate
            if new_total <= budget:
                kept.append(item)
                total_tokens = new_total
            else:
                removed_ids.append(item.id)
                reason = (
                    f"超预算: 累计 {total_tokens} tokens, "
                    f"加入 '{item.id}' (需 {item.token_estimate} tokens) "
                    f"将超出预算 {budget}"
                )
                removal_reasons.append(reason)

        compaction_report: dict = {
            "before_count": len(items),
            "after_count": len(kept),
            "removed_ids": removed_ids,
            "total_tokens_after": total_tokens,
            "budget": budget,
            "reason": "; ".join(removal_reasons) if removal_reasons else "预算充足，无需压缩",
            "compression_ratio": (
                round(1.0 - (len(kept) / len(items)), 4)
                if items
                else 0.0
            ),
        }

        return kept, compaction_report

    # ------------------------------------------------------------------
    # 公共 API: 完整四阶段流程
    # ------------------------------------------------------------------

    # 知识类关键词，用于标记系统级上下文
    KNOWLEDGE_KEYWORDS: set[str] = {
        "知识", "参考", "文档", "规范", "标准", "规则",
        "knowledge", "reference", "document", "standard",
    }

    def build_context_pack(
        self,
        task_input: str,
        task_type: TaskType,
        memories: list[MemoryItem],
        rag_chunks: list[dict],
        rules: list[str] | None = None,
        budget: int = 8000,
        run_id: str = "",
    ) -> ContextPack:
        """完整的四阶段上下文包构建流程。

        Stage 1: 筛选 — 删除 relevance_score < 0.2 的项。
        Stage 2: 去重 — 基于 content Jaccard 相似度 > 0.8 去重，保留高分的。
        Stage 3: 排序 — 高优先级放 top，普通放 middle，规则放 bottom。
        Stage 4: 压缩 — 超预算时从低优先级剔除，生成 compaction_report。

        Args:
            task_input: 用户任务输入文本。
            task_type: 任务类型。
            memories: 记忆列表。
            rag_chunks: RAG 检索块列表，每项为 dict。
            rules: 规则字符串列表，默认为空。
            budget: Token 预算上限，默认 8000。
            run_id: 运行 ID，空字符串时自动生成。

        Returns:
            构建完成的 ContextPack 实例。
        """
        if rules is None:
            rules = []

        # Stage 1: 筛选
        filtered_memories = self._filter_memories(memories)
        filtered_rag = self._filter_rag_chunks(rag_chunks)

        # Stage 2: 去重
        deduped_memories = self._deduplicate_items(filtered_memories)
        deduped_rag = self._deduplicate_items(filtered_rag)

        # Stage 3: 转换 + 排序
        context_items = self._to_context_items(deduped_memories, deduped_rag)
        context_items = self._add_rule_items(context_items, rules)
        sorted_items = self._sort_items(context_items)

        # Stage 4: 压缩
        kept_items, compaction_report = self._compact_items(
            sorted_items, budget
        )

        # 计算总 token 数
        total_tokens = sum(item.token_estimate for item in kept_items)

        # 生成 pack_id
        pack_id = f"pack:{run_id}:{uuid.uuid4().hex[:8]}"

        return ContextPack(
            pack_id=pack_id,
            run_id=run_id,
            task_input=task_input,
            task_type=task_type,
            items=kept_items,
            total_tokens=total_tokens,
            budget_limit=budget,
            compaction_report=compaction_report,
        )


# ============================================================================
# ContextPackBuilder — ContextPack 工厂
# ============================================================================


class ContextPackBuilder:
    """ContextPack 构建器工厂。

    使用 ContextTriage 构建完整的 ContextPack，并提供
    缓存/易变上下文分离和关键提醒提取功能。

    Attributes:
        triage: ContextTriage 实例。
    """

    def __init__(self, triage: ContextTriage) -> None:
        """初始化 ContextPackBuilder。

        Args:
            triage: ContextTriage 实例，用于构建上下文包。
        """
        self.triage = triage

    def from_memories_and_rag(
        self,
        task_input: str,
        task_type: TaskType,
        memories: list[MemoryItem],
        rag_chunks: list[dict],
        budget: int = 8000,
        run_id: str = "",
    ) -> ContextPack:
        """从记忆和 RAG 检索结果构建 ContextPack。

        这是 ContextTriage.build_context_pack 的便捷封装。

        Args:
            task_input: 用户任务输入文本。
            task_type: 任务类型。
            memories: 记忆列表。
            rag_chunks: RAG 检索块列表。
            budget: Token 预算上限，默认 8000。
            run_id: 运行 ID。

        Returns:
            构建完成的 ContextPack。
        """
        return self.triage.build_context_pack(
            task_input=task_input,
            task_type=task_type,
            memories=memories,
            rag_chunks=rag_chunks,
            rules=None,
            budget=budget,
            run_id=run_id,
        )

    def get_cacheable_prefix(self, pack: ContextPack) -> str:
        """抽取稳定的系统说明 + 项目常量作为 cacheable_prefix。

        提取 source_type 为 "system" 或 "rule" 的 ContextItem 内容，
        这些内容在多次运行之间通常是稳定的。

        Args:
            pack: 上下文包。

        Returns:
            可缓存的前缀字符串。
        """
        stable_items: list[str] = []
        for item in pack.items:
            if item.source_type in ("system", "rule"):
                stable_items.append(item.content)

        if not stable_items:
            # 如果没有 system/rule 类型，退而取 placement=bottom 的规则项
            for item in pack.items:
                if item.placement == "bottom" and item.source_type != "memory":
                    stable_items.append(item.content)
                    break

        return "\n\n".join(stable_items)

    def get_volatile_context(self, pack: ContextPack) -> str:
        """抽取每轮变化的任务上下文作为 volatile_context。

        提取 source_type 为 "memory"、"rag" 或 "user" 的 ContextItem 内容，
        以及任务输入本身。这些内容在每轮运行中都会变化。

        Args:
            pack: 上下文包。

        Returns:
            易变上下文字符串。
        """
        volatile_items: list[str] = []

        # 任务输入总是易变的
        if pack.task_input:
            volatile_items.append(f"任务: {pack.task_input}")

        for item in pack.items:
            if item.source_type in ("memory", "rag", "user"):
                volatile_items.append(item.content)

        return "\n\n".join(volatile_items)

    def get_critical_reminders(self, pack: ContextPack) -> list[str]:
        """抽取 placement="bottom" 的关键提醒。

        Args:
            pack: 上下文包。

        Returns:
            关键提醒字符串列表。
        """
        reminders: list[str] = []
        for item in pack.items:
            if item.placement == "bottom":
                reminders.append(item.content)
        # 同时检查 compaction_report 中是否有被移除的关键规则
        if pack.compaction_report:
            removed_ids = pack.compaction_report.get("removed_ids", [])
            if removed_ids:
                reminders.append(
                    f"注意：以下上下文因预算限制被剔除，可能需要额外检索: "
                    f"{', '.join(removed_ids)}"
                )
        return reminders
