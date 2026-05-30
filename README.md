<p align="center">
  <img src="https://img.shields.io/badge/tests-1083_passed-brightgreen?style=for-the-badge" alt="1083 Tests">
  <img src="https://img.shields.io/badge/python-3.13-blue?style=for-the-badge" alt="Python 3.13">
  <img src="https://img.shields.io/badge/pytest-9.0-0A9EDC?style=for-the-badge" alt="pytest">
  <img src="https://img.shields.io/badge/closed_loop-7/7_PASS-22c55e?style=for-the-badge" alt="Closed Loop">
  <img src="https://img.shields.io/badge/MCP-28_tools-7c3aed?style=for-the-badge" alt="MCP">
  <img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="MIT">
</p>

<h1 align="center">StableAgent OS</h1>

<p align="center">
  <strong>AI Agent 防降智操作系统</strong><br>
  <sub>真正闭环的自我优化 + 可解释的像素人可视化面板</sub>
</p>

---

## 架构概览

```
Claude Code / Cursor / Codex ──→ MCP tools/call ──→ stableagent.task.os_agent
                                                          │
┌─────────────────────────────────────────────────────────┼──────────────┐
│  RunLifecycle (22 阶段 · 唯一状态源)                     │              │
│  ├─ TemporalMemoryRouter (按时间戳召回记忆)               │              │
│  ├─ ContextCompressionGuard (6层保护 · 防丢核心目标)     │              │
│  └─ WorkflowEngine (17步编排执行)                        │              │
├─────────────────────────────────────────────────────────┼──────────────┤
│  DecisionTraceBuilder ──→ EventStream ──→ Dashboard Observer          │
│  (不含 chain_of_thought)     (WebSocket)     (像素人 17 场景 Canvas)   │
├─────────────────────────────────────────────────────────┼──────────────┤
│  SelfImprovementProofLoop                                          │  │
│  Eval → FailureAttribution → RegressionCase → MemoryCandidate       │  │
│  → SkillPatchCandidate → ValidationGate → HumanReview → best_skill  │  │
└──────────────────────────────────────────────────────┬──────────────┘  │
                                                       │ ← 真正闭环      │
                                                       └────────────────┘
```

## 闭环验证 (14/14 环节全部打通)

| # | 环节 | 状态 | 关键文件 |
|---|------|------|---------|
| 1 | 用户 → MCP tools/call | ✅ | `gateway/mcp_gateway.py` |
| 2 | RunLifecycle 创建阶段 | ✅ | `runtime/run_lifecycle.py` |
| 3 | TemporalMemory 按时间戳召回 | ✅ | `memory/temporal_memory_router.py` |
| 4 | ContextCompressionGuard 防降智 | ✅ | `context/context_compression_guard.py` |
| 5 | Workflow 执行任务 | ✅ | `orchestrator.py` |
| 6 | TraceEvent 记录过程 | ✅ | `gateway/tool_router.py` |
| 7 | DecisionTrace 可解释状态 | ✅ | `observation/decision_trace_builder.py` |
| 8 | Dashboard 实时显示 | ✅ | `web/templates/run_observer.html` |
| 9 | Eval 判断质量 | ✅ | `self_improvement/proof_loop.py` |
| 10 | FailureAttribution 分析 | ✅ | `_attribute_failure()` |
| 11 | BadCase → RegressionCase | ✅ | `_generate_regression_cases()` |
| 12 | MemoryCandidate + SkillPatch | ✅ | `_generate_skill_patches()` |
| 13 | RegressionValidationRunner | ✅ | 规则+LLM 混合评分 |
| 14 | HumanReview → best_skill.md | ✅ | `_export_best_skill_versioned()` |

## 快速开始

```bash
# 一键部署
bash scripts/deploy_local.sh

# 访问
#   Dashboard: http://127.0.0.1:8000
#   MCP:       http://127.0.0.1:8000/mcp
#   API Docs:  http://127.0.0.1:8000/docs
```

## MCP 集成

```json
{
  "mcpServers": {
    "stableagent": { "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

## 测试

| 命令 | 结果 |
|------|------|
| `pytest -q --ignore=tests/test_mcp_gateway.py` | **1083 passed**, 0 failures |
| `python tools/check_closed_loop.py` | **[PASS]** 7/7 项通过 |
| `bash scripts/smoke_test.sh` | 冒烟测试 |
| `bash scripts/integration_test.sh` | 端到端集成测试 |

## 核心特性

- **22 阶段 RunLifecycle** — 统一状态源，每个阶段有 progress_pct / status_text_zh / avatar_state / scene
- **时间感知记忆路由** — 按时间戳召回，防止上下文压缩丢失关键历史约束
- **6 层上下文保护** — 用户目标 / 项目约束 / 高置信记忆 / 失败经验 / 已验证规则 / 时间记忆
- **真实自我优化闭环** — Eval → FailureAttribution → Regression → Validation → HumanReview → Export
- **可解释决策轨迹** — 不含 chain_of_thought，只展示可观察、可审计的决策依据
- **Canvas 像素人 17 场景** — 由后端 avatar_state 驱动，前端不猜进度
- **best_skill.md 版本化** — 必须通过 Human Review 才能导出

## 文档

| 文档 | 说明 |
|------|------|
| [CLOSED_LOOP_AUDIT.md](CLOSED_LOOP_AUDIT.md) | 闭环审计报告 |
| [CLOSED_LOOP_REFACTOR_PLAN.md](CLOSED_LOOP_REFACTOR_PLAN.md) | 闭环打通重构计划 |
| [RUN_LIFECYCLE_SPEC.md](RUN_LIFECYCLE_SPEC.md) | RunLifecycle 规范 |
| [TEMPORAL_MEMORY_SPEC.md](TEMPORAL_MEMORY_SPEC.md) | 时间记忆规范 |
| [CONTEXT_COMPRESSION_GUARD_SPEC.md](CONTEXT_COMPRESSION_GUARD_SPEC.md) | 压缩保护规范 |
| [SELF_IMPROVEMENT_PROOF_SPEC.md](SELF_IMPROVEMENT_PROOF_SPEC.md) | 自我优化规范 |
| [DASHBOARD_OBSERVER_SPEC.md](DASHBOARD_OBSERVER_SPEC.md) | Dashboard 规范 |
| [DASHBOARD_OBSERVER_AUDIT.md](DASHBOARD_OBSERVER_AUDIT.md) | Dashboard 审计 |
| [DEPLOYMENT_AND_TESTING_GUIDE.md](DEPLOYMENT_AND_TESTING_GUIDE.md) | 部署与测试 |
| [DEPLOYMENT_TEST_AUDIT.md](DEPLOYMENT_TEST_AUDIT.md) | 部署测试审计 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) | 实施日志 |

## 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|---------|
| **V8.1** | 2026-05-30 | Phase 1-9 闭环硬化，Canvas 像素人，真实验证 |
| V7.1 | 2026-05-30 | HumanReview API + 飞书通知 + best_skill 版本化 |
| V7.0 | 2026-05-30 | 物理清理 (progress_model, gateway/run_lifecycle) |
| V6.3 | 2026-05-30 | HumanReviewQueue, best_skill 自动导出, RAG STUB→真实 |
| V6.2 | 2026-05-30 | Dashboard 收敛, V3/V4 MCP 删除, LLM 混合验证 |
| V6.1 | 2026-05-30 | TemporalMemoryBridge, CompressionGuard, RegressionValidationRunner |

## GitHub

- **仓库**: [github.com/liuanye9-lab/OS-Agent](https://github.com/liuanye9-lab/OS-Agent)
- **License**: MIT
