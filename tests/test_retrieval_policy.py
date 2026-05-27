"""测试 retrieval_policy 模块：RetrievalPolicy 和 RetrievalCritic。"""

from __future__ import annotations

import pytest

from stable_agent.models import TaskType
from stable_agent.retrieval_policy import RetrievalCritic, RetrievalPolicy


# ============================================================================
# RetrievalPolicy — should_retrieve 测试
# ============================================================================


class TestRetrievalPolicyShouldRetrieve:
    """测试 should_retrieve 决策逻辑。"""

    @pytest.fixture
    def policy(self) -> RetrievalPolicy:
        """创建 RetrievalPolicy 实例。"""
        return RetrievalPolicy()

    def test_should_retrieve_arch_refactor(self, policy: RetrievalPolicy) -> None:
        """ARCH_REFACTOR 任务基本都需要检索。"""
        result = policy.should_retrieve(
            TaskType.ARCH_REFACTOR,
            "重构用户认证模块的架构设计"
        )
        assert result is True

    def test_should_retrieve_code_generation(self, policy: RetrievalPolicy) -> None:
        """CODE_GENERATION 任务基本都需要检索。"""
        result = policy.should_retrieve(
            TaskType.CODE_GENERATION,
            "生成一个用户登录的 API 接口"
        )
        assert result is True

    def test_should_retrieve_bug_fix(self, policy: RetrievalPolicy) -> None:
        """BUG_FIX 任务基本都需要检索。"""
        result = policy.should_retrieve(
            TaskType.BUG_FIX,
            "修复登录页面 500 错误的 bug"
        )
        assert result is True

    def test_skip_retrieval_short_input(self, policy: RetrievalPolicy) -> None:
        """输入太短（< 10 字符）应跳过检索。"""
        result = policy.should_retrieve(TaskType.CODE_GENERATION, "hi")
        assert result is False

    def test_skip_retrieval_greeting(self, policy: RetrievalPolicy) -> None:
        """纯问候应跳过检索。"""
        result = policy.skip_retrieval(TaskType.GENERAL_QA, "你好")
        assert result is True

    def test_skip_retrieval_simple_confirm(self, policy: RetrievalPolicy) -> None:
        """简单确认（OK）应跳过检索。"""
        result = policy.skip_retrieval(TaskType.GENERAL_QA, "好的")
        assert result is True

    def test_general_qa_without_knowledge_keywords(self, policy: RetrievalPolicy) -> None:
        """GENERAL_QA 且无知识关键词应跳过检索。"""
        result = policy.should_retrieve(
            TaskType.GENERAL_QA,
            "今天天气怎么样？"
        )
        assert result is False

    def test_general_qa_with_knowledge_keywords(self, policy: RetrievalPolicy) -> None:
        """GENERAL_QA 但有知识关键词（如"文档"）应触发检索。"""
        result = policy.should_retrieve(
            TaskType.GENERAL_QA,
            "请查看项目文档中的 API 规范说明"
        )
        assert result is True

    def test_ui_design_with_style_keywords(self, policy: RetrievalPolicy) -> None:
        """UI_DESIGN 有样式关键词时应检索。"""
        result = policy.should_retrieve(
            TaskType.UI_DESIGN,
            "设计一个蓝色的按钮组件"
        )
        assert result is True

    def test_ui_design_without_style_keywords(self, policy: RetrievalPolicy) -> None:
        """UI_DESIGN 无样式关键词时应跳过。"""
        result = policy.should_retrieve(
            TaskType.UI_DESIGN,
            "做个界面"
        )
        assert result is False

    def test_skip_retrieval_single_word(self, policy: RetrievalPolicy) -> None:
        """单单词输入应跳过检索。"""
        result = policy.skip_retrieval(TaskType.GENERAL_QA, "test")
        assert result is True

    def test_skip_retrieval_empty_input(self, policy: RetrievalPolicy) -> None:
        """空输入应跳过检索。"""
        result = policy.skip_retrieval(TaskType.GENERAL_QA, "")
        assert result is True


# ============================================================================
# RetrievalCritic 测试
# ============================================================================


class TestRetrievalCritic:
    """测试 RetrievalCritic 二次筛选功能。"""

    @pytest.fixture
    def critic(self) -> RetrievalCritic:
        """创建 RetrievalCritic 实例。"""
        return RetrievalCritic()

    def test_critique_scores_and_ranks(self, critic: RetrievalCritic) -> None:
        """critique 应正确评分并排序。"""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Python 异步编程完整指南 async await 最佳实践",
                "source_path": "docs/async.md",
                "score": 0.9,
            },
            {
                "chunk_id": "c2",
                "content": "Python 基础语法介绍",
                "source_path": "docs/basics.md",
                "score": 0.6,
            },
            {
                "chunk_id": "c3",
                "content": "JavaScript 异步编程 Promise then catch",
                "source_path": "docs/js.md",
                "score": 0.3,
            },
        ]

        result = critic.critique(
            task_input="Python 异步编程 async await",
            retrieved_chunks=chunks,
            max_chunks=3,
        )

        assert len(result) == 3
        # 高分应排在前面
        assert result[0]["chunk_id"] == "c1"

    def test_critique_limits_max_chunks(self, critic: RetrievalCritic) -> None:
        """critique 应限制返回数量不超过 max_chunks。"""
        chunks = [
            {"chunk_id": f"c{i}", "content": f"文档 {i} Python 编程", "score": 0.9 - i * 0.1}
            for i in range(1, 11)
        ]

        result = critic.critique(
            task_input="Python 编程",
            retrieved_chunks=chunks,
            max_chunks=5,
        )

        assert len(result) <= 5

    def test_critique_detects_uncertainty_risk(self, critic: RetrievalCritic) -> None:
        """包含不确定词的 chunk 应标注 risk="uncertain"。"""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "这个方法可能有效，但也许需要更多测试验证",
                "source_path": "docs/uncertain.md",
                "score": 0.9,
            },
            {
                "chunk_id": "c2",
                "content": "这是一个确定的结论，经过充分验证",
                "source_path": "docs/certain.md",
                "score": 0.85,
            },
        ]

        result = critic.critique(
            task_input="方法验证",
            retrieved_chunks=chunks,
            max_chunks=2,
        )

        # 不确定词的 chunk 应有 risk="uncertain"
        uncertain_chunks = [
            c for c in result if c.get("risk") == "uncertain"
        ]
        assert len(uncertain_chunks) >= 1
        # 不确定词文档的排名应被惩罚（排在后面）
        if len(uncertain_chunks) > 0:
            # 不确定的 chunk 应在结果中
            assert uncertain_chunks[0]["chunk_id"] == "c1"

    def test_critique_empty_input(self, critic: RetrievalCritic) -> None:
        """空输入应返回空列表。"""
        result = critic.critique(
            task_input="测试",
            retrieved_chunks=[],
        )
        assert result == []

    def test_critique_adds_why_relevant(self, critic: RetrievalCritic) -> None:
        """critique 应为每个 chunk 添加 why_relevant 字段。"""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "React 组件开发指南，包含状态管理和生命周期",
                "source_path": "docs/react.md",
                "score": 0.8,
            },
        ]

        result = critic.critique(
            task_input="React 组件开发",
            retrieved_chunks=chunks,
        )

        assert len(result) == 1
        assert "why_relevant" in result[0]
        assert len(result[0]["why_relevant"]) > 0

    def test_critique_adds_token_estimate(self, critic: RetrievalCritic) -> None:
        """critique 应为每个 chunk 添加 token_estimate 字段。"""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "一些文档内容用于测试 token 估算",
                "source_path": "docs/test.md",
                "score": 0.8,
            },
        ]

        result = critic.critique(
            task_input="测试",
            retrieved_chunks=chunks,
        )

        assert len(result) == 1
        assert "token_estimate" in result[0]
        assert result[0]["token_estimate"] > 0

    def test_critique_penalizes_uncertain_chunks(self, critic: RetrievalCritic) -> None:
        """uncertain 风险的 chunk 排名应被降低。"""
        chunks = [
            {
                "chunk_id": "c_certain",
                "content": "经过验证的确定方案，效果显著",
                "source_path": "docs/certain.md",
                "score": 0.8,
            },
            {
                "chunk_id": "c_uncertain",
                "content": "这个方法可能有效，也许要考虑其他方案",
                "source_path": "docs/uncertain.md",
                "score": 0.9,
            },
        ]

        result = critic.critique(
            task_input="方案验证",
            retrieved_chunks=chunks,
            max_chunks=2,
        )

        # uncertain chunk (score 0.9) 乘以 (1-0.2) = 0.72
        # certain chunk (score 0.8) 乘以 1.0 = 0.8
        # certain 应排在 uncertain 前面
        assert result[0]["chunk_id"] == "c_certain"
