# RESEARCH_REPORT.md — 外部研究对标报告

> 研究时间：2026-05-28 | 范围：8个开源产品 + 8个论文/方向
> 目的：为 StableAgent Cloud SaaS 提供产品定位和差异化依据

## 1. 开源产品对标

### 1.1 Langfuse (langfuse.com)

- **解决什么**: LLM应用全链路追踪和评测
- **核心架构**: Trace → Observation → Score → Dataset 的层级模型
- **SaaS能力**: 完整SaaS平台 + 自托管选项，付费wall
- **Trace/Eval/Dataset**: 三合一闭环，@observe()装饰器自动埋点，支持自定义Eval
- **适合迁移**: Trace→Eval→Dataset 闭环模式、@observe 自动埋点
- **不适合**: 重LLM调用层（非Agent层）、无Skill管理、无Agent降智防护

### 1.2 Arize Phoenix (github.com/Arize-AI/phoenix)

- **解决什么**: AI实验和可观测性
- **核心架构**: OTEL标准化 + 模块化子包(evals/experiments/tracing)
- **SaaS能力**: 开源为主，配套Arize Cloud付费
- **适合迁移**: OTEL标准、模块化子包架构、MCP Skill支持
- **不适合**: 过于通用、缺少Agent专属语义

### 1.3 Promptfoo (promptfoo.dev)

- **解决什么**: Prompt安全测试和红队对抗
- **核心架构**: CLI工具 + 声明式YAML配置
- **SaaS能力**: 适合CI/CD集成
- **适合迁移**: 声明式Eval配置、Red Team测试模式
- **不适合**: 无Agent生命周期管理

### 1.4 Braintrust (braintrustdata.com)

- **解决什么**: 企业级LLM可观测性和评测
- **核心架构**: Trace→Dataset一键转化 + 混合部署
- **SaaS能力**: 企业付费模型
- **适合迁移**: Trace→Dataset一键转化、Loop Agent模式
- **不适合**: 复杂度高、定价高

## 2. Agent框架对标

| 项目 | 关键洞察 | 对StableAgent Cloud启发 |
|------|---------|----------------------|
| **Agent-S** | ACI抽象层 + Grounding验证 | L1执行层沙盒策略 |
| **OSWorld** | Triple Recording（截图/动作/视频） | L2可观察层完整记录 |
| **OpenHands** | SDK统一引擎 + RBAC + 技能系统 | L3审计层 + 权限管理 |
| **SWE-agent** | Policy as Code + 轨迹存储 | 声明式Policy + 轨迹审计 |
| **LangGraph** | 持久化执行 + 人机协同 | StateGraph 持久化模式 |
| **AutoGen** | 事件驱动消息总线 | Agent事件标准化 |
| **CrewAI** | 双轨架构 + AMP企业可观察性 | 企业级SaaS参考 |
| **browser-use** | CLI+API双模式 + 模板系统 | 部署形态参考 |

## 3. 论文对标

| 论文/方向 | 核心方法 | 产品化建议 |
|----------|---------|-----------|
| **Reflexion** | 语言Agent通过语言反馈学习 | Eval反馈 → Skill Patch管道 |
| **Self-RAG** | 自我反思的RAG | 检索质量自动评分 |
| **ReAct** | 推理+行动协同 | Decision Trace=ReAct可视化 |
| **MemGPT/Mem0** | 分层记忆管理 | MemoryLayer三层模型 |
| **HITL Safety** | 人在回路Agent安全 | Human Review Gate |
| **Prompt Injection** | Prompt注入防御 | 安全评分 + Red Team |
| **SkillOpt** | Skill自动优化迭代 | Validation Gate核心 |
| **OS-Harm** | Agent harm评估 | safety_score维度 |

## 4. StableAgent Cloud 差异化

| 维度 | 竞品 | StableAgent Cloud |
|------|------|-------------------|
| 定位 | LLM可观测性/评测 | Agent全生命周期 |
| 独特能力 | Trace/评分 | + Skill自优化 + Validation Gate |
| 安全 | API/注入防护 | + Skill回滚机制 |
| 降智防护 | 无 | 核心价值：防遗忘/跑偏/降智 |
| MCP | 部分支持 | 原生MCP Gateway |
| 闭环 | 观察→反馈 | 观察→评测→回归→Skill优化→审核 |

## 5. 三层架构建议

```
L3 审计层: Human Review + RBAC + Compliance Dashboard
L2 观察层: Triple Recording + State Tracking + Message Bus
L1 执行层: ACI抽象 + 沙盒 + Policy as Code
```

## 6. P0/P1 落地建议

**P0（本轮必做）**：
- Trace→Eval→Regression→Skill Patch 闭环 ✓
- Validation Gate + Human Review Gate ✓
- Workspace/Project 多租户隔离 ✓

**P1（下轮）**：
- OTEL标准化导出
- Policy as Code（声明式Agent策略）
- Red Team安全测试

**不应照搬**：
- 自研时序数据库（用SQLite/PostgreSQL标准方案）
- 维护海量LLM框架集成包（聚焦MCP标准）
- GPL/AGPL许可证（用MIT/BSD兼容方案）
