"""test_context_compression_guard — 测试 ContextCompressionGuard。"""
import pytest
from stable_agent.context.context_compression_guard import (
    CompressionDecision,
    ContextCompressionGuard,
)


class TestContextCompressionGuard:
    """ContextCompressionGuard 核心测试。"""

    def setup_method(self):
        self.guard = ContextCompressionGuard()

    def test_protects_user_goal(self):
        """应保护 user_goal 类型的条目。"""
        items = [
            {"type": "user_goal", "content": "修复登录页面崩溃"},
            {"type": "other", "content": "无关信息"},
        ]
        decision = self.guard.protect(
            task_input="修复登录页面崩溃",
            context_items=items,
            token_budget=100,
        )
        protected_types = [i.get("type") for i in decision.protected_items]
        assert "user_goal" in protected_types

    def test_protects_project_constraint(self):
        """应保护 project_constraint 类型的条目。"""
        items = [
            {"type": "project_constraint", "content": "使用 React 18"},
            {"type": "other", "content": "杂项"},
        ]
        decision = self.guard.protect(
            task_input="重构组件",
            context_items=items,
            token_budget=100,
        )
        protected_types = [i.get("type") for i in decision.protected_items]
        assert "project_constraint" in protected_types

    def test_protects_high_confidence_memory(self):
        """应保护 confidence >= 0.8 的记忆。"""
        items = [
            {"type": "memory", "content": "重要经验", "confidence": 0.9},
            {"type": "memory", "content": "低置信经验", "confidence": 0.3},
        ]
        decision = self.guard.protect(
            task_input="测试任务",
            context_items=items,
            token_budget=100,
        )
        assert len(decision.protected_items) == 1
        assert decision.protected_items[0]["confidence"] == 0.9

    def test_does_not_drop_user_goal(self):
        """user_goal 不应出现在 dropped_items 中。"""
        items = [
            {"type": "user_goal", "content": "核心目标"},
            {"type": "other", "content": "可丢弃"},
        ]
        decision = self.guard.protect(
            task_input="核心目标",
            context_items=items,
            token_budget=100,
        )
        dropped_types = [i.get("type") for i in decision.dropped_items]
        assert "user_goal" not in dropped_types

    def test_risk_flags_when_all_dropped(self):
        """当所有条目都被丢弃时应有 risk_flags。"""
        items = [
            {"type": "other", "content": "杂项1"},
            {"type": "other", "content": "杂项2"},
        ]
        decision = self.guard.protect(
            task_input="测试",
            context_items=items,
            token_budget=100,
        )
        assert len(decision.risk_flags) > 0

    def test_summary_zh_generated(self):
        """每次压缩应有 summary_zh。"""
        items = [
            {"type": "user_goal", "content": "修复Bug"},
            {"type": "project_constraint", "content": "使用Python"},
            {"type": "other", "content": "杂项"},
        ]
        decision = self.guard.protect(
            task_input="修复Bug",
            context_items=items,
            token_budget=500,
        )
        assert decision.summary_zh
        assert "保留" in decision.summary_zh

    def test_last_decision_stored(self):
        """应保存 last_decision。"""
        items = [{"type": "user_goal", "content": "目标"}]
        self.guard.protect(
            task_input="目标",
            context_items=items,
            token_budget=100,
        )
        assert self.guard.get_last_decision() is not None

    def test_get_protection_summary_no_decision(self):
        """无决策时应返回占位文本。"""
        summary = self.guard.get_protection_summary_zh()
        assert "尚未执行" in summary

    def test_validated_skill_rule_protected(self):
        """已验证的 skill rule 应被保护。"""
        items = [
            {"type": "skill_rule", "content": "规则1", "validated": True},
            {"type": "skill_rule", "content": "规则2", "validated": False},
        ]
        decision = self.guard.protect(
            task_input="测试",
            context_items=items,
            token_budget=100,
        )
        assert len(decision.protected_items) == 1
        assert decision.protected_items[0]["validated"] is True

    def test_no_items_empty_decision(self):
        """空列表应返回空决策。"""
        decision = self.guard.protect(
            task_input="空任务",
            context_items=[],
            token_budget=100,
        )
        assert len(decision.kept_items) == 0
        assert len(decision.dropped_items) == 0
