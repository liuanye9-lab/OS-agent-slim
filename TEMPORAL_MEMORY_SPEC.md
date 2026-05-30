# TEMPORAL_MEMORY_SPEC.md — 时间感知记忆路由规范

**版本**: V8.1 | **文件**: `stable_agent/memory/temporal_memory_router.py`, `temporal_memory_bridge.py`

---

## 概述

TemporalMemoryRouter 在上下文压缩前检索按时间戳相关的记忆，防止丢失关键历史约束。通过 TemporalMemoryBridge 连接旧 MemoryRouter → 新路由器。

## TemporalMemoryHit

```python
@dataclass
class TemporalMemoryHit:
    memory_id: str
    content: str
    created_at: float
    updated_at: float
    project_id: str | None       # 正式项目 ID，用于精确过滤
    valid_from: float | None     # 有效期起始
    valid_until: float | None    # 有效期截止
    confidence: float = 0.5
    relevance_score: float = 0.0
    recency_score: float = 0.0
    source: str = ""
    reason_zh: str = ""          # 召回原因（中文）
    tags: list[str]
    source_quality: float = 0.5
```

## 检索算法

```
final_score = relevance * 0.55 + recency * 0.20 + confidence * 0.20 + source_quality * 0.05
```

- relevance: 关键词匹配。task_input + intent_keywords 与 content/tags 命中比例
- recency: 时间衰减。24h 内优先，7 天后衰减至 0.3
- confidence: 记忆本身置信度
- source_quality: 来源质量（bad_case=0.8, skill_rule=0.9, memory_bank=0.6）

## TemporalMemoryBridge

连接三个数据源到 TemporalMemoryRouter：

| 来源 | source_quality | 转换函数 |
|------|---------------|---------|
| MemoryBank Items | 0.6 | `from_memory_item()` |
| BadCases | 0.8 | `from_bad_case()` |
| Skill Rules (validated) | 0.9 | `from_skill_rule()` |

## 主流程调用

```
Orchestrator.process_task step 6.5:
  bridge.load_for_project(project_id, existing_memories, bad_cases, skill_rules)
  hits = bridge.retrieve(task_input, project_id, top_k=8)
  ContextCompressionGuard.protect(context_items, temporal_memories=hits)
```

## 事件

发布 `temporal_memory.retrieved`:
```json
{
  "run_id": "<id>",
  "hit_count": 5,
  "hits": [{"memory_id": "...", "reason_zh": "关键词匹配，最近更新"}],
  "selected_memories": [...],
  "discarded_memories": [...],
  "time_window_days": 30
}
```
