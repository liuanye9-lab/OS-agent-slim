# StableAgent OS — AI 降智防御系统

> **真正的闭环自我优化 + 解释型可视化面板**

防止 AI Agent 在执行任务过程中"降智"（遗忘关键约束、跑偏方向、产生幻觉），并通过**真实闭环**让系统越用越好。

---

## 闭环架构

```
用户 / Claude Code / Codex / Cursor
    ↓
MCP tools/call → stableagent.task.os_agent
    ↓
RunLifecycle (22 阶段，统一状态源)
    ↓
TemporalMemoryRouter (按时间戳召回记忆)
    ↓
ContextCompressionGuard (保护核心目标不被压缩)
    ↓
Workflow / Orchestrator (17 步执行流程)
    ↓
DecisionTraceBuilder (生成可解释决策轨迹)
    ↓
Dashboard Observer (实时可视化：像素人 + 状态卡片 + 时间线)
    ↓
Eval → FailureAttribution → RegressionCase
    ↓
MemoryCandidate | SkillPatchCandidate → ValidationGate
    ↓
HumanReviewQueue → best_skill.md (版本化导出)
```

## 快速开始

```bash
# 一键部署
bash scripts/deploy_local.sh

# 访问
#   Dashboard: http://127.0.0.1:8000
#   MCP:       http://127.0.0.1:8000/mcp
#   API Docs:  http://127.0.0.1:8000/docs
```

## 测试

```bash
# 全量测试 (1083 passed)
pytest -q --ignore=tests/test_mcp_gateway.py

# 冒烟测试
bash scripts/smoke_test.sh

# 集成测试
bash scripts/integration_test.sh

# 闭环结构检查
python tools/check_closed_loop.py
```

## MCP 集成

在 Claude Code / Cursor / Codex 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 核心特性

| 特性 | 状态 |
|------|------|
| 22 阶段 RunLifecycle 统一状态源 | ✅ |
| 时间感知记忆路由（防遗忘） | ✅ |
| 上下文压缩保护（防降智） | ✅ |
| 真实自我优化闭环（Eval→Regression→Validation→HumanReview→Export） | ✅ |
| 可解释决策轨迹（不含 chain_of_thought） | ✅ |
| Canvas 像素人 17 场景 Dashboard | ✅ |
| best_skill.md 版本化 + Human Review 守卫 | ✅ |
| MCP V5 Gateway + 40+ 事件→阶段映射 | ✅ |

## 版本

- **V8.1**: Phase 1-9 闭环硬化，Canvas 像素人，_generate_skill_patches 真实验证
- **V7.1**: Human Review API + 飞书通知 + best_skill 版本化
- **V7.0**: 物理清理 (progress_model.py, gateway/run_lifecycle.py)
- **V6.3**: HumanReviewQueue, best_skill 自动导出, RAG STUB→真实
- **V6.2**: Dashboard 收敛, V3/V4 MCP 删除, LLM 验证
- **V6.1**: TemporalMemoryBridge, ContextCompressionGuard, RegressionValidationRunner

## 文档

| 文档 | 说明 |
|------|------|
| [CLOSED_LOOP_AUDIT.md](CLOSED_LOOP_AUDIT.md) | 闭环审计 |
| [RUN_LIFECYCLE_SPEC.md](RUN_LIFECYCLE_SPEC.md) | RunLifecycle 规范 |
| [TEMPORAL_MEMORY_SPEC.md](TEMPORAL_MEMORY_SPEC.md) | 时间记忆规范 |
| [CONTEXT_COMPRESSION_GUARD_SPEC.md](CONTEXT_COMPRESSION_GUARD_SPEC.md) | 压缩保护规范 |
| [SELF_IMPROVEMENT_PROOF_SPEC.md](SELF_IMPROVEMENT_PROOF_SPEC.md) | 自我优化规范 |
| [DASHBOARD_OBSERVER_SPEC.md](DASHBOARD_OBSERVER_SPEC.md) | Dashboard 规范 |
| [DEPLOYMENT_AND_TESTING_GUIDE.md](DEPLOYMENT_AND_TESTING_GUIDE.md) | 部署与测试 |

## 项目结构

```
stable_agent/
  runtime/          RunLifecycle (唯一状态源)
  memory/           TemporalMemoryRouter + Bridge
  context/           ContextCompressionGuard
  self_improvement/  ProofLoop + RegressionValidation + HumanReview
  observation/       DecisionTraceBuilder + EventStream
  gateway/           ToolRouter + MCP Gateway
  orchestrator.py    17步编排器
web/
  templates/         Dashboard HTML
  static/             Avatar Canvas, Observer JS, CSS
  server.py          FastAPI + WebSocket
scripts/             部署 + 测试脚本
tools/               check_closed_loop.py, integration_test.py
```
