"""LLM 客户端工厂 — 统一创建和管理 LLM 客户端实例。

读取环境变量 OPENAI_API_KEY 决定使用真实 API 还是 Mock 回退。
所有模块通过 get_llm_client() 获取统一实例。

用法:
    from stable_agent.llm_factory import get_llm_client
    client = get_llm_client()
    result = client.complete("你好", system_prompt="你是一个助手")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from stable_agent.llm_client import (
    BaseLLMClient,
    MockLLMClient,
    OpenAICompatibleClient,
)

logger = logging.getLogger(__name__)

_global_client: Optional[BaseLLMClient] = None


def get_llm_client(
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> BaseLLMClient:
    """获取全局 LLM 客户端实例（单例）。

    优先级:
    1. 已创建的全局实例（缓存）
    2. OPENAI_API_KEY 环境变量
    3. STABLE_AGENT_LLM_KEY 环境变量
    4. 所有都为空 → MockLLMClient（演示模式）

    Args:
        api_key: API 密钥，空则从环境变量读取。
        base_url: API 基础 URL，空则用 OpenAI 默认。
        model: 模型名称，空则用 gpt-4o。

    Returns:
        BaseLLMClient 实例（OpenAICompatibleClient 或 MockLLMClient）。
    """
    global _global_client

    if _global_client is not None:
        return _global_client

    # 尝试多个环境变量
    key = api_key or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("STABLE_AGENT_LLM_KEY", "")
    url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = model or os.environ.get("STABLE_AGENT_LLM_MODEL", "gpt-4o")

    if key:
        logger.info("使用 OpenAI 兼容 API: model=%s, base_url=%s", model_name, url)
        _global_client = OpenAICompatibleClient(
            api_key=key,
            base_url=url,
            model=model_name,
        )
    else:
        logger.info("未配置 API Key，使用 MockLLMClient（演示模式）")
        _global_client = MockLLMClient()

    return _global_client


def set_llm_client(client: BaseLLMClient) -> None:
    """手动设置全局 LLM 客户端（用于测试和自定义注入）。

    Args:
        client: BaseLLMClient 实例。
    """
    global _global_client
    _global_client = client


def reset_llm_client() -> None:
    """重置全局 LLM 客户端（用于测试清理）。"""
    global _global_client
    _global_client = None
