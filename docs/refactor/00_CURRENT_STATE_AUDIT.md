# 00_CURRENT_STATE_AUDIT.md

> 审计时间: 2026-06-02T22:23:00+08:00
> 审计范围: OS-Agent 全项目
> 审计目的: Phase 0 收敛式重构前基线记录

---

## 1. 顶层目录结构

```
OS-Agent/
├── stable_agent/          # 核心 Python 包 (23 个子包)
│   ├── gateway/           # MCP Gateway (tool_schemas, tool_router, unified_tool_registry, run_context)
│   ├── observation/       # RunStore, EventStream, DashboardSync, DecisionTraceBuilder
│   ├── context/           # ContextDecisionEngine, ContextBudgetManager, CompressionGuard
│   ├── memory/            # MemoryRouter, MemoryBank, TemporalMemoryBridge
│   ├── evals/             # Evaluator, RegressionSuite, RubricJudge, ValidationDataset
│   ├── skill_optimizer/   # SkillOptEngine, DocStore, PatchMerger
│   ├── self_improvement/  # SelfImprovementProofLoop
│   ├── capsule/           # CapsuleManager, CapsuleDoctor, MemoryLifecycleManager
│   ├── feedback/          # FeedbackLearningService
│   ├── understanding/     # SemanticInterpreter, ExpressionProfileManager, CorrectionStore
│   ├── model_profile/     # ModelProfileManager, ModelRouter
│   ├── token/             # BudgetLedger, TokenEstimator
│   ├── personal_eval/     # EvalCaseManager, ABRegressionRunner, RubricManager, FeedbackProcessor
│   ├── saas/              # WorkspaceService, ProjectService, RunService, SaasRepository
│   ├── approval/          # ApprovalResumeService, PendingToolStore
│   ├── effectiveness/     # ABRunner, ExperimentStore, Metrics
│   ├── explanation/       # DecisionNarrator, EvidenceSummarizer, LearningExplainer
│   ├── intent/            # IntentAlignmentEvaluator, IntentTaxonomy, PreferenceDriftDetector
│   ├── security/          # SecurityPolicy, SecurityContext
│   ├── runtime/           # RunLifecycle (RunStage, RunStageMeta, STAGE_PROGRESS)
│   ├── db/                # MigrationRunner
│   ├── mcp/               # MCP 协议相关
│   └── quickstart/        # 快速启动
├── web/                   # FastAPI Web 应用
│   ├── app.py             # create_app() 入口
│   ├── server.py          # uvicorn 入口
│   ├── routes/            # API/页面路由 (api, runs, dashboard, approvals, auth, etc.)
│   ├── static/            # JS/CSS (run_observer.js, dashboard_v2/v3.js, avatar_scene.js, etc.)
│   └── templates/         # HTML 模板 (run_observer.html, dashboard.html, etc.)
├── tests/                 # 135 个测试文件
├── tools/                 # check_closed_loop.py, integration_test.py, real_llm_e2e_test.py
├── scripts/               # deploy_local.sh, integration_test.sh, smoke_test.sh, etc.
├── data/                  # 运行时数据 (eval_results, rollouts, validation, sqlite)
├── skills/                # 技能版本目录
├── experiments/           # 实验数据
├── docs/                  # 文档 (44 个文件)
├── api/                   # Vercel API 入口
├── pyproject.toml         # 项目配置 (Python >= 3.11)
├── Dockerfile             # Docker 构建
└── docker-compose.yml     # Docker Compose
```

## 2. 当前 MCP 工具数量

**总计: 55 个工具** (注释声称 14 个，实际随 V5-V11 迭代扩展到 55 个)

### 按领域分布

| 领域 | 数量 | 工具 |
|------|------|------|
| task | 2 | task.process, task.os_agent |
| context | 2 | context.build, context.estimate_budget |
| memory | 7 | memory.retrieve, memory.write_candidate, memory.health, memory.review, memory.prune, memory.promote, memory.delete |
| rag | 1 | rag.retrieve |
| eval | 6 | eval.evaluate, eval.run, eval.case.create, eval.case.list, eval.run_ab, eval.rubric.get, eval.rubric.update |
| badcase | 1 | badcase.record |
| skillopt | 4 | skillopt.status, skillopt.get_current_skill, skillopt.run_epoch, skillopt.export_best |
| trace | 1 | trace.get_run |
| approval | 1 | approval.respond |
| understanding | 2 | understanding.trace, understanding.correct |
| expression | 3 | expression.list, expression.add, expression.delete |
| workspace | 1 | workspace.create |
| project | 2 | project.create, project.list |
| run | 1 | run.get |
| regression | 1 | regression.create |
| skill | 4 | skill.patch_propose, skill.validate, skill.review, skill.export_best |
| usage | 1 | usage.get |
| apikey | 2 | apikey.create, apikey.revoke |
| capsule | 2 | capsule.status, capsule.doctor |
| model | 4 | model.profile, model.list, model.suggest, model.update |
| feedback | 3 | feedback.remember, feedback.dont_do_this_again, feedback.correct_and_remember |
| token | 3 | token.report, token.run, token.summary |

## 3. stableagent.task.os_agent 输入 Schema

```json
{
  "task_input": "string (required)",
  "mode": "string (default: 'auto')",
  "run_id": "string (optional)",
  "open_dashboard": "boolean (default: true)",
  "force_eval_failed": "boolean (default: false)",
  "force_failure_mode": "string (optional)",
  "force_regression_case": "boolean (default: false)",
  "force_skill_patch": "boolean (default: false)",
  "force_validation_passed": "boolean|null (default: null)",
  "dry_run_learning": "boolean (default: true)",
  "project_id": "string (optional)",
  "agent_id": "string (optional)"
}
```

## 4. stableagent.task.os_agent 输出 Schema

```json
{
  "ok": "boolean",
  "run_id": "string",
  "tool_call_id": "string",
  "tool_name": "string",
  "data": {
    "ok": "boolean",
    "run_id": "string",
    "dashboard_url": "string",
    "observer_url": "string",
    "event_sync_ok": "boolean",
    "event_api_ok": "boolean",
    "dashboard_replay_ok": "boolean",
    "api_event_count": "integer",
    "emitted_event_count": "integer",
    "missing_required_events": ["string"],
    "api_missing_required_events": ["string"],
    "eval_passed": "boolean",
    "eval_score": "float|null",
    "si_report": "object",
    "progress_pct": "integer",
    "current_stage": "string",
    "understanding_trace": "object",
    "expression_matches": ["object"],
    "token_report": "object"
  },
  "plain_text": "string",
  "plain_text_zh": "string",
  "plain_text_en": "string",
  "dashboard_url": "string",
  "trace_url": "string",
  "warnings": ["string"],
  "next_actions": ["string"],
  "is_error": "boolean"
}
```

## 5. 当前 Required Events

### 正常路径 (13 个)

1. `task.received`
2. `intent.parsed`
3. `context.budgeted`
4. `temporal_memory.retrieved`
5. `rag.retrieved`
6. `context.compression_guard.checked`
7. `context.built`
8. `workflow.plan.created`
9. `workflow.step.started`
10. `workflow.step.completed`
11. `eval.completed`
12. `self_improvement.checked`
13. `task.completed`

### 失败学习路径 (4 个额外)

14. `regression.generated`
15. `memory.update.candidate`
16. `skill.patch.proposed`
17. `validation.checked`

## 6. 当前 Dashboard / Observer 路由

| 路由 | 方法 | 说明 |
|------|------|------|
| `/observe/{run_id}` | GET | Observer 主页面 (run_observer.html + meta run-id) |
| `/dashboard/` | GET | Dashboard V1 |
| `/dashboard-sync/ws/runs/{run_id}` | WebSocket | 实时事件推送 |
| `/runs/{run_id}` | GET | Run 概览页 |
| `/runs/{run_id}/detail` | GET | Run 详情页 |

## 7. 当前 RunStore / Events API 路由

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/runs` | POST | 创建 Run |
| `/api/runs/{run_id}` | GET | 获取 Run 概览 |
| `/api/runs/{run_id}/detail` | GET | 获取 Run 详情 |
| `/api/runs/{run_id}/events` | GET | 获取 Run 事件列表 (V10 结构化) |
| `/api/runs/{run_id}/summary` | GET | 获取 Run 摘要 |
| `/api/runs/{run_id}/feedback` | POST | 提交用户反馈 |
| `/api/runs/{run_id}/understanding` | GET | 获取 Understanding Trace |
| `/api/runs/{run_id}/token` | GET | 获取 Token Report |
| `/api/runs/{run_id}/learning` | GET | 获取 Learning Events |
| `/api/runs/{run_id}/badcases` | GET | 获取 Bad Cases |
| `/api/health` | GET | 健康检查 |
| `/api/usage` | GET | 用量摘要 |
| `/api/capsule/status` | GET | Capsule 状态 |
| `/api/memory/health` | GET | 记忆健康报告 |
| `/api/feedback/remember` | POST | "记住这个" |
| `/api/feedback/dont-do-this-again` | POST | "下次别这样" |
| `/api/feedback/correct-and-remember` | POST | "纠正并记住" |

## 8. 当前 SkillOpt / Skill / Feedback / Eval 相关工具

### SkillOpt (4 个)
- `stableagent.skillopt.status` — 引擎状态
- `stableagent.skillopt.get_current_skill` — 当前技能文档
- `stableagent.skillopt.run_epoch` — 运行优化回合
- `stableagent.skillopt.export_best` — 导出最优技能

### Skill (SaaS, 4 个)
- `stableagent.skill.patch_propose` — 提议 Skill 补丁
- `stableagent.skill.validate` — 验证 Skill 补丁
- `stableagent.skill.review` — 审核 Skill 补丁
- `stableagent.skill.export_best` — 导出最佳 Skill

### Feedback (3 个)
- `stableagent.feedback.remember` — 记住这个
- `stableagent.feedback.dont_do_this_again` — 下次别这样
- `stableagent.feedback.correct_and_remember` — 纠正并记住

### Eval (6 个)
- `stableagent.eval.evaluate` — 评测输出质量
- `stableagent.eval.run` — SaaS 运行评测
- `stableagent.eval.case.create` — 创建评估用例
- `stableagent.eval.case.list` — 列出评估用例
- `stableagent.eval.run_ab` — A/B 回归测试
- `stableagent.eval.rubric.get` / `update` — 评分维度管理

## 9. 当前非核心工具 (workspace / project / apikey / usage)

| 工具 | 说明 | 分类 |
|------|------|------|
| `stableagent.workspace.create` | SaaS 工作空间 | 非核心 |
| `stableagent.project.create` | SaaS 项目 | 非核心 |
| `stableagent.project.list` | SaaS 项目列表 | 非核心 |
| `stableagent.run.get` | SaaS 运行详情 | 非核心 |
| `stableagent.regression.create` | 回归用例创建 | 非核心 |
| `stableagent.usage.get` | 用量查询 | 非核心 |
| `stableagent.apikey.create` | API Key 创建 | 非核心 |
| `stableagent.apikey.revoke` | API Key 撤销 | 非核心 |
| `stableagent.model.profile` | 模型画像 | 非核心 |
| `stableagent.model.list` | 模型列表 | 非核心 |
| `stableagent.model.suggest` | 模型推荐 | 非核心 |
| `stableagent.model.update` | 模型更新 | 非核心 |

## 10. unified_tool_registry.py 职责与代码行数

### 基本信息
- **文件行数**: 2465 行
- **注册工具数**: 55 个
- **最复杂 handler**: `_h_task_os_agent` (~575 行)

### 嵌入的业务逻辑 (不应在此文件中)

1. **任务执行流水线** (9 阶段): task.received → intent.parsed → context.budgeted → temporal_memory → rag → compression_guard → context.built → workflow → eval → self_improvement → task.completed
2. **上下文构建**: ContextDecisionEngine, ContextBudgetManager, CompressionGuard 调用
3. **记忆检索**: TemporalMemoryBridge, MemoryRouter 调用
4. **RAG 检索**: RagManager 调用
5. **评测**: Evaluator 调用 + 评分逻辑
6. **自我优化闭环**: ProofLoop.evaluate_and_learn() 调用
7. **事件发布**: EventStream.publish_sync + RunStore.append_event
8. **事件同步健康检查**: event_sync_ok / event_api_ok / dashboard_replay_ok 计算
9. **RunStore 生命周期**: create_run → append_event → mark_completed
10. **Token 预算**: TokenEstimator + BudgetLedger 调用
11. **语义理解**: SemanticInterpreter + ExpressionProfileManager 调用
12. **记忆生命周期**: MemoryLifecycleManager (health/review/prune/promote/delete)
13. **SaaS 商业逻辑**: WorkspaceService, ProjectService, RunService, ApiKeyManager, UsageCounter

### 依赖的外部服务

通过 `self._orchestrator` 访问:
- decision_engine, budget_manager, memory_router, memory_bank, rag_manager
- evaluator, bad_case_manager, skillopt_engine, event_bus, proof_loop
- temporal_memory_bridge, context_compression_guard

通过 `self._tool_router` 访问:
- _event_stream, _run_store

延迟导入:
- ApprovalResumeService, RunLifecycle, SemanticInterpreter, ExpressionProfileManager
- CorrectionStore, CapsuleManager, CapsuleDoctor, MemoryLifecycleManager
- TokenEstimator, BudgetLedger, ModelProfileManager, ModelRouter
- EvalCaseManager, ABRegressionRunner, RubricManager, FeedbackProcessor
- WorkspaceService, ProjectService, RunService, SaasRepository (SaaS)

---

## 审计结论

### 架构热点
1. **unified_tool_registry.py (2465行)** — 职责过重，是最大架构风险
2. **RunStore (纯内存)** — Observer 0% 问题根因
3. **55 个 MCP 工具** — 过宽，需要 profile 化

### 收敛方向
1. 拆分 unified_tool_registry.py → core/executor + core/curator + core/validator
2. 工具 profile 化 (minimal: 8-12, default: ~20, full: 55)
3. SkillRepo v2 (文件 + SQLite)
4. Observer replay 修复 (RunStore 持久化)
5. CLI-first + MCP stdio 统一入口
