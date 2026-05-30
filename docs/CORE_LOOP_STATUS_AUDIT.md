# CORE_LOOP_STATUS_AUDIT.md — V6.0 硬化审计

> 审计日期：2026-05-30
> 方法论：逐个模块检查 exists / called / tested / silent-fails / stubs / serves-loop / serves-dashboard

---

## 审计结论总表

| # | 模块 | 存在 | 被调用 | 测试 | 静默失败 | Stub | 闭环 | Dashboard |
|---|------|------|--------|------|----------|------|------|-----------|
| 1 | `runtime/run_lifecycle.py` | ✅ | ✅ DecisionTraceBuilder | ✅ 8 tests | 无 | 无 | ✅ | ✅ |
| 2 | `memory/temporal_memory_router.py` | ✅ | ❌ 未接入主流程 | ✅ 8 tests | 无 | 无 | ❌ | ❌ |
| 3 | `context/context_compression_guard.py` | ✅ | ❌ 未接入主流程 | ✅ 10 tests | 无 | 无 token 截断 | ❌ | ❌ |
| 4 | `self_improvement/proof_loop.py` | ✅ | ✅ orchestrator | ✅ 10 tests | **P0** `validation_passed=True` | 无真实验证 | ❌ | ❌ |
| 5 | `self_improvement/memory_update_candidate.py` | ✅ | ⚠️ 创建但不 promote | ✅ | 无 | 无 | ⚠️ | ❌ |
| 6 | `self_improvement/skill_patch_candidate.py` | ✅ | ⚠️ 自动推进 | ✅ | 无 | 无真实 gate | ⚠️ | ❌ |
| 7 | `observation/decision_trace_builder.py` | ✅ | ✅ ToolRouter | ✅ | **P0** `except:pass` | 无 | ✅ | ✅ |
| 8 | `gateway/tool_router.py` | ✅ | ✅ MCP Gateway | ✅ | **P0** `except:pass` | STAGE_MAP 仅 execution | ✅ | ⚠️ |
| 9 | `orchestrator.py` | ✅ | ✅ web/app.py | ⚠️ 无集成测试 | **P2** run_id 未定义 | 无 | ⚠️ | ❌ |
| 10 | `workflow_state_machine.py` | ✅ | ✅ orchestrator | ✅ | 无 | RAG/LEARN STUB | ⚠️ | ❌ |
| 11 | `web/run_observer.html+js` | ✅ | ✅ 有 WebSocket | ⚠️ 无集成测试 | 无 | 无 | ✅ | ✅ |

---

## P0 问题（必须立即修复）

### P0-1: proof_loop.py:162 — `validation_passed = True` 无条件硬置

**文件**: `stable_agent/self_improvement/proof_loop.py`
**行**: 162

```python
# 标记验证通过（当前实现为规则驱动，非 LLM 模拟）
report.validation_passed = True
```

**影响**: 任何失败经验都能自动通过 validation gate，直接进入 human_review 状态。整个闭环的 `candidate → validating → validated → waiting_review` 在一条方法调用内自动完成，没有任何外部验证。

**必须修复**: 替换为 `RegressionValidationRunner.validate_patch()` 的真实结果。

### P0-2: tool_router.py:476-477 — `except Exception: pass` 无日志静默降级

**文件**: `stable_agent/gateway/tool_router.py`
**行**: 476-477

```python
except Exception:
    pass  # 决策字段非关键，静默降级
```

**影响**: 如果 `_trace_builder.build_for_dashboard()` 抛出任何异常，所有 decision_summary_zh/why_zh/next_step_zh 等 Dashboard 关键字段全部丢失，且无任何日志。

**必须修复**: 改为 `except Exception as e: logger.exception(...)`。

### P0-3: decision_trace_builder.py:87-89 — `except Exception: pass` 同样静默

**文件**: `stable_agent/observation/decision_trace_builder.py`
**行**: 87-89

```python
except Exception:
    import logging; logging.getLogger(__name__).debug("...")
```

**影响**: RunLifecycle 元信息注入路径失败时静默降级。

**必须修复**: 改为 `logger.exception(...)` 最低告警。

---

## P1 问题（必须本轮修复）

### P1-1: TemporalMemoryRouter 未被主流程接入
- 全代码库仅 3 处 import（测试、__init__ 导出、TYPE_CHECKING）
- orchestrator 未实例化 TemporalMemoryRouter
- 时间感知记忆路由功能在运行时从未被激活

### P1-2: ContextCompressionGuard 未被主流程接入
- protect() 方法是"分类标记"而非"真实压缩"
- 缺失 enforce_budget()：无 token 截断能力
- orchestrator 未实例化 ContextCompressionGuard

### P1-3: RunContext.progress_pct 始终为 0
- ToolRouter 的 route() 未在创建 RunContext 后调用 get_stage_meta() 更新进度
- 导致 Dashboard 接收的事件中 progress_pct 始终为默认值 0

---

## P2 问题（建议修复）

### P2-1: orchestrator 中 run_id 未定义
- 413-414 行：run_id 仅在 `if approval_required:` 分支内定义
- 如果 approval_required 为 False 且 _current_run_id 为 None，524 行引用触发 NameError
- 被 `except Exception` 捕获后隐蔽绕过

### P2-2: workflow_state_machine RAG/LEARN STUB
- _step_retrieve_knowledge：RAG 结果始终为空 []
- _step_learn：不作真实学习，只是一条 MemoryItem

### P2-3: ProgressModel 仍在 observation/__init__.py 中导出
- 虽然有 @deprecated 标记，但出口未清理
