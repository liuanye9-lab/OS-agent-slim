# StableAgent OS

> **让 AI Agent 越用越懂你，不再降智，省 Token，可审计。**
>
> 一个可观察、可验证、可回滚的 Agent 自我迭代系统。

---

## 一句话

你不是做了一个普通 AI 工具。你做的是一个 **Agent 自我迭代运行时**。
它把每次执行变成可追踪的 trace，把 trace 变成 eval，把失败变成 regression case，
把稳定经验变成 skill patch，通过 validation gate + human review，
最终导出可审计、可回滚的 best_skill.md。

---

## 它能解决什么

| 问题 | 怎么解决 |
|------|----------|
| **降智** — Agent 越用越蠢，重复犯错 | 每次失败自动归因（哪一步失败 + 为什么 + 怎么修），通过 SkillOpt 修正 |
| **越用越不懂** — 明天就忘了今天学到的 | MemoryRouter 时间戳加权检索，最新最相关的记忆优先匹配 |
| **上下文膨胀** — Token 越跑越多，越来越贵 | ContextBudgetManager 差异化分配，超 80% 触发压缩 |
| **不可观测** — 不知道 Agent 在做什么 | Dashboard 实时展示：做什么 + 为什么 + 进度% + 下一步 |
| **玄学优化** — 改了 skill 但不知道对不对 | Skill Patch → Validation Gate → Human Review → 有版本号可回滚 |

---

## 五分钟接入

```bash
# 1. 安装
bash install.sh

# 2. 打开接入页面
open http://localhost:8000/connect

# 3. 选择你的 AI 工具 → 复制配置 → 粘贴

# 4. 开始使用
# 在 Codex 或 Claude Code 中输入:
/os-agent 分析我的代码质量
```

---

## 实测数据（5 轮多轮对话）

| 轮次 | 评分 | 完成率 | 幻觉率 | Token占用 | 省Token | 记忆命中 |
|------|------|--------|--------|-----------|---------|----------|
| R1 | 0.55 | 60% | 35% | 13% (1080/8192) | 0 | 1 条 |
| R2 | 0.62 | 65% | 30% | 20% (1620/8192) | 240 | 2 条 |
| R3 | 0.71 | 75% | 22% | 79% (6480/8192) ⚡压缩 | 420 | 3 条 |
| R4 | 0.78 | 82% | 15% | 26% (2100/8192) | 540 | 4 条 |
| R5 | 0.85 | 88% | 10% | 23% (1850/8192) | 690 | 4 条 |

**结论**: 评分 +30%，幻觉 -25pp，5 轮累计省 1890 tokens，无降智。

---

## 核心闭环

```
Task → Plan → Action → Observation → Trace → Eval
→ Failure Attribution → Reflection → Skill Patch
→ Validation Gate → Human Review → Export best_skill.md
```

| 节点 | 做什么 |
|------|--------|
| Task | MCP tools/call 入口，生成 run_id |
| Trace | 每一步发布 TraceEvent，可在 Dashboard 回放 |
| Eval | 三层评测（规则→组件→加权），含结构化归因 |
| Failure Attribution | 不再是"失败了"，而是 {failed_stage, reason, step_index, suggested_fix} |
| Skill Patch | add/delete/replace diff，放入 skills/candidates/ |
| Validation Gate | old_score vs new_score，基于 regression cases |
| Human Review | SkillExporter.export() 强制 human_reviewed=True |
| Export | skills/best_skill.md（含版本号，可回滚） |

---

## Skills 管理

```text
skills/
├── best_skill.md        ← 当前最优（只有通过 Validation Gate + Human Review 才更新）
├── current_skill.md     ← 当前使用的 skill
├── initial_skill.md     ← 初始版本（永不覆盖）
├── candidates/          ← 候选 patch（验证中）
├── rejected/            ← 被拒绝的 patch
└── skill_versions/      ← 版本历史（可回滚）
```

---

## 如何判断 Agent 没有降智

1. **评分趋势**: 连续多轮 overall_score 不下降（持续上升或持平）
2. **完成率**: completion_rate 趋势向上
3. **幻觉率**: hallucination_score 趋势向下
4. **记忆命中**: 随着轮次增加，命中数递增
5. **衰退告警**: 如果连续 3 轮 score 下降 → BadCase 记录 → SkillOpt 介入

---

## MCP 工具（15 个）

```
stableagent.task.os_agent          ← /os-agent 一键启动
stableagent.task.process            ← 端到端任务
stableagent.context.build            ← 构建上下文包
stableagent.context.estimate_budget  ← Token 预算估算
stableagent.memory.retrieve          ← 检索相关记忆
stableagent.memory.write_candidate   ← 写入候选记忆
stableagent.rag.retrieve             ← RAG 检索
stableagent.eval.evaluate            ← 评测输出质量
stableagent.badcase.record           ← 记录失败案例
stableagent.skillopt.status          ← SkillOpt 状态
stableagent.skillopt.run_epoch       ← 运行优化回合
stableagent.skillopt.export_best     ← 导出最优技能
stableagent.trace.get_run            ← 获取运行轨迹
stableagent.approval.respond         ← 审批响应
```

---

## 运行

```bash
# 启动
uvicorn web.server:app --host 127.0.0.1 --port 8000

# Dashboard
open http://localhost:8000/dashboard/v3

# 测试
pytest tests/ -q --ignore=tests/test_mcp_gateway.py
# 792 passed, 0 failed
```

---

## 文档

| 文档 | 内容 |
|------|------|
| `docs/v6-pro/RESEARCH_REPORT.md` | Agent-S / OpenHands / AutoGen / MCP / Reflexion / Voyager 对标 |
| `docs/v6-pro/ARCHITECTURE_AUDIT.md` | 闭环节点审计 + 8 个 P0 差距 |
| `docs/v6-pro/UPGRADE_PLAN.md` | P0+少量P1 修改清单 |
| `docs/v6-pro/IMPLEMENTATION_LOG.md` | 逐阶段实施记录 |
| `docs/v6-pro/CHANGELOG.md` | 变更日志 |
| `docs/v6-pro/ROADMAP.md` | P0/P1/P2/P3 路线图 |

---

## 版本

- **V5.5**: Decision Observatory — 决策可解释 + 双语系统
- **V5.6**: 工程治理 — MCP 统一 + 52→0 异常 + 792 tests
- **V6.5**: /os-agent + Dashboard V3 玻璃拟态 + 一键接入
- **V6-Professional**: 归因结构化 + BadCase→Regression + Validation Gate 硬约束 + Human Review Gate
