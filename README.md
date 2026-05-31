<p align="center">
  <img src="https://img.shields.io/badge/tests-1274_passed-brightgreen?style=for-the-badge" alt="1274 Tests">
  <img src="https://img.shields.io/badge/closed_loop-30%2F30-22c55e?style=for-the-badge" alt="30/30 Closed Loop">
  <img src="https://img.shields.io/badge/E2E-6%2F6_REAL_LLM-ff6b35?style=for-the-badge" alt="Real LLM E2E">
  <img src="https://img.shields.io/badge/python-3.13-blue?style=for-the-badge" alt="Python 3.13">
  <img src="https://img.shields.io/badge/MCP-55_tools-7c3aed?style=for-the-badge" alt="MCP">
  <img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="MIT">
</p>

<h1 align="center">StableAgent OS</h1>

<p align="center">
  <strong>AI Agent 防降智操作系统</strong><br>
  <sub>100% 闭环自我优化 · 解释型可视化面板 · 真实 LLM E2E 验证</sub>
</p>

---

## 为什么需要 StableAgent？

AI Agent 在长任务中会**降智**：遗忘关键约束、偏离原始目标、产生幻觉。StableAgent 是一个 MCP 协议的"外脑"，接入 Claude Code / Cursor / Codex，通过**时间感知记忆 + 上下文保护 + 真闭环自我优化**来防止降智。

```
                    ┌─────────────────────────────────────────────┐
                    │         你和 AI 之间的"防降智层"              │
  Claude Code  ────→│  ✅ 记住你3小时前说的约束                      │
  Cursor      ────→│  ✅ 压缩上下文时保护核心目标                     │────→ 稳定输出
  Codex       ────→│  ✅ 失败经验自动转化为规则                      │
                    │  ✅ 新规则必须人工审批才能生效                   │
                    └─────────────────────────────────────────────┘
```

## 事件链 — 从 MCP 到 Dashboard 全链路打通

StableAgent 最核心的承诺：**每一个事件从产生到展示，全链路可追溯**。

```
  MCP tools/call
       │
       ▼
  os_agent 执行
       │
       ├── _emit() ──→ RunStore.append_event()    ← 写入
       │                    │
       │                    ▼
       │              /api/runs/{id}/events        ← 读取
       │                    │
       │                    ▼
       │              Dashboard Observer            ← 回放 + 实时
       │               (API 历史 + WebSocket)
       │
       └── 结果返回 MCP (event_api_ok=True)
```

**V10 硬性约束**：如果 `/api/runs/{run_id}/events` 为空，测试直接 FAIL。不再允许任何 fallback。

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          MCP Gateway (V5)                           │
│  28 个标准工具 · JSON-RPC 2.0 · WebSocket 实时推送                    │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────┐
│                   UnifiedToolRegistry                               │
│  stableagent.task.os_agent — 13 必需事件 + RunStore 回读验证          │
│  ├── _emit() → EventStream + RunStore (双写)                        │
│  ├── event_api_ok (RunStore 回读)                                   │
│  ├── api_event_count (API 实际事件数)                                │
│  └── dashboard_replay_ok (回放一致性)                                │
├──────────────────────────────────────────────────────────────────────┤
│                     RunLifecycle (22 阶段)                           │
│  唯一状态源 · progress_pct / status_text_zh / avatar_state / scene   │
├──────────────────────────────────────────────────────────────────────┤
│  TemporalMemoryRouter        │  ContextCompressionGuard              │
│  按时间戳召回关键约束          │  6 层保护 · 防丢核心目标               │
├──────────────────────────────────────────────────────────────────────┤
│                     WorkflowEngine (17 步编排)                       │
│  plan → retrieve → compress → execute → eval → improve → complete   │
├──────────────────────────────────────────────────────────────────────┤
│                   SelfImprovementProofLoop                           │
│  Eval → FailureAttribution → RegressionCase → MemoryCandidate        │
│  → SkillPatch → ValidationGate → HumanReview → best_skill.md        │
│                                                                      │
│  ⚠️  防火墙:                                                          │
│  • validation_failed → 不进入 HumanReview                             │
│  • dry_run_learning=True → 不导出 best_skill.md                       │
│  • force_validation_passed → 强制 HumanReview (测试用)                 │
└──────────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────┐
│                    Observation Layer                                  │
│  ├── RunStore (内存, 单例)                                           │
│  │   ├── create_run() / mark_completed()                            │
│  │   ├── append_event() / get_events()                              │
│  │   └── get_run_status()                                           │
│  ├── EventStream (同步 + 异步)                                       │
│  ├── DecisionTraceBuilder (可解释决策)                                │
│  └── HumanReviewQueue (审批队列)                                     │
├──────────────────────────────────────────────────────────────────────┤
│                    Web Layer (FastAPI)                                │
│  ├── /mcp                 — MCP JSON-RPC                             │
│  ├── /api/runs/{id}/events — 结构化 {run_id, event_count, events}    │
│  ├── /observe/{id}        — Dashboard Observer (302 from /runs/{id}) │
│  └── /ws/runs/{id}        — WebSocket 实时事件                       │
├──────────────────────────────────────────────────────────────────────┤
│                    Dashboard Observer                                 │
│  ├── API 历史回放 (先 fetch /api/runs/{id}/events)                   │
│  ├── WebSocket 实时补充                                              │
│  ├── API/WebSocket/Replay 状态显示                                    │
│  ├── 像素人 Canvas 17 场景 (avatar_state 驱动)                       │
│  └── 无事件 → "同步异常" (不允许静默空白)                              │
└──────────────────────────────────────────────────────────────────────┘
```

## 自我优化闭环

StableAgent 的自我优化是**真闭环** — 每一步都有结构检查，每一个产出都有审批门槛：

```
  任务执行失败
       │
       ▼
  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
  │ Eval 评分    │────→│ FailureAttribution│────→│ RegressionCase  │
  │ eval.completed│     │ 失败归因分析      │     │ regression.     │
  └──────────────┘     └──────────────────┘     │ generated       │
                                                  └────────┬────────┘
                                                           │
                      ┌────────────────────────────────────┘
                      │
                      ▼
           ┌──────────────────┐     ┌──────────────────┐
           │ MemoryCandidate  │────→│ SkillPatchCandidate│
           │ memory.update.   │     │ skill.patch.      │
           │ candidate        │     │ proposed          │
           └──────────────────┘     └─────────┬────────┘
                                              │
                    ┌─────────────────────────┘
                    │
                    ▼
           ┌──────────────────┐     YES    ┌──────────────────┐
           │ ValidationGate   │────────────→│ HumanReview      │
           │ validation.      │             │ human_review.    │
           │ checked          │             │ required         │
           └────────┬─────────┘             └────────┬─────────┘
                    │ NO                             │ 审批通过
                    ▼                                ▼
              不进入审批                    ┌──────────────────┐
              (validation_failed)          │ best_skill.md    │
                                           │ 版本化导出        │
                                           └──────────────────┘
```

**安全机制**：
- `dry_run_learning=True` → 只模拟不导出，阻止 best_skill.md 写入
- `validation_passed=False` → 直接拒绝，不进入 HumanReview
- 所有 patch 必须经过 `RegressionValidationRunner` 混合评分 (规则 70% + LLM 30%)

## 闭环验证 (30/30 结构检查)

| 类别 | 检查项 | 版本 |
|------|--------|------|
| **事件链** | _emit → RunStore 写入 | V9.0 |
| | RunStore 事件可被 API 读取 | V9.2 |
| | REQUIRED_NORMAL_EVENTS 13 项交叉检查 | V9.2 |
| | RunStore 回读 → event_api_ok | V10 |
| | event_sync_ok 依赖 event_api_ok | V10 |
| **集成测试** | 禁止 emitted_events fallback | V10 |
| | 必须从 /api/runs 验证事件 | V10 |
| | check_dashboard_replay_api | V10 |
| | WARN+SKIP → assert_true fail-fast | V9.2 |
| **Dashboard** | 先 API 历史回放再 WebSocket | V9.2 |
| | API 返回结构化 {event_count, events} | V10 |
| | 无事件显示同步异常 | V9.2 |
| **安全** | .env 在 .gitignore | V10 |
| | secret_masker.py 存在 | V10 |
| | real_llm_e2e_test 不打印 key | V10 |
| **自我优化** | proof_loop 存在 | V8.0 |
| | ValidationGate 存在 | V8.1 |
| | HumanReview 存在 | V8.1 |
| | best_skill 版本化导出 | V7.1 |
| | force_validation_passed 控制 | V9.1 |
| | dry_run 阻止导出 | V9.1 |
| | validation_failed 不进 HumanReview | V9.1 |
| | emitted_events 列表返回 | V9.1 |
| | best_skill_exported 在 si_report | V9.1 |
| | rag.retrieved 必需事件 | V9.1 |
| | next_step_zh 必需字段 | V9.2 |
| | except Exception: pass 零容忍 | V9.2 |
| | os_agent run 注册 RunStore | V9.2 |
| | 404 未知 run | V9.2 |

## 必需事件链

### 正常路径 (13 项)

```
task.received → intent.parsed → context.budgeted → temporal_memory.retrieved →
rag.retrieved → context.compression_guard.checked → context.built →
workflow.plan.created → workflow.step.started → workflow.step.completed →
eval.completed → self_improvement.checked → task.completed
```

### 失败学习路径 (额外 4 项)

```
regression.generated → memory.update.candidate → skill.patch.proposed → validation.checked
```

## Key 安全

```
.env (本地, 不提交)           .env.example (提交, 无真实 key)
  │                              │
  ▼                              ▼
环境变量读取                     模板示例
  │                              │
  ├── OPENAI_API_KEY             ├── OPENAI_API_KEY=
  ├── OPENAI_BASE_URL            ├── OPENAI_BASE_URL=
  └── STABLE_AGENT_*             └── STABLE_AGENT_*
                                 
  日志脱敏: mask_secret("sk-219efad867674c3a8575a82aa7b2e175")
  → "sk-2***e175"
```

**安全规则**：
- `.env` 在 `.gitignore` 中，永不被提交
- `secret_masker.py` 提供 `mask_secret` / `mask_text` / `is_secret_leaked`
- `llm_factory.py` 日志中 key 自动脱敏
- `real_llm_e2e_test.py` 报告中 key 自动脱敏
- 无 key 时测试走 mock mode

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/liuanye9-lab/OS-Agent.git
cd OS-Agent

# 2. 配置 (可选: 真实 LLM)
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行测试
pytest tests/ -q --ignore=tests/test_mcp_gateway.py

# 5. 启动
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 6. 访问
#   Dashboard: http://127.0.0.1:8000
#   MCP:       http://127.0.0.1:8000/mcp
#   API Docs:  http://127.0.0.1:8000/docs
```

## MCP 集成

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### 核心工具

| 工具 | 说明 |
|------|------|
| `stableagent.task.os_agent` | 主入口: 多阶段编排 + 事件链 + 自我优化 |
| `stableagent.task.quickstart` | 快速启动: 简化参数 |
| `stableagent.memory.query` | 查询时间感知记忆 |
| `stableagent.skill.list` | 列出已验证技能 |
| `stableagent.run.list` | 列出运行历史 |
| `stableagent.run.observe` | 观察运行详情 |

## 测试体系

| 测试 | 命令 | 结果 |
|------|------|------|
| **单元测试** | `pytest tests/ -q --ignore=tests/test_mcp_gateway.py` | **1108 passed**, 0 failures |
| **闭环结构检查** | `python tools/check_closed_loop.py` | **30/30 PASS** |
| **集成测试** | `bash scripts/integration_test.sh` | 三条路径 fail-fast |
| **真实 LLM E2E** | `bash scripts/real_llm_e2e_test.sh` | **6/6 PASS** (阿里云 qwen-plus) |
| **冒烟测试** | `bash scripts/smoke_test.sh` | MCP 连通性 |

### 集成测试三条路径

1. **Normal Path** — 完整 13 事件链，`event_api_ok=True`
2. **Failure-Val-Fail** — 失败学习 + `validation_passed=False` → 不进 HumanReview
3. **Failure-Val-Pass** — 失败学习 + `validation_passed=True` → 进入 HumanReview, `dry_run` 阻止导出

## 项目规模

| 指标 | 数值 |
|------|------|
| Python 代码 | ~55K 行 |
| JavaScript 代码 | ~271K 行 |
| HTML 模板 | ~2.4K 行 |
| Python 模块 | 239 文件 |
| 测试用例 | 1108 个 |
| MCP 工具 | 28 个 |
| 必需事件类型 | 13 (正常) + 4 (失败) |
| 闭环结构检查 | 30 项 |
| RunLifecycle 阶段 | 22 个 |
| 核心子模块 | 15 个 |

## 核心模块

```
stable_agent/
├── gateway/              # MCP 入口 + 工具注册 + 路由
│   ├── mcp_gateway.py    # JSON-RPC 2.0 服务
│   ├── unified_tool_registry.py  # os_agent 主执行 + 事件链
│   └── tool_router.py    # RunStore + EventStream
├── runtime/              # 运行时生命周期
│   └── run_lifecycle.py  # 22 阶段状态机
├── memory/               # 时间感知记忆
│   └── temporal_memory_router.py  # 按时间戳召回
├── context/              # 上下文保护
│   └── context_compression_guard.py  # 6 层保护
├── self_improvement/     # 自我优化闭环
│   └── proof_loop.py     # Eval→Failure→Regression→Validation→HumanReview→Export
├── observation/          # 观测层
│   ├── run_store.py      # 内存存储 (单例)
│   ├── event_stream.py   # 事件流
│   └── decision_trace_builder.py  # 可解释决策
├── security/             # 安全
│   └── secret_masker.py  # 密钥脱敏
├── evals/                # 评估
├── intent/               # 意图解析
├── skill_optimizer/      # 技能优化
├── approval/             # 审批
├── db/                   # 数据库
├── mcp/                  # MCP 工具
└── saas/                 # SaaS 集成
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.13, FastAPI, WebSocket |
| 前端 | Vanilla HTML/CSS/JS (零框架依赖) |
| UI 风格 | 玻璃拟态 + Canvas 像素人 |
| 架构 | 分层 + EventBus 事件驱动 |
| 测试 | pytest (1108 tests) |
| 持久化 | SQLite (sqlite3 标准库) |
| Token 估算 | tiktoken 优先, fallback 启发式 |
| LLM 集成 | OpenAI Compatible API (阿里云 qwen-plus 验证) |
| 协议 | MCP (JSON-RPC 2.0) |

## 文档

| 文档 | 说明 |
|------|------|
| [MANUAL_TEST_GUIDE.md](MANUAL_TEST_GUIDE.md) | 手动验证指南 (V10, 14 节) |
| [CLOSED_LOOP_AUDIT.md](CLOSED_LOOP_AUDIT.md) | 闭环审计报告 |
| [RUN_LIFECYCLE_SPEC.md](RUN_LIFECYCLE_SPEC.md) | RunLifecycle 规范 |
| [TEMPORAL_MEMORY_SPEC.md](TEMPORAL_MEMORY_SPEC.md) | 时间记忆规范 |
| [CONTEXT_COMPRESSION_GUARD_SPEC.md](CONTEXT_COMPRESSION_GUARD_SPEC.md) | 压缩保护规范 |
| [SELF_IMPROVEMENT_PROOF_SPEC.md](SELF_IMPROVEMENT_PROOF_SPEC.md) | 自我优化规范 |
| [DASHBOARD_OBSERVER_SPEC.md](DASHBOARD_OBSERVER_SPEC.md) | Dashboard 规范 |
| [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) | 实施日志 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [V11_UPGRADE_REPORT.md](docs/V11_UPGRADE_REPORT.md) | V11 升级报告 |
| [DEVELOPER_QUICKSTART.md](docs/DEVELOPER_QUICKSTART.md) | 快速开始 |

## 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|---------|
| **V11** | 2026-05-31 | Agent Capsule: 胶囊管理 + 记忆生命周期 + 语义理解 + Token 预算 + 模型画像 + 个人评测 + 反馈闭环 + CLI, 1274 tests, 55 MCP tools |
| **V10** | 2026-05-31 | 100% 闭环: 禁止 emitted_events fallback, event_api_ok, dashboard_replay_ok, 真实 LLM E2E (阿里云), key 安全脱敏, 30/30 checks |
| V9.2 | 2026-05-31 | 事件链硬化: _tool_router 注入, REQUIRED_NORMAL_EVENTS 13项, fail-fast, 404 未知 run |
| V9.1 | 2026-05-31 | Validation Gate: force_validation_passed, dry_run 阻止导出, 21/21 checks |
| V9.0 | 2026-05-30 | 闭环硬验收: _emit→RunStore 打通, event_sync_ok 交叉检查 |
| V8.1 | 2026-05-30 | 真闭环自我优化 + Dashboard Observer 完整同步 |
| V7.1 | 2026-05-30 | HumanReview API + 飞书通知 + best_skill 版本化 |
| V7.0 | 2026-05-30 | 物理清理 (progress_model, gateway/run_lifecycle) |
| V6.3 | 2026-05-30 | HumanReviewQueue, best_skill 自动导出, RAG STUB→真实 |

## GitHub

- **仓库**: [github.com/liuanye9-lab/OS-Agent](https://github.com/liuanye9-lab/OS-Agent)
- **License**: MIT
