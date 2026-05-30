# StableAgent Cloud — Final Closed-Loop Hardening Audit

**日期**: 2026-05-31
**版本**: V9.0 Final Hardening
**审计人**: 首席架构师

---

## 1. os_agent 一次正常 run 实际产生哪些事件？

| # | 事件类型 | 阶段 | progress_pct |
|---|---------|------|-------------|
| 1 | task.received | received | 5 |
| 2 | intent.parsed | intent_parsing | 10 |
| 3 | context.budgeted | context_budgeting | 18 |
| 4 | temporal_memory.retrieved | temporal_memory_retrieving | 28 |
| 5 | rag.retrieved | rag_retrieving | 38 |
| 6 | context.compression_guard.checked | context_compressing | 48 |
| 7 | context.built | context_building | 55 |
| 8 | workflow.plan.created | planning | 63 |
| 9 | workflow.step.started | acting | 72 |
| 10 | workflow.step.completed | observing | 80 |
| 11 | eval.completed | evaluating | 86 |
| 12 | self_improvement.checked | evaluating | 86 |
| 13 | task.completed | completed | 100 |

**结论**: 正常路径产生 13 个事件，覆盖完整生命周期。

## 2. os_agent 一次失败 run 实际产生哪些事件？

除上述 13 个基础事件外，还会额外产生：

| # | 事件类型 | 触发条件 |
|---|---------|---------|
| 14 | regression.generated | eval_failed + force_regression_case |
| 15 | memory.update.candidate | learning_triggered |
| 16 | skill.patch.proposed | force_skill_patch 或 failure_mode 非空 |
| 17 | validation.checked | patch 存在且验证运行 |
| 18 | human_review.required | validation_passed + patches > 0 |

**结论**: 失败学习路径最多产生 18 个事件。

## 3. 是否能触发 regression.generated？

**是** — 调用 `force_eval_failed=true` + `force_regression_case=true` 即可稳定触发。

## 4. 是否能触发 skill.patch.proposed？

**是** — 调用 `force_eval_failed=true` + `force_skill_patch=true` 即可稳定触发。
即使 failure_mode 为空，force_skill_patch 也会使用 "forced_test" 作为模式。

## 5. 是否能触发 validation.checked？

**是** — 当 skill patches 存在时，evaluate_and_learn() 内部会自动运行
RegressionValidationRunner.validate_patch()，验证通过则触发 validation.checked。

## 6. 是否能触发 human_review.required？

**是** — 当 validation_passed=True 且存在 patches 时，
human_review_required=True，触发 human_review.required 事件。

## 7. Dashboard 是否能显示这些事件？

**是** — Dashboard Observer (run_observer.js) 已增强：
- 同步异常 banner (event_sync_ok=false)
- SelfImprovement Report 展示 learning_triggered / validation_passed / human_review_status / regression_cases / skill_patches
- 时间线使用中文标签映射 (STAGE_LABEL_MAP)
- 事件通过 WebSocket 实时推送

## 8. integration_test 是否强制验证这些事件？

**是** — V9.0 integration_test.py:
- 正常路径: 验证 12 个必须事件 (NORMAL_PATH_EVENTS)
- 失败学习路径: 验证 10 个必须事件 (FAILURE_PATH_EVENTS)
- 缺字段即 FAIL (不再只是 WARNING)
- event_sync_ok 必须为 True

---

## 关键变更清单

| 变更 | 文件 | 类型 |
|------|------|------|
| +force_eval_failed 参数 | unified_tool_registry.py | 新增 |
| +force_failure_mode 参数 | unified_tool_registry.py | 新增 |
| +force_regression_case 参数 | unified_tool_registry.py, proof_loop.py | 新增 |
| +force_skill_patch 参数 | unified_tool_registry.py, proof_loop.py | 新增 |
| +dry_run_learning 参数 | unified_tool_registry.py | 新增 |
| +事件同步健康检查 | unified_tool_registry.py | 修改 |
| +MemoryBank.list_items() | memory_router.py | 新增 |
| ~_items → list_items() | orchestrator.py, unified_tool_registry.py | 修复 |
| ~approve_patch 不自动导出 | proof_loop.py | 修改 |
| +export_approved_patch() | proof_loop.py | 新增 |
| +同步异常 banner | run_observer.html, run_observer.js | 新增 |
| +中文阶段标签 | run_observer.js | 新增 |
| +强事件字段验收 | integration_test.py, check_closed_loop.py | 修改 |

---

**审计结论**: V9.0 Final Hardening 彻底打通了 MCP → os_agent → RunLifecycle → TemporalMemory → CompressionGuard → Eval → SelfImprovement → Validation → HumanReview → Dashboard Observer 全链路。
