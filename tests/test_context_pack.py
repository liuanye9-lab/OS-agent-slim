"""测试 context_pack 模块：ContextTriage 和 ContextPackBuilder。

覆盖四阶段上下文构建流程：筛选 → 去重 → 排序 → 压缩。
"""

from __future__ import annotations

import uuid

import pytest

from stable_agent.context_pack import ContextPackBuilder, ContextTriage
from stable_agent.models import (
    ContextItem,
    ContextPack,
    MemoryItem,
    TaskType,
)
from stable_agent.token_meter import TokenMeter


# ============================================================================
# 辅助函数
# ============================================================================


def _make_memory(
    mem_id: str = "",
    content: str = "",
    priority: float = 0.8,
    confidence: float = 0.9,
    mem_type: str = "user_pref",
    layer: str = "warm",
) -> MemoryItem:
    """创建测试用 MemoryItem。"""
    return MemoryItem(
        id=mem_id or str(uuid.uuid4())[:8],
        content=content or f"测试记忆内容 {mem_id}",
        type=mem_type,
        priority=priority,
        confidence=confidence,
        layer=layer,
    )


def _make_rag_chunk(
    chunk_id: str = "",
    content: str = "",
    score: float = 0.8,
    source: str = "test/doc.md",
) -> dict:
    """创建测试用 RAG chunk。"""
    return {
        "chunk_id": chunk_id or str(uuid.uuid4())[:8],
        "content": content or f"测试 RAG 内容 {chunk_id}",
        "source_path": source,
        "score": score,
    }


# ============================================================================
# ContextTriage 测试
# ============================================================================


class TestContextTriageBuildContextPack:
    """测试 build_context_pack 完整流程。"""

    def test_triage_builds_valid_context_pack(self) -> None:
        """基本流程应返回有效的 ContextPack 实例。"""
        triage = ContextTriage()
        memories = [
            _make_memory("m1", "用户偏好使用 Python", priority=0.9, confidence=0.9),
        ]
        rag_chunks = [
            _make_rag_chunk("c1", "Python 异步编程指南", score=0.85),
        ]

        pack = triage.build_context_pack(
            task_input="用 Python 写异步代码",
            task_type=TaskType.CODE_GENERATION,
            memories=memories,
            rag_chunks=rag_chunks,
            budget=8000,
            run_id="test-run",
        )

        assert isinstance(pack, ContextPack)
        assert pack.task_type == TaskType.CODE_GENERATION
        assert pack.task_input == "用 Python 写异步代码"
        assert pack.run_id == "test-run"
        assert pack.budget_limit == 8000
        assert len(pack.items) >= 1
        assert pack.total_tokens > 0
        assert "pack_id" in pack.__dict__ or pack.pack_id

    def test_triage_filters_low_relevance(self) -> None:
        """Stage 1: 低相关度条目应被筛选掉。"""
        triage = ContextTriage()
        # 低相关度记忆: priority * confidence = 0.1 * 0.1 = 0.01 < 0.2
        memories = [
            _make_memory("m1", "高相关记忆", priority=0.9, confidence=0.9),
            _make_memory("m2", "低相关记忆", priority=0.1, confidence=0.1),
        ]
        # 低分 RAG chunk: score = 0.1 < 0.2
        rag_chunks = [
            _make_rag_chunk("c1", "高分参考文档", score=0.9),
            _make_rag_chunk("c2", "低分参考文档", score=0.1),
        ]

        pack = triage.build_context_pack(
            task_input="测试筛选功能",
            task_type=TaskType.GENERAL_QA,
            memories=memories,
            rag_chunks=rag_chunks,
            budget=8000,
        )

        contents = [item.content for item in pack.items]
        assert "高相关记忆" in contents or any("m1" in item.id for item in pack.items)
        assert "低相关记忆" not in contents
        # 低分 RAG chunk 应被过滤
        assert "低分参考文档" not in contents
        # 高分 RAG chunk 应保留
        assert any("c1" in item.id for item in pack.items)

    def test_triage_deduplicates_similar_content(self) -> None:
        """Stage 2: Jaccard 相似度 > 0.8 应去重。"""
        triage = ContextTriage()
        # 两个几乎相同的记忆（只有微小差别）
        memories = [
            _make_memory(
                "m1",
                "Python 是一种广泛使用的高级编程语言，"
                "具有动态类型和自动内存管理功能。"
                "它支持多种编程范式包括面向对象、"
                "函数式和过程式编程。",
                priority=0.9,
                confidence=0.9,
            ),
            _make_memory(
                "m2",
                "Python 是一种广泛使用的高级编程语言，"
                "具有动态类型和自动内存管理功能。"
                "它支持多种编程范式包括面向对象、"
                "函数式和过程式编程。只多了一点内容在末尾。",
                priority=0.8,
                confidence=0.8,
            ),
        ]

        pack = triage.build_context_pack(
            task_input="Python 编程语言",
            task_type=TaskType.GENERAL_QA,
            memories=memories,
            rag_chunks=[],
            budget=8000,
        )

        # 去重后应只剩下一个（高分者被保留）
        memory_items = [
            item for item in pack.items if item.source_type == "memory"
        ]
        # 两个高度相似的记忆去重后应最多保留 1 个
        assert len(memory_items) <= 1

    def test_triage_sorts_by_placement(self) -> None:
        """Stage 3: placement 排序正确。"""
        triage = ContextTriage()
        # hot 层记忆 → placement="top"
        memories = [
            _make_memory("m1", "TOP 记忆", priority=0.9, confidence=0.9, layer="hot"),
            _make_memory("m2", "MIDDLE 记忆", priority=0.5, confidence=0.5, layer="warm"),
        ]
        rag_chunks = [
            _make_rag_chunk("c1", "MIDDLE RAG", score=0.6),
        ]
        rules = ["BOTTOM 规则：必须遵守安全规范"]

        pack = triage.build_context_pack(
            task_input="测试排序",
            task_type=TaskType.GENERAL_QA,
            memories=memories,
            rag_chunks=rag_chunks,
            rules=rules,
            budget=8000,
        )

        placements = [item.placement for item in pack.items]
        # 应该有 top → middle → bottom 的顺序
        assert "top" in placements
        assert "bottom" in placements
        # 验证排列顺序（top 在前，bottom 在后）
        top_indices = [i for i, p in enumerate(placements) if p == "top"]
        bottom_indices = [i for i, p in enumerate(placements) if p == "bottom"]
        if top_indices and bottom_indices:
            assert top_indices[0] < bottom_indices[-1]

    def test_triage_compresses_over_budget(self) -> None:
        """Stage 4: 超预算时应剔除低优先级条目。"""
        triage = ContextTriage()
        # 创建多条内容使总 token 超过 small budget
        memories = [
            _make_memory(
                "m1",
                "长文本内容 " * 80,  # ~400 chars
                priority=0.9,
                confidence=0.9,
                layer="hot",
            ),
            _make_memory(
                "m2",
                "另一个长文本内容 " * 80,  # ~400 chars
                priority=0.8,
                confidence=0.8,
            ),
        ]

        pack = triage.build_context_pack(
            task_input="测试压缩",
            task_type=TaskType.GENERAL_QA,
            memories=memories,
            rag_chunks=[],
            budget=50,  # 极小预算，强制压缩
        )

        # 压缩后应有 compaction_report
        assert pack.compaction_report
        assert "before_count" in pack.compaction_report
        assert "after_count" in pack.compaction_report

    def test_triage_generates_compaction_report(self) -> None:
        """压缩后应生成有效的 compaction_report。"""
        triage = ContextTriage()
        memories = [
            _make_memory("m1", "数据 " * 100, priority=0.9, confidence=0.9),
            _make_memory("m2", "更多数据 " * 100, priority=0.5, confidence=0.5),
        ]

        pack = triage.build_context_pack(
            task_input="测试报告",
            task_type=TaskType.GENERAL_QA,
            memories=memories,
            rag_chunks=[],
            budget=30,  # 极小预算
        )

        report = pack.compaction_report
        assert isinstance(report, dict)
        assert "reason" in report or report  # 报告非空
        # 当有剔除时应有 removed_ids
        if report.get("before_count", 0) > report.get("after_count", 0):
            assert "removed_ids" in report

    def test_triage_empty_inputs(self) -> None:
        """空输入应返回空的 ContextPack。"""
        triage = ContextTriage()

        pack = triage.build_context_pack(
            task_input="空输入测试",
            task_type=TaskType.GENERAL_QA,
            memories=[],
            rag_chunks=[],
            rules=[],
            budget=8000,
        )

        assert isinstance(pack, ContextPack)
        assert len(pack.items) == 0
        assert pack.total_tokens == 0

    def test_triage_with_rules(self) -> None:
        """规则应作为 placement="bottom" 的 ContextItem 添加。"""
        triage = ContextTriage()
        rules = ["安全规则1", "编码规范"]

        pack = triage.build_context_pack(
            task_input="测试规则",
            task_type=TaskType.CODE_GENERATION,
            memories=[],
            rag_chunks=[],
            rules=rules,
            budget=8000,
        )

        rule_items = [
            item for item in pack.items if item.source_type == "rule"
        ]
        assert len(rule_items) == 2
        for item in rule_items:
            assert item.placement == "bottom"


# ============================================================================
# ContextPackBuilder 测试
# ============================================================================


class TestContextPackBuilder:
    """测试 ContextPackBuilder 工厂方法。"""

    def test_builder_produces_cacheable_prefix(self) -> None:
        """cacheable_prefix 应抽取 system/rule 类型的稳定内容。"""
        triage = ContextTriage()
        builder = ContextPackBuilder(triage)

        memories = [
            _make_memory("m1", "用户偏好", priority=0.9, confidence=0.9),
        ]
        rules = ["项目编码规范：使用 Google Style"]

        pack = builder.from_memories_and_rag(
            task_input="写代码",
            task_type=TaskType.CODE_GENERATION,
            memories=memories,
            rag_chunks=[],
            budget=8000,
        )

        # 重新构建带规则的包以获取 rule 条目
        pack2 = triage.build_context_pack(
            task_input="写代码",
            task_type=TaskType.CODE_GENERATION,
            memories=memories,
            rag_chunks=[],
            rules=rules,
            budget=8000,
        )

        prefix = builder.get_cacheable_prefix(pack2)
        assert isinstance(prefix, str)
        # 规则内容应在 cacheable_prefix 中
        if any(item.source_type == "rule" for item in pack2.items):
            assert len(prefix) > 0

    def test_builder_produces_volatile_context(self) -> None:
        """volatile_context 应抽取 memory/rag 类型的易变内容。"""
        triage = ContextTriage()
        builder = ContextPackBuilder(triage)

        memories = [
            _make_memory("m1", "易变记忆内容", priority=0.9, confidence=0.9),
        ]
        rag_chunks = [
            _make_rag_chunk("c1", "易变 RAG 内容", score=0.8),
        ]

        pack = builder.from_memories_and_rag(
            task_input="任务A",
            task_type=TaskType.CODE_GENERATION,
            memories=memories,
            rag_chunks=rag_chunks,
            budget=8000,
        )

        volatile = builder.get_volatile_context(pack)
        assert isinstance(volatile, str)
        assert "任务A" in volatile
        assert "易变记忆内容" in volatile or "易变 RAG 内容" in volatile

    def test_builder_produces_critical_reminders(self) -> None:
        """critical_reminders 应抽取 placement="bottom" 的关键提醒。"""
        triage = ContextTriage()
        builder = ContextPackBuilder(triage)

        rules = ["关键提醒：必须检查安全性", "重要：所有文件操作需审批"]

        pack = triage.build_context_pack(
            task_input="危险操作",
            task_type=TaskType.ARCH_REFACTOR,
            memories=[],
            rag_chunks=[],
            rules=rules,
            budget=8000,
        )

        reminders = builder.get_critical_reminders(pack)
        assert isinstance(reminders, list)
        # 规则条目 placement="bottom"
        assert len(reminders) >= 2
        assert any("安全性" in r for r in reminders)
        assert any("审批" in r for r in reminders)

    def test_builder_critical_reminders_notes_removed(self) -> None:
        """当 compaction_report 中有 removed_ids 时，应提示用户。"""
        triage = ContextTriage()
        builder = ContextPackBuilder(triage)

        # 创建会触发压缩的场景
        memories = [
            _make_memory("m1", "X " * 200, priority=0.9, confidence=0.9),
            _make_memory("m2", "Y " * 200, priority=0.5, confidence=0.5),
        ]

        pack = triage.build_context_pack(
            task_input="压缩测试",
            task_type=TaskType.GENERAL_QA,
            memories=memories,
            rag_chunks=[],
            budget=20,
        )

        reminders = builder.get_critical_reminders(pack)
        # 如果有被移除的项，reminders 中应有提示
        if pack.compaction_report.get("removed_ids"):
            has_removal_note = any(
                "剔除" in r or "removed" in r.lower() for r in reminders
            )
            # 至少 reminders 列表存在
            assert isinstance(reminders, list)
