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
    # V6.1: token 预算相关字段
    token_budget: int = 0
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0
    compression_ratio: float = 0.0
    blocked: bool = False


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

    # ------------------------------------------------------------------
    # V6.1: Token Budget Enforcement
    # ------------------------------------------------------------------

    def enforce_budget(
        self,
        decision: CompressionDecision,
        token_budget: int,
    ) -> CompressionDecision:
        """在不丢 protected_items 的前提下压缩普通 items。

        算法：
        1. protected_items 全部保留，不允许被丢弃
        2. 如果 protected_items 本身已经超过预算 → blocked=True，返回风险说明
        3. 否则按"非保护 items 的优先级"从低到高丢弃，直到预算内
        4. 生成 summary_zh 和压缩统计数据

        Args:
            decision: protect() 方法生成的原始决策。
            token_budget: token 预算上限。

        Returns:
            更新后的 CompressionDecision（包含 kept/dropped 最终分配）。
        """
        # Token 估算（简单：content 长度 / 2 近似 token 数）
        def _estimate(content: str) -> int:
            return max(1, len(content) // 2)

        protected = list(decision.protected_items)
        non_protected = list(decision.kept_items)  # 非保护但候选保留的 items

        # 计算 protected 的 token 总量
        protected_tokens = sum(_estimate(str(i.get("content", ""))) for i in protected)
        total_before_tokens = protected_tokens + sum(
            _estimate(str(i.get("content", ""))) for i in non_protected
        )

        decision.estimated_tokens_before = total_before_tokens
        decision.token_budget = token_budget

        # 情况 1: protected_items 本身就超预算
        if protected_tokens > token_budget:
            decision.blocked = True
            decision.risk_flags.append(
                f"保护条目总 token({protected_tokens}) 超过预算({token_budget})，"
                f"不能丢弃受保护条目。建议增大 token_budget 到至少 {protected_tokens * 2}。"
            )
            decision.estimated_tokens_after = protected_tokens
            decision.compression_ratio = 0.0
            decision.summary_zh = (
                f"压缩被阻止: protected_items 已有 {protected_tokens} tokens，"
                f"超过了 {token_budget} 预算上限。"
            )
            self._last_decision = decision
            return decision

        # 情况 2: 正常压缩 — 从非保护 items 中按优先级丢弃
        # 优先级排序（低优先级的先丢弃）：
        #   - type="secondary" 最先丢
        #   - 短内容（len < 20）优先丢
        #   - 无 confidence 的先丢
        def _priority(item: dict) -> int:
            """返回优先级得分，越低越先被丢弃。"""
            score = 0
            if item.get("type") == "secondary":
                score -= 20
            content_len = len(str(item.get("content", "")))
            if content_len < 20:
                score -= 10
            if not item.get("confidence"):
                score -= 5
            return score

        sorted_items = sorted(non_protected, key=_priority)
        kept: list[dict] = []
        dropped: list[dict] = []
        current_tokens = protected_tokens

        for item in sorted_items:
            item_tokens = _estimate(str(item.get("content", "")))
            if current_tokens + item_tokens <= token_budget:
                kept.append(item)
                current_tokens += item_tokens
            else:
                dropped.append(item)

        decision.estimated_tokens_after = current_tokens
        decision.compression_ratio = (
            (total_before_tokens - current_tokens) / total_before_tokens
            if total_before_tokens > 0
            else 0.0
        )
        decision.blocked = False

        # 更新 kept/dropped 列表
        decision.kept_items = kept
        decision.dropped_items = dropped
        # protected_items 保持不变（必然保留）

        decision.summary_zh = (
            f"压缩完成: {protected_tokens} tokens (受保护) + {current_tokens - protected_tokens} tokens (普通保留) "
            f"= {current_tokens} / {token_budget} tokens | "
            f"丢弃 {len(dropped)} 条, 保留 {len(protected) + len(kept)} 条"
        )
        if decision.risk_flags:
            decision.summary_zh += f" | 风险: {'; '.join(decision.risk_flags)}"

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
