# 01_CONTRACT_FREEZE.md

> 冻结时间: 2026-06-02T22:23:00+08:00
> 冻结目的: 保证重构过程中 stableagent.task.os_agent 外部契约不变

---

## 冻结范围

### stableagent.task.os_agent 外部输出契约

以下字段在重构过程中 **必须保留**，不得删除、重命名或改变类型：

#### 顶层 StableAgentToolResult 字段

| 字段 | 类型 | 说明 | 冻结 |
|------|------|------|------|
| `ok` | bool | 执行是否成功 | ✅ |
| `run_id` | str | 运行 ID | ✅ |
| `tool_name` | str | 工具名 | ✅ |
| `data` | dict | 结构化返回数据 | ✅ |
| `plain_text` | str | 人类可读结果 | ✅ |
| `plain_text_zh` | str | 中文结果 | ✅ |
| `plain_text_en` | str | 英文结果 | ✅ |
| `dashboard_url` | str | Dashboard 链接 | ✅ |
| `trace_url` | str | Trace 链接 | ✅ |
| `warnings` | list[str] | 警告信息 | ✅ |
| `next_actions` | list[str] | 建议后续操作 | ✅ |
| `is_error` | bool | 是否错误 | ✅ |

#### data 子对象字段

| 字段 | 类型 | 说明 | 冻结 |
|------|------|------|------|
| `ok` | bool | 执行是否成功 | ✅ |
| `run_id` | str | 运行 ID | ✅ |
| `dashboard_url` | str | Dashboard URL | ✅ |
| `observer_url` | str | Observer URL | ✅ |
| `event_sync_ok` | bool | 事件同步是否成功 | ✅ |
| `event_api_ok` | bool | 事件 API 是否正常 | ✅ |
| `dashboard_replay_ok` | bool | Dashboard 回放是否正常 | ✅ |
| `api_event_count` | int | API 返回的事件数量 | ✅ |
| `emitted_event_count` | int | 发出的事件数量 | ✅ |
| `missing_required_events` | list[str] | 缺失的必需事件 | ✅ |
| `api_missing_required_events` | list[str] | API 缺失的必需事件 | ✅ |
| `eval_passed` | bool | 评测是否通过 | ✅ |
| `eval_score` | float\|None | 评测分数 | ✅ |
| `si_report` | dict | 自我优化报告 | ✅ |
| `progress_pct` | int | 进度百分比 | ✅ |
| `current_stage` | str | 当前阶段 | ✅ |

### Required Events 冻结

#### 正常路径 (13 个)

```
task.received
intent.parsed
context.budgeted
temporal_memory.retrieved
rag.retrieved
context.compression_guard.checked
context.built
workflow.plan.created
workflow.step.started
workflow.step.completed
eval.completed
self_improvement.checked
task.completed
```

#### 失败学习路径 (4 个额外)

```
regression.generated
memory.update.candidate
skill.patch.proposed
validation.checked
```

### 工具名冻结

以下工具名在重构过程中 **不得删除或重命名**：

```
stableagent.task.os_agent
stableagent.trace.get_run
stableagent.feedback.correct_and_remember
stableagent.feedback.remember
stableagent.feedback.dont_do_this_again
stableagent.token.report
stableagent.capsule.status
```

### 事件字段冻结

每个事件字典必须包含以下字段：

```
run_id
event_type
timestamp
payload
avatar_state
importance
stage
progress_pct
status_text_zh
decision_summary_zh
why_zh
next_step_zh
```

---

## 冻结验证方式

每次提交前必须运行：

```bash
python -m py_compile stable_agent/gateway/unified_tool_registry.py
python tools/check_closed_loop.py
python tools/integration_test.py  # 需要服务器运行
```

## 回滚策略

如果重构导致 `stableagent.task.os_agent` 正常路径失败：

1. `git stash` 保存当前变更
2. `git checkout main` 回到基线
3. 逐个 cherry-pick 安全的提交
4. 重新验证闭环
