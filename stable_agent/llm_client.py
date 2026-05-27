"""StableAgent OS LLM 客户端抽象层模块。

提供统一的 LLM 调用接口，支持：
- BaseLLMClient: 抽象基类，定义 complete() 和 estimate_tokens() 契约。
- MockLLMClient: 模拟客户端，根据 prompt 关键词生成确定性模拟回复。
- OpenAICompatibleClient: OpenAI API 兼容客户端，无 API key 时自动回退到 MockLLMClient。

约定：
- complete() 始终返回固定结构的 dict，不会抛出异常。
- 回退机制确保系统在任何情况下都不会因 API 不可用而崩溃。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from stable_agent.token_meter import TokenMeter


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类。

    定义了所有 LLM 客户端必须实现的契约方法。
    子类必须实现 complete() 和 estimate_tokens()。
    """

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """执行一次 LLM 补全调用。

        Args:
            prompt: 用户提示文本。
            system_prompt: 系统提示文本，默认为空。
            max_tokens: 最大输出 token 数，默认 4096。
            temperature: 采样温度，默认 0.7。
            **kwargs: 额外的模型参数。

        Returns:
            包含以下固定字段的字典：
            - text (str): 模型输出的文本内容。
            - input_tokens (int): 输入 token 数。
            - output_tokens (int): 输出 token 数。
            - model_name (str): 模型名称。
            - latency_ms (int): 调用延迟（毫秒）。
        """
        ...

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数。

        Args:
            text: 输入文本。

        Returns:
            预估的 token 数量。
        """
        ...


class MockLLMClient(BaseLLMClient):
    """模拟 LLM 客户端。

    用于测试和演示场景，根据 prompt 中的关键词生成预定义的模拟回复。
    使用 time.sleep(0.01) 模拟 API 调用延迟。

    Attributes:
        token_meter: TokenMeter 实例，用于 token 估算。
    """

    def __init__(self, token_meter: Optional[TokenMeter] = None) -> None:
        """初始化模拟客户端。

        Args:
            token_meter: TokenMeter 实例，None 时创建默认实例。
        """
        self.token_meter = token_meter if token_meter is not None else TokenMeter()

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """根据 prompt 中关键词生成模拟回复。

        回复策略：
        - 包含"修复"/"bug"/"fix" → 生成 bug 修复回复。
        - 包含"重构"/"refactor" → 生成重构建议回复。
        - 包含"优化"/"optimize" → 生成性能优化回复。
        - 默认 → 通用任务完成回复。

        Args:
            prompt: 用户提示文本。
            system_prompt: 系统提示文本（模拟中忽略但计入 token）。
            max_tokens: 最大输出 token 数。
            temperature: 采样温度（模拟中忽略）。
            **kwargs: 额外参数（模拟中忽略）。

        Returns:
            包含 text, input_tokens, output_tokens, model_name, latency_ms 的字典。
        """
        # 模拟 API 调用延迟
        time.sleep(0.01)

        # 根据关键词选择回复内容
        prompt_lower = prompt.lower()

        if any(kw in prompt_lower for kw in ("修复", "bug", "fix", "修復", "缺陷")):
            response = (
                "已定位到问题：CSS flexbox 属性缺失，在 styles.css:42 添加 "
                "`display: flex; justify-content: center;` 即可解决。"
                "根本原因是父容器未设置弹性布局导致子元素无法居中。"
            )
        elif any(kw in prompt_lower for kw in ("重构", "refactor", "重構")):
            response = (
                "建议重构方案：\n"
                "1. 提取 AuthService 统一管理认证逻辑\n"
                "2. 引入 JWT 中间件替代手动 token 验证\n"
                "3. 分离 UserRepository 层，遵循依赖倒置原则\n"
                "4. 将硬编码配置迁移到环境变量"
            )
        elif any(kw in prompt_lower for kw in ("优化", "optimize", "性能")):
            response = (
                "优化方案：\n"
                "1. 使用 React.memo 减少不必要的重渲染\n"
                "2. 引入虚拟列表处理大数据量展示\n"
                "3. 对 API 响应启用 HTTP 缓存头\n"
                "4. 使用 Web Worker 处理 CPU 密集型计算"
            )
        else:
            response = "根据您的需求，我已完成任务处理。如有任何问题，请随时提出。"

        # 限制响应长度在 max_tokens 范围内（粗略估算：中文约 1.5 字符/token）
        max_chars = max_tokens * 1.5
        if len(response) > max_chars:
            response = response[: int(max_chars)] + "..."

        # 计算 token 数
        combined_input = system_prompt + "\n" + prompt if system_prompt else prompt
        input_tokens = self.token_meter.estimate_tokens(combined_input)
        output_tokens = self.token_meter.estimate_tokens(response)

        return {
            "text": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model_name": "mock-v1",
            "latency_ms": 10,  # 模拟 10ms 延迟
        }

    def estimate_tokens(self, text: str) -> int:
        """委托给 TokenMeter 进行 token 估算。

        Args:
            text: 输入文本。

        Returns:
            预估 token 数。
        """
        return self.token_meter.estimate_tokens(text)


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI API 兼容客户端。

    支持 OpenAI 及兼容 API（如 Azure OpenAI、本地模型）。
    当 api_key 为空时，自动回退到 MockLLMClient，确保系统不会因
    缺少 API key 而崩溃。

    Attributes:
        api_key: OpenAI API 密钥。
        base_url: API 基础 URL。
        model: 模型名称。
        token_meter: TokenMeter 实例。
        _mock_fallback: 回退用的 MockLLMClient 实例。
        _is_mock: 是否处于 mock 回退模式。
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        token_meter: Optional[TokenMeter] = None,
    ) -> None:
        """初始化 OpenAI 兼容客户端。

        Args:
            api_key: OpenAI API 密钥，空字符串表示使用 mock 回退。
            base_url: API 基础 URL，默认 OpenAI 官方地址。
            model: 模型名称，默认 gpt-4o。
            token_meter: TokenMeter 实例，None 时创建默认实例。
        """
        self.api_key: str = api_key
        self.base_url: str = base_url
        self.model: str = model
        self.token_meter: TokenMeter = (
            token_meter if token_meter is not None else TokenMeter()
        )

        # 无 API key 时使用 mock 回退
        self._is_mock: bool = not bool(api_key)
        self._mock_fallback: MockLLMClient = MockLLMClient(self.token_meter)

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """执行 LLM 补全调用。

        有 API key 时调用真实 API，否则回退到 MockLLMClient。

        Args:
            prompt: 用户提示文本。
            system_prompt: 系统提示文本。
            max_tokens: 最大输出 token 数。
            temperature: 采样温度。
            **kwargs: 额外参数。

        Returns:
            包含 text, input_tokens, output_tokens, model_name, latency_ms 的字典。
        """
        if self._is_mock:
            return self._mock_fallback.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

        # 真实 API 调用
        try:
            return self._call_api(prompt, system_prompt, max_tokens, temperature, **kwargs)
        except Exception:
            # API 调用失败时优雅降级到 mock
            return self._mock_fallback.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

    def _call_api(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs,
    ) -> dict:
        """调用 OpenAI Chat Completions API。

        Args:
            prompt: 用户提示文本。
            system_prompt: 系统提示文本。
            max_tokens: 最大输出 token 数。
            temperature: 采样温度。
            **kwargs: 额外的模型参数（如 top_p、stop 等）。

        Returns:
            标准化的响应字典。
        """
        import json
        from urllib.request import Request, urlopen
        from urllib.error import URLError

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 构建请求体
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # 合并额外参数
        body.update(kwargs)

        # 发送请求
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        req = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        start_time = time.time()
        with urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        latency_ms = int((time.time() - start_time) * 1000)

        # 解析响应
        choice = raw["choices"][0]
        text = choice["message"]["content"]
        input_tokens = raw.get("usage", {}).get("prompt_tokens", 0)
        output_tokens = raw.get("usage", {}).get("completion_tokens", 0)

        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model_name": self.model,
            "latency_ms": latency_ms,
        }

    def estimate_tokens(self, text: str) -> int:
        """委托给 TokenMeter 进行 token 估算。

        Args:
            text: 输入文本。

        Returns:
            预估 token 数。
        """
        return self.token_meter.estimate_tokens(text)

    @property
    def is_mock(self) -> bool:
        """是否处于 mock 回退模式。

        Returns:
            True 表示使用 MockLLMClient 回退。
        """
        return self._is_mock
