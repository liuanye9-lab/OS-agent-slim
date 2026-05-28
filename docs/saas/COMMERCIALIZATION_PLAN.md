# COMMERCIALIZATION_PLAN.md

## 1. 商业定位

StableAgent Cloud 是一个面向 AI Agent 团队的 **AgentOps + SkillOps SaaS**。

> 不是 LLM 可观测性工具，而是让 Agent 越用越好的运维平台。

## 2. 目标客户

| 客户类型 | 痛点 | 付费意愿 |
|----------|------|----------|
| AI coding 用户 | Agent 降智、遗忘、幻觉 | 低-中 |
| AI 产品团队 | 无法评估 Agent 稳定性 | 中 |
| Agent 开发团队 | 缺乏 Skill 管理 | 中-高 |
| 企业 AI 自动化 | 合规审计需求 | 高 |
| AI 咨询团队 | 需要交付可验证成果 | 高 |

## 3. 付费痛点

1. **"Agent 越用越笨"** → 记忆污染、上下文爆炸
2. **"不知道改了什么"** → Skill 变更无审计
3. **"没法证明变好了"** → 缺少可量化评测
4. **"不敢上线"** → 缺少安全审批流程
5. **"Token 烧钱"** → 无成本控制

## 4. 核心付费功能

| 功能 | Free | Pro | Team | Enterprise |
|------|------|-----|------|------------|
| Agent 执行记录 | ✓ | ✓ | ✓ | ✓ |
| Decision Trace | ✓ | ✓ | ✓ | ✓ |
| Eval 评测 | - | ✓ | ✓ | ✓ |
| BadCase → Regression | - | ✓ | ✓ | ✓ |
| Skill Library | ✓ | ✓ | ✓ | ✓ |
| Skill Validation | - | ✓ | ✓ | ✓ |
| Human Review | - | - | ✓ | ✓ |
| API Key | - | - | ✓ | ✓ |
| Audit Log | - | - | ✓ | ✓ |
| SSO | - | - | - | ✓ |
| 私有部署 | - | - | - | ✓ |

## 5. Free / Pro / Team / Enterprise

### Free
- 1 workspace, 1 project
- 100 runs/month
- 7天 trace 保留
- 本地 MCP 接入
- 基础 Dashboard

### Pro ($29/month)
- 3 projects
- 2,000 runs/month
- 30天 trace 保留
- Skill Validation
- Export Report
- Regression Suite

### Team ($99/month)
- 10 projects
- 20,000 runs/month
- 90天 trace 保留
- Human Review
- API Key 管理
- Audit Log
- 多成员协作

### Enterprise (定制)
- 无限制 projects/runs
- 365天 trace 保留
- SSO + RBAC
- 私有部署
- 专属安全策略
- Priority Support

## 6. 使用量计费维度

| 维度 | 单位 | 计费方式 |
|------|------|----------|
| Run 次数 | count | 月度限额 |
| Token 消耗 | token | 套餐内包含，超额按量 |
| Project 数量 | count | 套餐内限定 |
| 成员数量 | count | 套餐内限定 |
| Trace 保留 | 天 | 套餐内限定 |
| API Key 数量 | count | 套餐内限定 |

## 7. 竞品对标

| 产品 | 定位 | 差异化 |
|------|------|--------|
| Langfuse | LLM Tracing | 我们不只 Trace，还做 Skill 闭环 |
| Arize Phoenix | LLM Observability | 我们关注 Agent 特殊性（降智/遗忘） |
| Promptfoo | Prompt Testing | 我们做全链路 Eval + Regression |
| Braintrust | LLM Evaluation | 我们增加 Skill 审批 + 导出 |
| OpenHands | Agent 引擎 | 我们是 Agent 的运维平台 |

## 8. 差异化卖点

**核心闭环**：
```
Run → Trace → Eval → BadCase → Regression → Skill Patch → Validation → Human Review → Export
```

竞品最多做到 Trace → Score → Feedback，StableAgent 做到全链路闭环。

**三条护城河**：
1. **Validation Gate**: Skill 变更必须量化验证
2. **Human Review Gate**: 高风险变更必须人工审批
3. **Audit Trail**: 所有操作不可篡改

## 9. Go-to-market 建议

1. **Claude Code / Codex 社区**: 提供免费接入，积累用户
2. **GitHub Stars 驱动**: 开源核心，SaaS 增值
3. **内容营销**: "为什么你的 Agent 越用越笨" 系列
4. **企业试点**: 找 3-5 个 AI 团队免费试用 Team 版
5. **MCP 生态**: 作为 MCP Server 分发

## 10. 面试讲述版本

> "StableAgent Cloud 解决的是 AI Agent 领域最被低估的问题：Agent 不是调用一次就完事了，它会遗忘、会跑偏、会降智。我们做的不是又一个 LLM 可观测性工具，而是 Agent 全生命周期的运维平台。
>
> 你把 Agent 接入 StableAgent 后，每次执行都变成可追溯的 trace，失败自动转成 regression case，成功经验沉淀为可审批、可验证、可回滚的 skill。团队可以看到 Agent 到底在做什么、有没有变好、花了多少钱。
>
> 我们跟 Langfuse/Phoenix 的区别是：他们做 Trace → Score，我们做 Trace → Eval → Regression → Skill Patch → Validation → Human Review → Export。这是一个完整的自迭代闭环。
>
> 商业上，我们走开源 + SaaS 模式，Free 版给个人开发者，Team 版给团队，Enterprise 给企业合规需求。核心壁垒是 Validation Gate + Human Review Gate 的双重约束——这让你不能随便改 Agent 的行为而不被记录。"
