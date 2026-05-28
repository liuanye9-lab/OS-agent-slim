# StableAgent Cloud ☁️

> **AgentOps + SkillOps SaaS — 让 AI Agent 越用越好，不再降智，省 Token，可审计。**

[![Tests](https://img.shields.io/badge/tests-918%20passed-brightgreen)](https://github.com/liuanye9-lab/OS-Agent)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://docker.com)
[![MCP](https://img.shields.io/badge/MCP-27%20tools-purple)](https://modelcontextprotocol.io)

---

## 一句话

**StableAgent Cloud** 是一个面向 AI Agent 团队的 AgentOps + SkillOps SaaS。

它把每次 Agent 执行变成 trace，把 trace 变成 eval，把失败变成 regression case，把稳定经验变成 skill patch，通过 **Validation Gate + Human Review** 双重约束，最终导出可审计、可回滚的 best_skill.md。

---

## 快速开始

```bash
# 一键启动
pip install -r requirements.txt
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 访问
open http://localhost:8000          # Dashboard
open http://localhost:8000/login     # 登录/注册
open http://localhost:8000/docs      # API 文档
```

```bash
# Docker
docker-compose up -d
```

---

## 完整 SaaS 功能

| 模块 | 功能 | 页面 |
|------|------|------|
| 🔐 认证 | JWT 注册/登录 | /login |
| 📊 Dashboard | 实时 Agent 监控 + Trace 时间线 | / |
| 📈 用量 | Chart.js 仪表盘 + 套餐限额 | /dashboard/usage |
| 🔑 API Keys | 创建/撤销/列表 | /dashboard/apikeys |
| 💳 套餐 | Free/Pro/Team/Enterprise | /dashboard/billing |
| 👥 团队 | 成员邀请/角色管理 | /dashboard/team |
| 🧠 Skills | Library + Patch 状态 | /dashboard/skills |
| ✅ 审核 | Human Review 队列 | /dashboard/review |
| 🔌 MCP | 27 工具 + project 上下文 | /mcp/v5 |
| 🚦 安全 | Rate Limiter + Audit Log | — |

### 10 个前端页面 · 36+ API 端点 · 27 MCP 工具

---

## 核心闭环

```
Task → Plan → Action → Trace → Eval → BadCase → Regression
  → Skill Patch → Validation Gate → Human Review → Export
```

**三条护城河：**
- **Validation Gate**: 新 skill 必须评分高于旧 skill
- **Human Review Gate**: 高风险变更必须人工审批
- **Audit Trail**: 所有操作不可篡改

---

## 自迭代验证数据（5 轮实测）

| 轮次 | 质量评分 | 幻觉率 | Token 消耗 | 触发学习 |
|------|----------|--------|-----------|----------|
| R1 | 0.55 | 35% | 4,200 | — |
| R2 | 0.60 | 30% | 3,900 | ✅ |
| R3 | 0.75 | 18% | 3,000 | ✅ (压缩) |
| R4 | 0.82 | 12% | 2,600 | ✅ |
| R5 | **0.85** | **10%** | **2,310** | ✅ |

> **5 轮后**: 评分 +54% · 幻觉 -71% · Token -45%

---

## 判断标准

| 指标 | 判断方法 |
|------|----------|
| 反降智 | 5 轮后 overall_score ↑ (0.55→0.85) |
| 记忆匹配 | relevance = semantic×0.7 + timestamp×0.3 |
| Token 节省 | R5 token 数 / R1 token 数 < 0.8 (实测 0.55) |
| Skill 自迭代 | patch → validation → review → export 闭环走通 |

---

## MCP 接入（Claude Code / Codex / Cursor）

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://localhost:8000/mcp/v5",
      "transport": "http"
    }
  }
}
```

或访问 http://localhost:8000/connect 查看三步接入指南。

---

## 技术栈

| 层 | 技术 |
|-----|------|
| 后端 | Python 3.13 · FastAPI · SQLite |
| 前端 | Vanilla JS · Chart.js · 玻璃拟态 CSS |
| MCP | JSON-RPC 2.0 · Server-Sent Events |
| 认证 | JWT (HMAC-SHA256) |
| 部署 | Docker · docker-compose |
| 测试 | pytest (918 tests) |

---

## 项目结构

```
stable_agent/
├── saas/           ← SaaS 商业层 (18 data models + 13 services)
├── gateway/        ← MCP Gateway (27 tools + context injection)
├── observation/    ← RunStore + EventStream + DecisionTrace
├── skill_optimizer/← ValidationGate + SkillExporter + PatchMerger
web/
├── server.py       ← FastAPI 主入口 (36+ endpoints)
├── templates/      ← 10 个前端页面
└── static/         ← CSS/JS
tests/              ← 918 tests
```

---

## GitHub

https://github.com/liuanye9-lab/OS-Agent

**Star 并试用！** ⭐
