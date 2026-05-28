# StableAgent OS V5.6 — 工程治理审计报告

> 扫描时间：2026-05-28 | 当前版本：V5.5 (731 tests)

## 一、MCP 实现清单（严禁新增第四个）

| 版本 | 文件 | 状态 |
|------|------|------|
| V3 | `mcp_server.py` + `mcp_tools.py` | 仅 bug fix，不新增业务 |
| V4 | `mcp/skillopt_tools.py` | 兼容保留，不新增能力 |
| **V5** | `gateway/` 7个模块 | **唯一活跃 MCP 主入口** |

✅ 无第四个实现。所有新能力走 `gateway/unified_tool_registry.py`。

## 二、`except Exception:` 静默吞异常 — 52 处

### 高危文件（≥5处）

| 文件 | 数量 | 行号 |
|------|------|------|
| `storage.py` | 20 | 216,241,261,280,341,360,424,465,487,561,580,647,665,739,759,831,863,879... |
| `orchestrator.py` | 10 | 345,365,371,479,495,502,544,580,675,712 |
| `tool_router.py` | 5 | 169,287,389,415,428 |
| `trace_event_bus.py` | 5 | 107,324,373,429,503 |
| `dashboard.py` | 5 | 176,358,363,469,481 |
| `dashboard_sync.py` | 2 | 85,97 |
| `skillopt_tools.py` | 2 | 528,536 |
| `token_meter.py` | 2 | 39,76 |
| `skill_document_store.py` | 1 | 366 |

**要求**：全部改为 `logger.exception()` 或 `logger.warning()` + 显式处理。

## 三、`print()` 生产代码 — 2 处

| 文件 | 行号 | 说明 |
|------|------|------|
| `workflow_state_machine.py` | 278, 861 | 调试用 print，应改 `logger.info()` |

✅ `orchestrator.py` 中的 print 在 `__main__` 块内（CLI入口），允许保留。

## 四、事件循环手动管理 — 1 处

| 文件 | 行号 | 问题 |
|------|------|------|
| `tool_router.py` | 398-416 | `get_event_loop()` + `ensure_future()` + `run_until_complete()` |

**修复**：EventStream 提供 `publish_sync()` 方法，handler 内禁止直接操作 event loop。

## 五、FastAPI Mount 顺序

当前顺序（`web/server.py`）：
```
app.mount("/mcp/v5", v5_app)   # ← 先挂子路径 ✅
app.mount("/mcp", mcp_server.app)  # ← 后挂父路径 ✅
```
✅ 已正确。

## 六、STUB 清单 — 需优先替换

| 文件 | STUB 内容 | 替换优先级 |
|------|-----------|-----------|
| `rag_context_pack.py` | embedding/向量检索占位 | P0 — 暴露 HybridRetriever 接口 |
| `memory_router.py` | 关键词→语义搜索 | P0 — 暴露 RetrieverProtocol |
| `eval_and_bad_case.py` | 幻觉检测随机/占位 | P1 — 规则引擎 + 可选 LLM judge |
| `git_diff_checkpoint.py` | 7处 subprocess STUB | P1 — 增加 timeout + Path.resolve |
| `workflow_state_machine.py` | RAG 结果占位 | P2 — 对接 V5 gateway |
| `skill_optimizer/` | patch validation/rejected buffer | P1 — 真实落盘 |
| `dashboard_sync.py` | run_id 事件订阅 | P1 — 真实联动 |

## 七、依赖缺口

当前 `pyproject.toml` 缺失：
- ❌ `pydantic>=2.0.0`
- ❌ `httpx>=0.27.0`
- ❌ dev 依赖组（pytest、ruff）
- ❌ 可选 extras（rag、llm）

## 八、安全检查

| 项 | 状态 |
|-----|------|
| `eval()`/`exec()`/`__import__()` | ✅ 未发现 |
| `subprocess` timeout | ⚠️ `swe_sandbox.py` 有 timeout，`git_diff_checkpoint.py` 部分有 |
| `cwd` Path.resolve() | ❌ `git_diff_checkpoint.py` 未做 |
| git repo 验证 | ❌ 未验证 `.git` 存在 |

## 九、现有工具注册（14个）

```
stableagent.task.process
stableagent.context.build
stableagent.context.estimate_budget
stableagent.memory.retrieve
stableagent.memory.write_candidate
stableagent.rag.retrieve
stableagent.eval.evaluate
stableagent.badcase.record
stableagent.skillopt.status
stableagent.skillopt.get_current_skill
stableagent.skillopt.run_epoch
stableagent.skillopt.export_best
stableagent.trace.get_run
stableagent.approval.respond
```

**缺失但 spec 要求**：无新增工具需求，但 handler 签名需统一（`_h_<domain>_<action>` 命名），`_make_result` 需支持双语字段。

## 十、DecisionTrace / BilingualText 现状

- `explanation/bilingual_text.py` — 已有 `BilingualText` + `I18nManager`
- `explanation/decision_narrator.py` — 已有 `DecisionNarrator`（19 事件映射）
- `observation/decision_trace.py` — 已有 `DecisionTrace` + `DecisionEvidence`
- `observation/decision_trace_builder.py` — 已有 `DecisionTraceBuilder`
- `observation/learning_evidence.py` — 已有 `LearningEvidence`
- `observation/run_insight.py` — 已有 `RunInsight`
- `observation/dashboard_projection.py` — 已有 `DashboardProjection`

**需升级**：
1. `TraceEvent` 缺 `importance` + `decision_trace` + 双语字段
2. `StableAgentToolResult` 缺 `plain_text_zh`/`plain_text_en`/`dashboard_url`
3. `DecisionNarrator` 需扩展 `explain_why`/`summarize_discarded`
4. 新增 `stage_explainer.py`/`evidence_summarizer.py`/`learning_explainer.py`/`user_friendly_formatter.py`
5. 新增 `UserFeedbackSignal` 数据模型

## 十一、Dashboard V2 现状

- `dashboard_v2.html` — 已有 5 区布局
- `dashboard_v2.js` — 已有 WebSocket 连接
- `avatar_scene.js` — 已有 Canvas 动画
- `decision_timeline.js` — 已有时间线
- `learning_panel.js` — 已有学习面板
- `i18n.js` — 已有国际化
- `styles_v2.css` — 已有样式

**需升级**：
1. 像素小人从抽象状态升级为 13 种语义场景映射
2. 决策卡片增加"丢弃了什么"/"为什么"
3. 学习面板增加 diff 展示 + 未触发原因
4. 新增用户反馈按钮
5. RunInsight 任务总结卡片

## 十二、测试现状

当前 40 个测试文件。需新增：
- `test_unified_tool_registry.py`（handler 签名+依赖注入）
- `test_tool_schemas.py`（schema 分离验证）
- `test_tool_router_events.py`（事件链完整性）
- `test_event_stream_sync_async.py`（sync/async 发布）
- `test_no_silent_exceptions.py`（全局扫描）
- `test_dependency_injection.py`（DI 验证）

---

## 总结

| 问题类别 | 严重程度 | 影响范围 |
|----------|----------|---------|
| 52 处静默吞异常 | 🔴 高 | 全项目 |
| Event loop 手动管理 | 🔴 高 | gateway/ |
| 缺失依赖声明 | 🟡 中 | pyproject.toml |
| STUB 待替换 | 🟡 中 | 5 个模块 |
| 双语字段不完整 | 🟡 中 | models + explanation |
| 像素小人语义化 | 🟢 低 | web/ |
