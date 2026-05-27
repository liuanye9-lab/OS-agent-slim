"""测试 LLM 客户端抽象层模块。

覆盖 MockLLMClient、OpenAICompatibleClient 和 BaseLLMClient 的核心功能。
"""

from __future__ import annotations

import pytest

from stable_agent.llm_client import (
    BaseLLMClient,
    MockLLMClient,
    OpenAICompatibleClient,
)


class TestMockLLMClient:
    """MockLLMClient 测试。"""

    @pytest.fixture
    def client(self) -> MockLLMClient:
        """创建 MockLLMClient 实例。"""
        return MockLLMClient()

    def test_mock_complete_returns_structure(self, client: MockLLMClient) -> None:
        """验证返回的 dict 包含所有必要字段。"""
        result = client.complete("测试 prompt")
        assert isinstance(result, dict)
        assert "text" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "model_name" in result
        assert "latency_ms" in result
        assert result["model_name"] == "mock-v1"
        assert isinstance(result["text"], str)
        assert isinstance(result["input_tokens"], int)
        assert isinstance(result["output_tokens"], int)

    def test_mock_complete_bug_fix_response(self, client: MockLLMClient) -> None:
        """验证包含'修复'的 prompt 返回 bug 修复相关的回复。"""
        result = client.complete("请修复登录页面的样式问题")
        assert "定位" in result["text"] or "修复" in result["text"] or "CSS" in result["text"]

    def test_mock_complete_refactor_response(self, client: MockLLMClient) -> None:
        """验证包含'重构'的 prompt 返回重构建议。"""
        result = client.complete("请重构用户模块")
        assert "重构" in result["text"] or "AuthService" in result["text"]

    def test_mock_complete_optimize_response(self, client: MockLLMClient) -> None:
        """验证包含'优化'的 prompt 返回优化方案。"""
        result = client.complete("请优化首页加载速度")
        assert "优化" in result["text"] or "React.memo" in result["text"]

    def test_mock_complete_default_response(self, client: MockLLMClient) -> None:
        """验证不匹配任何关键词的 prompt 返回默认回复。"""
        result = client.complete("今天天气怎么样")
        assert "任务处理" in result["text"] or "需求" in result["text"]

    def test_mock_estimate_tokens(self, client: MockLLMClient) -> None:
        """验证 token 估算返回正整数。"""
        tokens = client.estimate_tokens("Hello, world!")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_mock_estimate_tokens_empty(self, client: MockLLMClient) -> None:
        """验证空文本返回 0 token。"""
        tokens = client.estimate_tokens("")
        assert tokens == 0

    def test_mock_complete_with_system_prompt(self, client: MockLLMClient) -> None:
        """验证带 system_prompt 的调用正常工作。"""
        result = client.complete("测试", system_prompt="你是一个助手")
        assert "text" in result
        assert result["input_tokens"] > 0


class TestOpenAICompatibleClient:
    """OpenAICompatibleClient 测试。"""

    def test_openai_client_fallback_when_no_key(self) -> None:
        """验证无 API key 时自动使用 mock 回退。"""
        client = OpenAICompatibleClient(api_key="")
        assert client.is_mock is True
        result = client.complete("修复 bug")
        assert result["model_name"] == "mock-v1"

    def test_openai_client_with_key_creates_client(self) -> None:
        """验证有 API key 时创建真实客户端（非 mock 模式）。"""
        client = OpenAICompatibleClient(api_key="sk-test-key")
        assert client.is_mock is False
        assert client.api_key == "sk-test-key"
        assert client.model == "gpt-4o"

    def test_openai_client_custom_model(self) -> None:
        """验证自定义 model 参数生效。"""
        client = OpenAICompatibleClient(
            api_key="sk-key",
            model="gpt-4o-mini",
            base_url="https://custom.api.com/v1",
        )
        assert client.model == "gpt-4o-mini"
        assert client.base_url == "https://custom.api.com/v1"

    def test_openai_client_estimate_tokens(self) -> None:
        """验证 token 估算委托给 TokenMeter。"""
        client = OpenAICompatibleClient(api_key="")
        tokens = client.estimate_tokens("Hello")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_openai_client_complete_fallback_on_no_key(self) -> None:
        """验证无 key 的 complete 调用正常返回结构。"""
        client = OpenAICompatibleClient(api_key="")
        result = client.complete("优化性能")
        assert "text" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "model_name" in result
        assert "latency_ms" in result


class TestBaseLLMClient:
    """BaseLLMClient 抽象基类测试。"""

    def test_base_abstract_cannot_instantiate(self) -> None:
        """验证不能直接实例化抽象基类。"""
        with pytest.raises(TypeError):
            BaseLLMClient()  # type: ignore[abstract]

    def test_base_abstract_cannot_instantiate_direct(self) -> None:
        """验证缺少 complete 方法的子类也不能实例化。"""
        class IncompleteClient(BaseLLMClient):
            def estimate_tokens(self, text: str) -> int:
                return len(text)

        with pytest.raises(TypeError):
            IncompleteClient()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        """验证正确实现的子类可以实例化并使用。"""
        class FullClient(BaseLLMClient):
            def complete(self, prompt, system_prompt="", max_tokens=4096,
                         temperature=0.7, **kwargs):
                return {
                    "text": prompt,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "model_name": "test",
                    "latency_ms": 1,
                }

            def estimate_tokens(self, text: str) -> int:
                return len(text)

        client = FullClient()
        result = client.complete("hello")
        assert result["text"] == "hello"
        assert result["model_name"] == "test"
