"""测试 plain_language 模块：PlainLanguageExplainer。"""

from __future__ import annotations

import pytest

from stable_agent.plain_language import PlainLanguageExplainer


# ============================================================================
# PlainLanguageExplainer 测试
# ============================================================================


class TestPlainLanguageExplainer:
    """测试 PlainLanguageExplainer 大白话翻译功能。"""

    @pytest.fixture
    def explainer(self) -> PlainLanguageExplainer:
        """创建 PlainLanguageExplainer 实例。"""
        return PlainLanguageExplainer()

    def test_explain_known_event(self, explainer: PlainLanguageExplainer) -> None:
        """已知事件应返回对应的大白话解释。"""
        result = explainer.explain("workflow:started")
        assert "接到任务" in result or "思考" in result or "🧠" in result

    def test_explain_unknown_event_returns_default(self, explainer: PlainLanguageExplainer) -> None:
        """未知事件应返回默认解释。"""
        result = explainer.explain("unknown:event:xyz")
        assert result == explainer.DEFAULT_EXPLANATION

    def test_explain_with_context_memory_count(self, explainer: PlainLanguageExplainer) -> None:
        """带 memory_count 的上下文应增强解释。"""
        result = explainer.explain_with_context(
            "memory:retrieved",
            {"memory_count": 5},
        )
        assert "5" in result
        assert "记忆" in result or "memory" in result.lower()

    def test_explain_with_context_budget(self, explainer: PlainLanguageExplainer) -> None:
        """带 total 的上下文应包含 token 预算信息。"""
        result = explainer.explain_with_context(
            "budget:allocated",
            {"total": 8000},
        )
        assert "8000" in result
        assert "token" in result

    def test_explain_with_context_score(self, explainer: PlainLanguageExplainer) -> None:
        """带 score 的上下文应包含评分信息。"""
        result = explainer.explain_with_context(
            "eval:score",
            {"score": 0.95, "overall_score": 0.92},
        )
        assert "0.95" in result or "0.92" in result

    def test_all_known_events_have_explanation(self, explainer: PlainLanguageExplainer) -> None:
        """所有已知事件应有非空解释。"""
        for event_type, explanation in explainer.EXPLANATIONS.items():
            assert isinstance(explanation, str), (
                f"事件 '{event_type}' 的解释不是字符串"
            )
            assert len(explanation) > 0, (
                f"事件 '{event_type}' 的解释为空"
            )

    def test_default_explanation_not_empty(self, explainer: PlainLanguageExplainer) -> None:
        """默认解释不应为空。"""
        assert len(explainer.DEFAULT_EXPLANATION) > 0

    def test_explain_all_events_no_exception(self, explainer: PlainLanguageExplainer) -> None:
        """对所有已知事件调用 explain 不应抛异常。"""
        for event_type in explainer.EXPLANATIONS:
            try:
                result = explainer.explain(event_type)
                assert isinstance(result, str)
            except Exception as e:
                pytest.fail(f"事件 '{event_type}' 触发异常: {e}")

    def test_explain_with_context_tool_call(self, explainer: PlainLanguageExplainer) -> None:
        """带 tool_name 的上下文应增强工具名称信息。"""
        result = explainer.explain_with_context(
            "tool:called",
            {"tool_name": "read_file"},
        )
        assert "read_file" in result

    def test_explain_with_context_approval_action(self, explainer: PlainLanguageExplainer) -> None:
        """带 action 的审批事件应增强操作信息。"""
        result = explainer.explain_with_context(
            "approval:required",
            {"action": "删除文件 /etc/config"},
        )
        assert "删除文件" in result

    def test_explain_with_context_error_detail(self, explainer: PlainLanguageExplainer) -> None:
        """失败事件应包含错误详情。"""
        result = explainer.explain_with_context(
            "workflow:failed",
            {"error": "MemoryError: 内存不足"},
        )
        assert "MemoryError" in result or "内存不足" in result

    def test_explain_with_context_no_payload(self, explainer: PlainLanguageExplainer) -> None:
        """空 payload 应返回基础解释。"""
        result = explainer.explain_with_context("workflow:started", {})
        assert len(result) > 0
        # 应该等于基础解释
        assert result == explainer.explain("workflow:started")
