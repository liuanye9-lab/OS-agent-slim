# ARCHITECTURE_AUDIT.md — StableAgent OS V6-Professional

## 审计范围

围绕核心闭环逐节点审计：

```text
Task → Plan → Action → Observation → Trace → Eval → Failure Attribution
→ Reflection → Skill Patch → Validation Gate → Human Review → Export best_skill.md
```

审计时间：2026-05-28。审计基线：V5.6（commit `e368632`），792 测试全部通过。

---

## 0. 审计前置检查

```text
✅ except Exception: pass  → 0 处（V5.6 已清理）
✅ print() in production  → 0 处（V5.6 已清理）
✅ chain_of_thought 字段  → 0 处（从未存在）
✅ TODO/STUB/NotImplemented → 0 处（已清理）
✅ pytest: 792/792 passed
✅ 15 MCP 工具, 含 os_agent
✅ MCP Gateway /mcp/v5/mcp JSON-RPC 2.0
✅ Dashboard V2/V3 存在
✅ skills/best_skill.md 存在
```

---

## 1. 逐节点审计

### 1.1 Task（任务入口）

| 属性 | 状态 | 证据 |
|------|------|------|
| 入口是否存在 | ✅ | `stableagent.task.process` + `stableagent.task.os_agent` |
| MCP tools/call 创建 run_id | ✅ | `RunContext.create()` 生成 run_id |
| task_input 传递 | ✅ | `args["task_input"]` → `RunContext.create(task_input=...)` |
| dashboard_url 返回 | ✅ | `_make_result` 包含 `dashboard_url` |

**审计结论**：闭环入口完整。

### 1.2 Plan（规划阶段）

| 属性 | 状态 | 证据 |
|------|------|------|
| Workflow 数据类 | ✅ | `models.py` 定义 `Workflow` + `SpanStatus` |
| WorkflowStateMachine | ✅ | 状态迁移逻辑 |
| 层级规划 (Plan → SubSteps) | ⚠️ | Workflow 缺 `sub_steps` 字段 |
| 经验注入 Plan | ⚠️ | MemoryRouter 检索记忆，但未显式注入 Plan 阶段 |

**P0 差距**：Workflow 结构缺少 `sub_steps` 字段，不支持层级规划。
MemoryRouter 的记忆检索结果未在 Plan 阶段显式引用。

### 1.3 Action（执行阶段）

| 属性 | 状态 | 证据 |
|------|------|------|
| Tool Router | ✅ | `tool_router.py` 路由 + 安全检查 |
| MCP tools/call | ✅ | 15 工具通过 JSON-RPC 暴露 |
| Security Policy | ✅ | 风险分级 + forbidden 工具拦截 |
| Approval Manager | ✅ | 高风险操作需人工审批 |

**审计结论**：执行链路完整。

### 1.4 Observation（观察阶段）

| 属性 | 状态 | 证据 |
|------|------|------|
| TraceEvent 发布 | ✅ | EventStream.publish_sync() |
| RunContext 统一标识 | ✅ | run_id + tool_call_id + trace_id + span_id |
| ProgressModel 11阶段 | ✅ | 5%→100% 单调递增 |
| Dashboard 实时同步 | ✅ | WebSocket /ws/runs/{run_id} |

**审计结论**：观察阶段完整。

### 1.5 Trace（追踪阶段）

| 属性 | 状态 | 证据 |
|------|------|------|
| TraceEvent 字段完整性 | ✅ | run_id, stage, status_text_zh, why_zh, progress_pct, avatar_state |
| Event 链完整性 | ✅ | mcp.call.received → tool.risk_checked → tool.completed |
| span_id 父子关系 | ✅ | RunContext.child_span() |
| RunStore 回放 | ✅ | get_events(run_id) |

**审计结论**：Trace 链路完整。

### 1.6 Eval（评估阶段）

| 属性 | 状态 | 证据 |
|------|------|------|
| Evaluator 存在 | ✅ | 三层评测（RuleEval → ComponentEval → 加权汇总） |
| EvaluationResult 存在 | ✅ | 14 个评分字段 |
| **failure_attribution** 字段 | ❌ | 缺 `failure_attribution: dict` |
| **step_efficiency** 字段 | ❌ | 缺 `step_efficiency: float` |
| 幻觉检测 | ⚠️ | 规则检测，非 LLM judge |

**P0 差距**（P0-3）：
- `EvaluationResult` 有 `failure_reasons: list[str]` 但有自由文本，缺少结构化归因。
- 缺少 `failure_attribution` 字段标明"哪一步失败、为什么"。
- 缺少 `step_efficiency` 字段（步数效率）。

### 1.7 Failure Attribution（失败归因）

| 属性 | 状态 | 证据 |
|------|------|------|
| BadCaseManager.record_case | ✅ | 超过阈值记录 |
| failure_reason 字符串 | ✅ | BadCase 有 `failure_reason` 字段 |
| **结构化 attribution** | ❌ | failure_reason 是自由文本 |
| **convert_to_regression_case** | ⚠️ | `convert_to_eval_case()` 存在，但未导出到 `data/regression_cases.jsonl` |

**P0 差距**（P0-4）：
- BadCase → Regression Case 路径不完整。
- `data/regression_cases.jsonl` 文件不存在。
- BadCase 缺少 `id`、`tags`、`source_run_id` 等可追踪字段。

### 1.8 Reflection（反思阶段）

| 属性 | 状态 | 证据 |
|------|------|------|
| generate_improvement_rule | ✅ | 基于 BadCase 模板生成改进规则 |
| _analyze_failures | ✅ | SkillOptimizationEngine 失败分析 |
| **反思模板** | ✅ | 已在 prompt_contracts.py |

**审计结论**：反思阶段基本完整，但反思质量依赖 BadCase 的质量。

### 1.9 Skill Patch（技能补丁）

| 属性 | 状态 | 证据 |
|------|------|------|
| Patch Generator | ✅ | patch_applier.py + patch_merger.py |
| Diff 格式 | ✅ | add/delete/replace |
| **candidates/ 目录** | ❌ | `skills/candidates/` 不存在 |
| **rejected/ 目录** | ❌ | `skills/rejected/` 不存在 |
| **自动覆盖 best_skill.md** | ⚠️ | export_best_skill() 未强制验证 |

**P0 差距**（P0-5）：
- 缺少 `skills/candidates/` 和 `skills/rejected/` 目录。
- `SkillExporter.export()` 和 `SkillDocumentStore.promote_to_best()` 缺少硬性的"验证通过才允许"约束。

### 1.10 Validation Gate（验证门）

| 属性 | 状态 | 证据 |
|------|------|------|
| ValidationGate 类 | ✅ | validate() + _simulate_execution + _evaluate_skill |
| Regression Suite | ✅ | regression_suite.py |
| old_score vs new_score | ✅ | 已实现 |
| delta 计算 | ✅ | 已实现 |
| **hard gate 阻断** | ⚠️ | 存在但未被始终强制 |

**P0 差距**（P0-6）：
- ValidationGate 存在，但调用方（SkillOptimizationEngine）在 ValidationGate 返回 `passed=False` 后，
  仍然可能调用 `export_best_skill()`。需要硬性阻断。

### 1.11 Human Review（人工审核）

| 属性 | 状态 | 证据 |
|------|------|------|
| ApprovalManager | ✅ | approve/reject |
| SkillExport 人工确认 | ❌ | `export_best_skill()` 直接执行，无人工确认步骤 |
| Dashboard 审批 UI | ⚠️ | 安全审批有，技能导出审批无 |

**P0 差距**（P0-7）：
- `SkillExporter.export()` 无任何人工确认步骤。应有 `requires_human_review` 标志。

### 1.12 Export best_skill.md（导出最优技能）

| 属性 | 状态 | 证据 |
|------|------|------|
| SkillExporter | ✅ | 版本管理 + 导出 |
| SkillDocumentStore | ✅ | promote_to_best() + revert() |
| skill_versions.jsonl | ✅ | 记录每次导出 |
| **P0：验证门+人工确认链** | ❌ | 上述缺口导致导出链路不可信 |

**审计结论**：导出机制存在，但缺少前置验证和人工确认的硬性约束。

---

## 2. P0 差距列表

| ID | 问题 | 影响 | 相关文件 | 本轮修复 |
|----|------|------|----------|----------|
| P0-1 | Workflow 缺少 sub_steps | 无层级规划 | models.py:Workflow | ✅ |
| P0-2 | MemoryRouter 检索结果未显式注入 Plan | 经验未利用 | orchestrator.py | ✅ |
| P0-3 | EvaluationResult 缺 failure_attribution + step_efficiency | 归因不结构化 | models.py:EvaluationResult | ✅ |
| P0-4 | BadCase → Regression Case 路径不完整 | 失败案例无法复测 | eval_and_bad_case.py | ✅ |
| P0-5 | 缺 skills/candidates/ + skills/rejected/ 目录 | Patch 管理混乱 | skills/ 目录 | ✅ |
| P0-6 | ValidationGate 非硬约束 | 可能跳过验证 | skill_optimization_engine.py | ✅ |
| P0-7 | SkillExport 无人确认步骤 | 自动覆盖风险 | skill_exporter.py | ✅ |
| P0-8 | README 与代码不完全对齐 | 文档偏差 | README.md | ✅ |

---

## 3. 架构完整性评分

| 闭环节点 | 完整性 | 可信度 |
|----------|--------|--------|
| Task | 100% | 高 |
| Plan | 75% | 中（缺 sub_steps） |
| Action | 100% | 高 |
| Observation | 100% | 高 |
| Trace | 100% | 高 |
| Eval | 80% | 中（缺归因字段） |
| Failure Attribution | 50% | 低（未结构化） |
| Reflection | 80% | 中 |
| Skill Patch | 65% | 中（目录缺失） |
| Validation Gate | 75% | 中（非硬约束） |
| Human Review | 30% | 低（技能导出无确认） |
| Export | 60% | 低（缺验证链） |

**总体评分：75%** — 基础闭环存在，但 Failure Attribution → Validation Gate → Human Review 链路薄弱。

---

## 4. 证据汇总

```text
✅ 792 tests, 0 failures
✅ 15 MCP 工具
✅ MCP Gateway JSON-RPC 2.0
✅ Dashboard V2/V3 WebSocket 实时同步
✅ EventStream.publish_sync()（V5.6 修复）
✅ ValidationGate 类存在
✅ SkillExporter 类存在
✅ RegressionSuite 类存在
❌ EvaluationResult 缺 failure_attribution
❌ data/regression_cases.jsonl 不存在
❌ skills/candidates/ 目录不存在
❌ skills/rejected/ 目录不存在
❌ SkillExport 缺 HumanReview gate
```

---

## 5. 与 README 的对齐检查

| README 声明 | 代码实际 | 状态 |
|-------------|----------|------|
| "Memory Router" | 存在 ✅ | 对齐 |
| "RAG Context Pack" | 存在 ✅ | 对齐 |
| "Workflow State Machine" | 存在 ✅ | 对齐 |
| "Eval & Bad Case" | 存在 ✅ | 对齐 |
| "Trace EventBus" | 存在 ✅ | 对齐 |
| "SkillOpt 自迭代" | 存在 ✅ | 对齐 |
| "Regression Benchmark" | README 提了，regression_suite.py 存在但缺数据 | ⚠️ |
| "Validation Gate" | 存在但非硬约束 | ⚠️ |
| "Human Review" | 安全审批有，技能导出审批无 | ⚠️ |
