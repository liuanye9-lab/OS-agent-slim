# CONTEXT_COMPRESSION_GUARD_SPEC.md — 上下文压缩保护守卫规范

**版本**: V8.1 | **文件**: `stable_agent/context/context_compression_guard.py`

---

## 概述

ContextCompressionGuard 在上下文压缩前标记受保护条目，确保核心目标、约束和关键记忆不被丢弃。

## CompressionDecision

```python
@dataclass
class CompressionDecision:
    kept_items: list[dict]           # 保留条目
    dropped_items: list[dict]        # 丢弃条目
    protected_items: list[dict]      # 受保护条目（强制保留）
    risk_flags: list[str]            # 风险标记
    summary_zh: str                  # 决策摘要
    token_budget: int = 0            # Token 预算
    estimated_tokens_before: int     # 压缩前 Token 估算
    estimated_tokens_after: int      # 压缩后 Token 估算
    compression_ratio: float         # 压缩比例
    blocked: bool = False            # 是否因超预算被阻止
```

## protect() — 6 层保护规则

按优先级排序：

| 优先级 | 规则 | 匹配条件 | 保护原因 |
|--------|------|---------|---------|
| 1 | 用户核心目标 | type="user_goal"/"task_input"/"current_intent" | 最高优先级，不可丢弃 |
| 2 | 项目约束 | type="project_constraint"/"project_rule"/"system_rule" | 避免违背项目规范 |
| 3 | 高置信度记忆 | type="memory" + confidence >= 0.8 | 稳定性保证 |
| 4 | 最近失败经验 | type="bad_case"/"failure" + 7天内 | 防止重复错误 |
| 5 | 已验证 Skill Rule | type="skill_rule"/"skill_patch" + validated=True | 保持已验证规则 |
| 6 | 时间记忆相关 | 内容与 TemporalMemoryHit 关键词交集 >= 2 | 关联历史上下文 |

## enforce_budget() — Token 预算强制

```
1. protected_items 全部保留，不可丢弃
2. 如果 protected_items 已超过 budget → blocked=True
3. 否则按优先级从低到高丢弃非保护条目：
   - type="secondary" 最先丢
   - 短内容 (len < 20) 优先丢
   - 无 confidence 的先丢
4. 生成 compression_ratio 统计
```

## 禁止行为

- ❌ 丢弃用户核心目标
- ❌ 让过期记忆覆盖新记忆
- ❌ 让失败经验直接进入长期记忆
- ❌ 压缩掉 high confidence temporal memory

## 事件

发布 `context.compression_guard.checked`:
```json
{
  "run_id": "<id>",
  "protected_count": 5,
  "dropped_count": 3,
  "kept_count": 8,
  "risk_flags": ["⚠️ 丢弃条目远多于保留条目"],
  "blocked": false,
  "summary_zh": "保留5条(受保护)+3条(普通)=8/8000 tokens | 风险: 无"
}
```

## Dashboard 展示

Dashboard 应展示：
- 保留了什么（kept_items）
- 丢弃了什么（dropped_items）
- 为什么丢弃（summary_zh）
- 是否存在压缩风险（risk_flags）
