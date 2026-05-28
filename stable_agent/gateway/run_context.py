"""RunContext — 统一工具调用上下文。

每次 MCP tools/call 创建一个 RunContext 实例，用于追踪一次工具调用的
完整生命周期。支持嵌套 span 形成调用树。

用法::

    ctx = RunContext()
    child = ctx.child_span()  # 创建子 span，继承 run_id + trace_id
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class RunContext:
    """统一工具调用上下文。

    每次 MCP tools/call 创建一个实例。支持通过 child_span() 创建
    嵌套子 span，子 span 继承父级的 run_id 和 trace_id。

    Attributes:
        run_id: 运行唯一标识，同一 run 内所有 span 共享。
        tool_call_id: 工具调用唯一标识。
        trace_id: 追踪链 ID，跨服务传递。
        span_id: 当前 span 唯一标识。
        parent_span_id: 父 span ID，None 表示根 span。
        started_at: 开始时间戳（time.time() 格式）。
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: str | None = None
    started_at: float = field(default_factory=time.time)

    def child_span(self) -> RunContext:
        """创建子 span。

        子 span 继承当前实例的 run_id、tool_call_id 和 trace_id，
        但拥有新的 span_id，parent_span_id 设置为当前实例的 span_id。

        Returns:
            新的 RunContext 实例，作为当前 span 的子 span。
        """
        return RunContext(
            run_id=self.run_id,
            tool_call_id=self.tool_call_id,
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
        )
