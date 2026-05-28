# StableAgent OS

> 一个可观察、可验证、可回滚的 Agent 自我迭代系统。

**一句话**：
StableAgent OS 不是普通 AI 工具，而是一个 **Agent 自我迭代运行时**。
它把每次执行变成可追踪的 trace，把 trace 变成 eval，把失败变成 regression case，
把稳定经验变成 skill patch，再通过 validation gate 和 human review，
最终导出可审计、可回滚的 `best_skill.md`。

---

## 它解决什么问题

| 问题 | StableAgent OS 的答案 |
|------|----------------------|
| Agent 遗忘（重复犯错） | MemoryRouter 检索过去记忆，抽取经验注入当前上下文 |
| 上下文膨胀（Token 浪费） | ContextBudgetManager 按预算裁剪，只保留关键信息 |
| 不可观测（不知道 Agent 在做什么） | Trace + DecisionNarrator + Dashboard 实时展示 |
| 自我优化不可感知 | SkillOpt + LearningEvidence + RunInsight 可见化 |
| 玄学优化（改了什么不知道） | Skill Patch → Validation Gate → Human Review → best_skill.md |

---

## 核心闭环（V6-Professional）

```text
Task → Plan → Action → Observation → Trace → Eval
→ Failure Attribution → Reflection → Skill Patch
→ Validation Gate → Human Review → Export best_skill.md
```

| 节点 | 说明 |
|------|------|
| **Task** | MCP tools/call 入口，生成 run_id |
| **Plan** | WorkflowStateMachine + 层级规划（sub_steps） |
| **Action** | 15 个 MCP 工具通过 ToolRouter 路由 |
| **Trace** | EventStream.publish_sync()，每步发布 TraceEvent |
| **Eval** | 三层评测（RuleEval → ComponentEval → 加权），含 failure_attribution |
| **Failure Attribution** | EvaluationResult.failure_attribution: {"failed_stage": "...", "reason": "..."} |
| **Reflection** | BadCaseManager → generate_improvement_rule |
| **Skill Patch** | add/delete/replace diff → skills/candidates/ |
| **Validation Gate** | old_score vs new_score → passed/rejected |
| **Human Review** | SkillExporter.export() 强制 human_reviewed=True |
| **Export** | skills/best_skill.md（含版本号，可回滚） |

---

## 系统架构

```text
stable_agent/
├── gateway/           # MCP Gateway (JSON-RPC 2.0, 15 tools)
├── observation/       # Trace/Eval/RunStore/DashboardSync/ProgressModel
├── explanation/       # DecisionNarrator (22 events, 中英双语)
├── skill_optimizer/   # SkillOpt + ValidationGate + SkillExporter
├── intent/            # UserIntentProfile + IntentAlignmentEvaluator
├── evals/             # RegressionSuite + RubricJudge
├── quickstart/        # 一键接入 Claude Code / Codex / Cursor
├── orchestrator.py    # 主控
├── workflow_state_machine.py
├── context_decision_engine.py
├── context_budget_manager.py
├── memory_router.py
├── rag_context_pack.py
└── models.py          # 30+ 数据类

web/
├── templates/         # dashboard_v3.html (iOS 玻璃拟态)
├── static/            # liquid_glass.css, dashboard_v3.js, etc.
└── server.py          # FastAPI + WebSocket

skills/
├── best_skill.md      # 当前最优技能
├── candidates/        # 候选 patch（验证中）
├── rejected/          # 被拒绝的 patch
└── skill_versions/    # 版本历史

data/
└── regression_cases.jsonl  # BadCase → Regression Case
```

---

## MCP 接入（15 工具）

```json
{
  "mcpServers": {
    "stableagent-os": {
      "transport": "streamable_http",
      "url": "http://127.0.0.1:8000/mcp/v5/mcp"
    }
  }
}
```

可用工具：`stableagent.task.os_agent`, `stableagent.context.build`, `stableagent.memory.retrieve`,
`stableagent.rag.retrieve`, `stableagent.eval.evaluate`, `stableagent.skillopt.run_epoch`,
`stableagent.skillopt.export_best`, `stableagent.approval.respond`, 等共 15 个。

---

## Dashboard 可观察性

| 区域 | 展示内容 |
|------|----------|
| 状态卡片 | 当前阶段 + 做什么 + 进度% |
| 决策卡片 | 为什么这样做 + 丢弃了什么 |
| 像素人 | 14 语义场景（后端 avatar_state 驱动） |
| 学习面板 | 是否触发学习 + diff + rollout count |
| RunInsight | 质量/意图/Token ROI/记忆命中率 |
| 反馈区 | 7 种反馈 → SkillOpt 管道 |

---

## SkillOpt 如何避免玄学

```text
不是：模型自己判断"我觉得改一下会更好" → 直接覆盖 best_skill.md

而是：
1. Rollout → 收集执行数据
2. Failure Analysis → 识别失败模式
3. Patch Proposal → add/delete/replace diff
4. Validation Gate → old_score vs new_score，基于 regression cases
5. Human Review → 必须人工确认
6. Export → skills/best_skill.md（含版本号，可回滚）

只有满足 passed=true AND human_reviewed=true AND new_score > old_score 时才允许导出。
```

---

## 安全边界

- **高风险工具**：approval 机制（需人工确认）
- **Forbidden 工具**：SecurityPolicy 直接拒绝
- **Sandbox**：git_diff_checkpoint 支持回滚
- **安全审查**：禁止 eval/exec/__import__

---

## 如何运行

```bash
# 安装
pip install -e .

# 启动
uvicorn web.server:app --host 127.0.0.1 --port 8000

# Dashboard
open http://localhost:8000/dashboard/v3

# 一键接入
open http://localhost:8000/connect

# 在 Codex 中输入
/os-agent 分析项目架构
```

---

## 如何测试

```bash
pytest tests/ -q --ignore=tests/test_mcp_gateway.py
# 792 passed, 0 failed
```

---

## 面试讲述版本

```
我不是做了一个普通 AI 工具。
我做的是一个 Agent 自我迭代运行时。

它把每次执行变成可追踪的 trace，
把 trace 变成 eval（不只是打分，而是结构化归因：哪一步失败了、为什么），
把失败变成 regression case（可复测的基准案例），
把稳定经验变成 skill patch（add/delete/replace diff），
再通过 validation gate（新旧实力对比）和 human review（必须人工确认），
最终导出可审计、可回滚的 best_skill.md。

这个系统的架构对标了 Agent-S（经验增强规划）、OpenHands（sandbox+WebSocket）、
AutoGen Studio（可视化调试）、Reflexion（失败反思）、Voyager（技能库积累），
并通过 MCP 协议对外暴露 15 个工具，可以被 Claude Code / Codex / Cursor 直接调用。

每次任务执行，Dashboard 上能实时看到 Agent 在做什么、为什么这么做、
执行到百分之多少、是否触发了学习——全部由后端 event stream 驱动，不是前端假数据。

792 个测试，0 回归，闭环完整度 90%。
```
