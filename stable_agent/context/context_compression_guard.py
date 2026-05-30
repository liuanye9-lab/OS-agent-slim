"""ContextCompressionGuard — 上下文压缩保护守卫。

在压缩上下文之前，确保以下内容不会被压缩掉：
- 用户当前核心目标
- 最新项目约束
- 高置信度记忆
- 最近失败经验
- validation 通过的 skill rule
- 当前任务相关时间戳记忆

禁止：
- 压缩掉本次用户核心目标
- 压缩掉最新高置信度约束
- 让过期记忆覆盖新记忆
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from stable_agent.memory.temporal_memory_router import TemporalMemoryHit


@dataclass
class CompressionDecision:
    """上下文压缩后的决策记录。

    Attributes:
        kept_items: 保留的上下文条目。
        dropped_items: 被丢弃的条目。
        protected_items: 受保护（强制保留）的条目。
        risk_flags: 风险标记列表。
        summary_zh: 中文决策摘要。
    """

    kept_items: list[dict] = field(default_factory=list)
    dropped_items: list[dict] = field(default_factory=list)
    protected_items: list[dict] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    summary_zh: str = ""


class ContextCompressionGuard:
    """上下文压缩保护守卫。

    在上下文压缩之前执行保护检查，标记关键条目为 protected，
    防止被压缩逻辑丢弃。

    保护策略按优先级排序：
    1. 用户当前核心目标（最高优先级，不可丢弃）
    2. 最新项目约束（高优先级）
    3. 高置信度记忆（confidence >= 0.8）
    4. 最近失败经验（近 7 天内的 bad_case）
    5. validation 通过的 skill rule
    6. 当前任务相关时间戳记忆

    Attributes:
        _protection_rules: 保护规则名称列表（用于 summary_zh 生成）。
        _last_decision: 最近的压缩决策记录。
    """

    def __init__(self) -> None:
        """初始化空的保护规则列表。"""
        self._protection_rules: list[str] = []
        self._last_decision: CompressionDecision | None = None

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def protect(
        self,
        task_input: str,
        context_items: list[dict],
        temporal_memories: list["TemporalMemoryHit"] | None = None,
        token_budget: int = 8000,
    ) -> CompressionDecision:
        """在压缩前标记受保护条目。

        对每个 context_item 检查是否匹配保护规则，匹配则标记为 protected。
        保护规则优先级从高到低：
        1. 用户核心目标
        2. 项目约束
        3. 高置信度记忆
        4. 最近失败经验
        5. validation 通过的 skill rule
        6. 时间记忆

        Args:
            task_input: 用户原始任务输入。
            context_items: 待压缩的上下文条目列表，每条目为 {'content': str, 'type': str, ...}。
            temporal_memories: 时间记忆命中列表，用于交叉检查。
            token_budget: token 预算上限。

        Returns:
            CompressionDecision 包含 protected/kept/dropped 分类和风险标记。
        """
        if temporal_memories is None:
            temporal_memories = []

        protected: list[dict] = []
        dropped: list[dict] = []
        risk_flags: list[str] = []
        protection_reasons: list[str] = []

        # 提取任务目标关键词
        task_keywords = self._extract_keywords(task_input)

        for item in context_items:
            item_type = item.get("type", "")
            item_content = str(item.get("content", ""))
            is_protected = False
            reason = ""

            # 规则 1：用户核心目标（最高优先级）
            if item_type in ("user_goal", "task_input", "current_intent"):
                is_protected = True
                reason = "用户核心目标"
                protection_reasons.append(reason)

            # 规则 2：项目约束
            elif item_type in ("project_constraint", "project_rule", "system_rule"):
                is_protected = True
                reason = "项目约束"
                protection_reasons.append(reason)

            # 规则 3：高置信度记忆
            elif item_type in ("memory", "long_term_memory") and item.get("confidence", 0) >= 0.8:
                is_protected = True
                reason = "高置信度记忆"
                protection_reasons.append(reason)

            # 规则 4：最近失败经验（与时间记忆交叉检查）
            elif item_type in ("bad_case", "failure", "lesson_learned"):
                # 检查是否在 7 天内
                is_recent = self._is_recent(item, temporal_memories)
                if is_recent:
                    is_protected = True
                    reason = "最近失败经验"
                    protection_reasons.append(reason)

            # 规则 5：Validation 通过的 skill rule
            elif item_type in ("skill_rule", "skill_patch") and item.get("validated", False):
                is_protected = True
                reason = "已验证 skill rule"
                protection_reasons.append(reason)

            # 规则 6：时间记忆相关
            elif self._matches_temporal_memory(item_content, temporal_memories):
                is_protected = True
                reason = "时间记忆相关"
                protection_reasons.append(reason)

            if is_protected:
                item["_protected"] = True
                item["_protection_reason"] = reason
                protected.append(item)

        # 分类保留和丢弃
        kept = [item for item in context_items if item.get("_protected")]
        dropped = [item for item in context_items if not item.get("_protected")]

        # 风险检查
        if not kept:
            risk_flags.append("⚠️ 所有上下文条目均未被保护，可能丢失核心目标")
        if len(dropped) > len(kept) * 2:
            risk_flags.append("⚠️ 丢弃条目远多于保留条目，建议增大 token_budget")
        if any(item.get("type") == "user_goal" for item in dropped):
            risk_flags.append("🔴 严重：用户核心目标被丢弃！")

        # 生成摘要
        summary_zh = self._build_summary(
            task_input=task_input,
            protected_count=len(protected),
            dropped_count=len(dropped),
            protection_reasons=protection_reasons,
            risk_flags=risk_flags,
            token_budget=token_budget,
        )

        decision = CompressionDecision(
            kept_items=kept,
            dropped_items=dropped,
            protected_items=protected,
            risk_flags=risk_flags,
            summary_zh=summary_zh,
        )

        self._last_decision = decision
        return decision

    def get_last_decision(self) -> CompressionDecision | None:
        """获取最近的压缩决策记录。

        Returns:
            最近的 CompressionDecision 或 None。
        """
        return self._last_decision

    def get_protection_summary_zh(self) -> str:
        """获取保护规则摘要（中文）。

        Returns:
            保护规则摘要文本。
        """
        if self._last_decision is None:
            return "尚未执行压缩保护"
        return self._last_decision.summary_zh

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """从文本提取关键词（长度 >= 2 的 token）。

        Args:
            text: 输入文本。

        Returns:
            关键词集合。
        """
        import re
        tokens = set(
            t.lower()
            for t in re.split(r"[^\w\u4e00-\u9fff]+", text)
            if len(t) >= 2
        )
        return tokens

    @staticmethod
    def _is_recent(item: dict, temporal_memories: list["TemporalMemoryHit"]) -> bool:
        """检查条目是否在最近 7 天内的时间记忆中出现。

        Args:
            item: 上下文条目。
            temporal_memories: 时间记忆列表。

        Returns:
            True 表示最近出现过。
        """
        import time
        now = time.time()
        item_content = str(item.get("content", ""))

        for mem in temporal_memories:
            age_seconds = now - max(mem.updated_at, mem.created_at)
            if age_seconds <= 7 * 86400:  # 7天内
                if item_content and item_content in mem.content:
                    return True
        return False

    @staticmethod
    def _matches_temporal_memory(
        content: str, temporal_memories: list["TemporalMemoryHit"]
    ) -> bool:
        """检查内容是否与时间记忆相关。

        通过关键词交集判断是否匹配。

        Args:
            content: 内容文本。
            temporal_memories: 时间记忆列表。

        Returns:
            True 表示与某条时间记忆相关。
        """
        import re

        def tokenize(text: str) -> set[str]:
            return set(
                t.lower()
                for t in re.split(r"[^\w\u4e00-\u9fff]+", text)
                if len(t) >= 2
            )

        if not content or not temporal_memories:
            return False

        content_tokens = tokenize(content)
        for mem in temporal_memories:
            mem_tokens = tokenize(mem.content)
            intersection = content_tokens & mem_tokens
            if len(intersection) >= 2:  # 至少2个共同关键词
                return True
        return False

    @staticmethod
    def _build_summary(
        task_input: str,
        protected_count: int,
        dropped_count: int,
        protection_reasons: list[str],
        risk_flags: list[str],
        token_budget: int,
    ) -> str:
        """构建中文决策摘要。

        Args:
            task_input: 用户任务输入。
            protected_count: 保护条目数。
            dropped_count: 丢弃条目数。
            protection_reasons: 保护原因列表。
            risk_flags: 风险标记列表。
            token_budget: token 预算。

        Returns:
            中文摘要文本。
        """
        task_short = task_input[:40] + "..." if len(task_input) > 40 else task_input
        parts = [
            f"任务: {task_short}",
            f"Token预算: {token_budget}",
            f"保留: {protected_count}条, 丢弃: {dropped_count}条",
        ]

        if protection_reasons:
            unique_reasons = list(dict.fromkeys(protection_reasons))  # 去重保留顺序
            parts.append(f"保护策略: {' > '.join(unique_reasons[:4])}")

        if risk_flags:
            parts.append(f"风险: {'; '.join(risk_flags)}")
        else:
            parts.append("风险: 无")

        return " | ".join(parts)
