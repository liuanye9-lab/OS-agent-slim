# StableAgent Cloud — AgentOps + SkillOps SaaS

> **从单机Agent Runtime 升级为 商业化 AgentOps + SkillOps SaaS**

[![Tests](https://img.shields.io/badge/tests-871%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## 一句话定位

**StableAgent Cloud** 是一个可观察、可验证、可回滚的 AgentOps + SkillOps SaaS。

它把每次 Agent 执行变成 trace，把 trace 变成 eval，把失败变成 regression case，把稳定经验变成 skill patch，再通过 validation gate 和 human review，最终导出可审计、可回滚的 best_skill.md。

---

## 为什么需要 StableAgent？

| 问题 | 现状 | StableAgent |
|------|------|-------------|
| 🤖 Agent降智但不知情 | 无自动检测 | Eval自动评分，低于阈值告警 |
| 🔧 改prompt导致退化 | 无回归测试 | Regression suite自动检测 |
| 📊 团队经验无法共享 | 每人独自优化 | Skill Library + workspace共享 |
| 💸 不知道Agent成本 | 无可视化 | Usage counter + token追踪 |
| 🔐 决策不可审计 | 无trace | DecisionTrace完整记录 |
| 🚀 新人接入困难 | 手动配置MCP | 一键生成配置，3分钟接入 |

## 核心闭环

```
Agent执行 → Trace记录 → Eval评分 → BadCase收集
    ↓                                        ↓
Skill Export ← Human Review ← Validation ← Regression Case
```

### 5轮自迭代验证数据

| 轮次 | 综合评分 | 幻觉率 | Token消耗 | 记忆命中 |
|------|---------|--------|----------|---------|
| R1 | 0.55 | 35% | 4800 | 30% |
| R2 | 0.62 | 28% | 4500 | 42% |
| R3 | 0.70 | 20% | 4200 | 55% |
| R4 | 0.78 | 14% | 3800 | 68% |
| R5 | **0.85** | **10%** | **2910** | **82%** |

- 评分提升: **+54%** (0.55 → 0.85)
- 幻觉降低: **-71%** (35% → 10%)
- Token节省: **1890** (5轮累计)

## 快速开始

```bash
# 一键安装
bash install.sh

# 启动服务
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 运行测试
pytest -q
# 871 passed ✅
```

## 接入 Claude Code / Codex

### Claude Code
```json
// .claude/mcp.json
{
  "mcpServers": {
    "stableagent": {
      "type": "http",
      "url": "http://localhost:8000/mcp/v5/mcp"
    }
  }
}
```
然后在 Claude Code 中输入: `/os-agent 你的任务`

### Codex
```json
// .codex/mcp_config.json
{
  "mcp": {
    "stableagent": {
      "url": "http://localhost:8000/mcp/v5/mcp"
    }
  }
}
```
然后在 Codex 中输入: `/os-agent 你的任务`

### 一键接入页面
启动后访问: `http://localhost:8000/connect`

## SaaS 架构

```
Workspace (团队空间)
├── Members
└── Projects
    ├── Agent Profiles
    ├── Runs ← Trace ← Eval
    ├── Skills ← Patches ← Validation ← Review
    └── Regression Cases
```

### SaaS数据模型 (16个实体)

Workspace → Project → AgentRun → TraceEvent →
EvalResult → BadCase → RegressionCase →
Skill → SkillVersion → SkillPatch → ValidationRun →
HumanReview → ApiKey → UsageEvent

## 验收标准 (14/14 ✅)

1. ✅ 可创建 workspace 和 project
2. ✅ run 归属 project
3. ✅ trace event 归属 run
4. ✅ MCP tool call 携带 project_id
5. ✅ 无 project_id 在 SaaS 模式失败
6. ✅ local 模式可用 default project
7. ✅ BadCase 可转 RegressionCase
8. ✅ Skill Patch 不能绕过 Validation Gate
9. ✅ best_skill.md 不能绕过 Human Review
10. ✅ UsageEvent 记录工具调用
11. ✅ API Key 可创建和撤销
12. ✅ Dashboard 按 project 查看
13. ✅ pytest 全部通过 (871/871)
14. ✅ 现有测试不受影响

## 技术栈

- Python 3.13 + FastAPI + WebSocket
- SQLite (SaaS MVP) / PostgreSQL (P2)
- MCP Gateway V5 (JSON-RPC 2.0)
- Vanilla HTML/CSS/JS Dashboard (玻璃拟态)
- 871 tests · 33 modules

## 项目结构

```
stable_agent/
├── models.py              # 核心数据模型
├── storage.py             # SQLite存储
├── gateway/               # MCP Gateway
├── saas/                  # ★ SaaS模块 (新增)
│   ├── models.py          # 16个SaaS dataclass
│   ├── repository.py      # 13张表CRUD
│   ├── service.py         # 业务逻辑
│   ├── usage.py           # 用量计数器
│   ├── permissions.py     # 权限校验
│   ├── api_keys.py        # API Key管理
│   ├── regression_service.py
│   └── skill_review_service.py
├── skill_optimizer/       # Skill优化引擎
├── observation/           # 可观测性
└── eval_and_bad_case.py   # 评测+失败案例
```

## 版本

- **SaaS v1.0** (2026-05-28): 多租户 + Eval闭环 + Validation/HumanReview Gate
- **v6.5**: Dashboard V3 + 一键接入
- **v5.6**: 工程治理 + MCP统一网关

## 开源协议

MIT License

---

*"把Agent管理从玄学变成工程"*
