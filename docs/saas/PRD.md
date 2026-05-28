# StableAgent Cloud PRD

> 版本：SaaS v1.0-MVP | 日期：2026-05-28
> 从单机Agent Runtime升级为商业化AgentOps + SkillOps SaaS

## 1. 背景

### 1.1 现状

StableAgent OS v5.6 是一个运行在本地/单机上的Agent Runtime，通过MCP协议提供服务。核心能力：
- 记忆管理（防遗忘）
- 上下文预算（防token爆炸）
- 工作流引擎（防跑偏）
- 评测+BadCase（防降智）
- Skill自优化（防退化）
- MCP Gateway（统一工具入口）
- Dashboard（可观测性）

**现状问题**：单机模式无法支撑团队协作和商业化，所有数据混在一起，没有多租户隔离。

### 1.2 为什么做SaaS

```
单机Agent Runtime           →     AgentOps + SkillOps SaaS
"我能让自己变好"              →     "我能让团队的每个Agent变好"
本地自我迭代                   →     跨团队、跨项目的经验共享
run_id = 唯一标识              →     workspace > project > run 层级体系
```

## 2. 产品定位

**StableAgent Cloud** 是一个面向AI Agent团队的 **AgentOps + SkillOps SaaS**。

> 它把每次Agent执行变成trace，把trace变成eval，把失败变成regression case，把稳定经验变成skill patch，再通过validation gate和human review，最终导出可审计、可回滚的best_skill.md。

### 核心差异

| 维度 | 竞品（Langfuse等） | StableAgent Cloud |
|------|-------------------|-------------------|
| 定位 | LLM可观测性 | Agent全生命周期 |
| 数据模型 | trace为中心 | workspace > project > run > trace |
| 闭环 | 观察+反馈 | 观察→评测→回归→Skill优化→验证→人工审核 |
| 安全 | API内 | 内建skill回滚机制 |
| 商业化 | 成熟 | MVP阶段 |

## 3. 目标用户

### 3.1 用户画像

- **AI Agent团队**（2-20人）：使用Claude Code / Codex / Cursor等工具进行日常开发
- **Agent运维人员**：需要监控Agent行为、审计决策、防止降智
- **Prompt/ Skill工程师**：需要迭代优化Agent的skill/prompt
- **技术管理者**：需要看到Agent团队的效率、成本、质量指标

### 3.2 使用场景

1. **Agent行为审计**：团队经理查看本周Agent跑了多少任务、哪些失败、为什么
2. **Skill迭代**：Skill工程师提交patch → validation → 人工审核 → 发布
3. **防降智**：Eval自动检测 → BadCase → Regression → 阻止退化skill上线
4. **成本控制**：按项目/token使用量追踪，发现浪费
5. **新人接入**：一键生成MCP配置，3分钟接入Claude Code/Codex

## 4. 用户痛点

| 痛点 | 现状 | StableAgent Cloud方案 |
|------|------|----------------------|
| Agent降智但不知情 | 无自动检测 | Eval自动评分，低于阈值告警 |
| 改prompt导致退化 | 无回归测试 | Regression suite自动检测 |
| 团队经验无法共享 | 每人独自优化 | Skill Library + workspace共享 |
| 不知道Agent花了多少钱 | 无可视化 | Usage counter + token成本追踪 |
| 新人不知道如何接入 | 手动配置MCP | 一键生成配置 |
| 决策不可审计 | 无trace | DecisionTrace完整记录 |

## 5. 核心价值主张

> **让Agent团队告别"降智盲飞"，每个决策可审计，每次失败能沉淀，每个优化可验证。**

一句话：把Agent管理从"玄学"变成"工程"。

## 6. 产品信息架构

```
StableAgent Cloud
├── Workspace（团队空间）
│   ├── Members（成员管理）
│   └── Projects（项目）
│       ├── Agent Profiles（Agent配置）
│       ├── Runs（执行记录）
│       │   ├── Traces（决策追踪）
│       │   ├── Eval Results（评测结果）
│       │   └── Usage Events（用量记录）
│       ├── Skills（技能库）
│       │   ├── Skill Documents
│       │   ├── Skill Patches（待审核补丁）
│       │   └── Validation Runs
│       ├── Regression Cases（回归用例集）
│       ├── Bad Cases（失败案例）
│       └── Human Reviews（人工审核记录）
├── API Keys（访问控制）
├── Usage（用量面板）
└── Settings（工作区设置）
```

## 7. 核心功能模块

### 7.1 Workspace / Project

- 创建workspace（团队空间）
- 在workspace下创建project
- 邀请成员（P1）
- Workspace级别的settings

### 7.2 Agent Run

- 每次MCP tools/call创建一个run
- run必须归属于 project_id
- SaaS模式必须校验project_id
- local模式fallback到default project

### 7.3 Trace / Decision Trace

- 每个run下的决策事件记录
- 决策类型、理由、丢弃的选项
- 双语（中/英）决策解释
- Trace timeline可视化

### 7.4 Eval

- 6维自动评分（完成度/上下文/效率/幻觉/偏好/安全）
- 按project聚合评分趋势
- 低于阈值自动标记BadCase
- Eval dashboard

### 7.5 BadCase / Regression Dataset

- 失败案例自动收集
- BadCase → RegressionCase一键转换
- 回归数据集管理
- 阻止skill退化

### 7.6 SkillOpt / Skill Library

- Skill多版管理
- Patch建议（基于失败分析）
- Skill版本对比
- 跨project共享skill（P1）

### 7.7 Validation Gate

- 候选skill vs 基线skill自动评分
- 必须 new_score > old_score
- 关键任务类型回归检查
- 不通过无法进入审核

### 7.8 Human Review

- 人工审核面板
- 审核记录持久化
- 未审核skill无法导出
- 审核历史可追溯

### 7.9 MCP Gateway

- 统一JSON-RPC 2.0端点
- 所有工具支持project_id
- 新增SaaS管理工具（project/run/trace/eval/skill/usage）
- SaaS模式强校验

### 7.10 Dashboard

- Workspace selector
- Project selector
- Runs列表（按时间/状态筛选）
- Run detail（决策时间线+评测结果+skill diff）
- Usage趋势
- 玻璃拟态UI

### 7.11 API Key / Usage Counter

- API Key创建/撤销
- Key绑定workspace
- 基础用量记录（MCP调用/token/run）
- Usage dashboard

### 7.12 Billing Scaffold

- UsageEvent持久化
- cost_estimated字段
- 为未来计费做准备
- 本轮不接Stripe

## 8. SaaS 权限设计

### MVP（P0）

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Workspace   │───▶│   Project    │───▶│    Run      │
│  (团队空间)   │    │   (项目)     │    │   (执行)    │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
  API Keys           Agent Profiles     Traces / Evals
```

- Workspace: 隔离边界
- Project: 资源归属
- Run: 最小执行单元
- API Key: workspace级访问

### P1（后续）
- 成员角色（owner/admin/member/viewer）
- Project级权限
- RBAC

## 9. 数据模型

### 9.1 核心实体（16个）

```python
Workspace(id, name, created_at)
WorkspaceMember(id, workspace_id, user_id, role)
Project(id, workspace_id, name, description, created_at)
AgentProfile(id, workspace_id, project_id, name, config)
AgentRun(id, workspace_id, project_id, agent_id, status, started_at, ...)
TraceEventRecord(id, run_id, event_type, payload, decision_trace, ...)
EvalResultRecord(id, run_id, workspace_id, project_id, scores, ...)
BadCaseRecord(id, workspace_id, project_id, run_id, task_type, ...)
RegressionCaseRecord(id, workspace_id, project_id, task_input, expected_behavior, ...)
SkillRecord(id, workspace_id, project_id, name, current_version, ...)
SkillVersionRecord(id, skill_id, version, content, score, ...)
SkillPatchRecord(id, skill_id, from_version, to_version, patch_content, ...)
ValidationRunRecord(id, patch_id, baseline_score, candidate_score, passed, ...)
HumanReviewRecord(id, target_id, target_type, reviewer, status, ...)
ApiKeyRecord(id, workspace_id, key_hash, name, created_at, revoked_at, ...)
UsageEventRecord(id, workspace_id, project_id, run_id, event_type, tokens, cost, ...)
```

### 9.2 关键字段约束

所有实体必须包含：`id` / `created_at`
归属实体必须包含：`workspace_id` / `project_id`（除非该实体天然不属于project，如Workspace本身）

## 10. API 设计

### 10.1 MCP 工具（新增/升级）

```
stableagent.project.create    → 创建项目
stableagent.project.list      → 列出项目
stableagent.task.os_agent     → 统一任务入口（已有，升级支持project_id）
stableagent.run.get           → 获取运行记录
stableagent.run.list          → 列出项目运行
stableagent.trace.get         → 获取决策追踪
stableagent.eval.run          → 执行评测
stableagent.eval.result       → 获取评测结果
stableagent.regression.create → 从BadCase创建回归用例
stableagent.skill.patch_propose → 提交skill补丁
stableagent.skill.validate    → 验证skill补丁
stableagent.skill.review      → 人工审核skill
stableagent.skill.export_best → 导出best_skill
stableagent.usage.get         → 获取用量
```

### 10.2 REST API（Dashboard用）

```
GET  /api/projects                        → 列出项目
POST /api/projects                        → 创建项目
GET  /api/projects/{id}/runs              → 项目运行列表
GET  /api/projects/{id}/runs/{run_id}     → 运行详情
GET  /api/projects/{id}/skills            → 技能列表
GET  /api/projects/{id}/evals             → 评测历史
GET  /api/projects/{id}/usage             → 用量统计
```

## 11. Dashboard 交互设计

### 11.1 页面结构

```
┌─────────────────────────────────────────────────────┐
│  StableAgent Cloud  [Workspace ▼]  [Project ▼]     │
├─────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────┐│
│  │  Runs List           │  │  Run Detail          ││
│  │  - run_001 ✅        │  │  ┌────────────────┐  ││
│  │  - run_002 ❌        │  │  │ Decision Trace │  ││
│  │  - run_003 ✅        │  │  └────────────────┘  ││
│  │  - run_004 ⏳        │  │  ┌────────────────┐  ││
│  │                      │  │  │ Eval Results   │  ││
│  └──────────────────────┘  │  └────────────────┘  ││
│  ┌──────────────────────┐  │  ┌────────────────┐  ││
│  │  Usage Overview      │  │  │ Skill Diff     │  ││
│  │  [Token Chart]       │  │  └────────────────┘  ││
│  └──────────────────────┘  └──────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### 11.2 视觉语言
- 玻璃拟态（毛玻璃 + 高斯模糊）
- 低饱和渐变背景（流动壁纸）
- iOS风格信息层级
- 非技术用户友好（简洁中文标签）

## 12. 商业化定价建议（MVP不实现，仅设计）

| 层级 | 价格 | 功能 |
|------|------|------|
| Free | ¥0/月 | 1 workspace, 3 projects, 1000 runs/月 |
| Pro | ¥99/月 | 5 workspaces, 20 projects, 10000 runs/月 |
| Team | ¥499/月 | 无限workspace, 团队协作 |
| Enterprise | 询价 | SSO, 私有部署, SLA |

## 13. MVP 范围

### P0（本轮）
- [x] SaaS数据模型scaffold
- [x] Project/Run/Trace归属
- [x] MCP project_context
- [x] Eval→Regression闭环
- [x] Skill Validation + Human Review Gate
- [x] Usage Counter
- [x] API Key scaffold
- [x] Dashboard按project查看
- [x] 测试覆盖
- [x] 文档产出

### P1（下一轮）
- [ ] Workspace UI管理
- [ ] 成员邀请
- [ ] Skill跨project共享
- [ ] Usage面板完整
- [ ] Billing scaffold接Stripe

### P2（远期）
- [ ] PostgreSQL
- [ ] SSO/OAuth
- [ ] RBAC
- [ ] 私有部署

## 14. 验收标准

### 功能验收
1. 可创建workspace和project
2. run必须归属project
3. trace event归属run
4. MCP tool call携带project_id
5. 无project_id在SaaS模式失败
6. local模式可用default project
7. BadCase可转RegressionCase
8. Skill Patch不能绕过Validation Gate
9. best_skill.md不能绕过Human Review
10. UsageEvent记录用量
11. API Key可创建/撤销
12. Dashboard可按project查看

### 非功能验收
- 现有792测试保持通过
- 新增test至少80%通过
- 无dataclass JSON序列化错误
- 向后兼容（现有MCP工具参数不变）

## 15. 面试讲述版本

> "我们把StableAgent从单机Agent Runtime升级成了AgentOps SaaS。核心思路是：不是重新发明LLM可观测性，而是针对Agent的特殊性——Agent会遗忘、会跑偏、会降智——建立了一套从执行到评测到回归到Skill优化的完整闭环。每个run都有完整的decision trace，每次失败都转成regression case，每次skill优化都要过validation gate和human review才能上线。现在团队可以共享skill经验，管理者可以看到Agent在做什么、花多少钱、质量如何。这是把Agent管理从玄学变成工程的第一步。"
