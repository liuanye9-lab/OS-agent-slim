"""RunContext — 统一工具调用上下文 (V6.5)。

每次 MCP tools/call 创建一个 RunContext 实例，用于追踪一次工具调用的
完整生命周期。支持嵌套 span 形成调用树。

V6.5 新增进度跟踪字段，所有 MCP 调用 / Dashboard / RunStore 共享同一个 run_id。

用法::

    ctx = RunContext.create(task_input="分析项目架构")
    child = ctx.child_span()  # 创建子 span，继承 run_id + trace_id
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunContext:
    """统一工具调用上下文 (V6.5)。

    每次 MCP tools/call 创建一个实例。支持通过 child_span() 创建
    嵌套子 span，子 span 继承父级的 run_id 和 trace_id。

    V6.5 新增:
        task_input, source, current_stage, progress_pct, dashboard_url,
        trace_url, avatar_state, avatar_scene, status_text_zh, status_text_en,
        metadata, created_at.
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: str | None = None
    started_at: float = field(default_factory=time.time)
    # V6.5 新增
    task_input: str | None = None
    source: str = "mcp"
    current_stage: str = "created"
    progress_pct: int = 0
    dashboard_url: str = ""
    trace_url: str = ""
    avatar_state: str = "listening"
    avatar_scene: str = "desk"
    status_text_zh: str = ""
    status_text_en: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        task_input: str | None = None,
        source: str = "mcp",
        run_id: str | None = None,
    ) -> RunContext:
        final_run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        tool_call_id = f"call_{uuid.uuid4().hex[:12]}"
        trace_id_val = f"trace_{uuid.uuid4().hex[:12]}"
        return cls(
            run_id=final_run_id,
            tool_call_id=tool_call_id,
            trace_id=trace_id_val,
            source=source,
            task_input=task_input,
            dashboard_url=f"/runs/{final_run_id}",
            trace_url=f"/runs/{final_run_id}",
        )

    def child_span(self) -> RunContext:
        return RunContext(
            run_id=self.run_id,
            tool_call_id=self.tool_call_id,
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
        )
