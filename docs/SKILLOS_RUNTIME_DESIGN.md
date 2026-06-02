# SKILLOS_RUNTIME_DESIGN.md — StableAgent OS V12 SkillOS Runtime Curation 设计文档

## 1. 为什么不做 Full RL

SkillOS 原论文提出使用 GRPO (Group Relative Policy Optimization) 进行技能策展的强化学习训练。但在工程实践中：

1. **资源限制**：GRPO 训练需要 16×H100 级别的 GPU 资源，不适合 2 核 2GB 的 OpenClaw 云服务器。
2. **数据量不足**：当前 run trace 数据量远未达到 RL 训练所需的规模。
3. **工程复杂度**：引入 verl 等 RL 框架会大幅增加系统复杂度和维护成本。
4. **实际需求**：用户更需要的是"可解释的技能经营"，而非黑盒的策略优化。

因此，本次升级只复刻 SkillOS 的 **runtime curation loop**，不做 RL 训练。

## 2. 架构概览

```
User / Claude Code / Codex / Trae
        ↓
MCP / CLI / Dashboard
        ↓
OS-Agent Run Kernel
        ↓
Skill Retrieval ← SkillRepo
        ↓
Executor / Worker
        ↓
Trajectory Store
        ↓
Outcome Judge + Content Judge
        ↓
Skill Curator Service
        ↓
SkillRepo insert / update / delete
        ↓
Version Store + Rollback
        ↓
Dashboard Observer
```

## 3. 核心组件

### 3.1 SkillRepo

**职责**：统一的技能存储库，支持 MCP / CLI / Dashboard 共用。

**存储**：
- SQLite 数据库：`.stableagent-capsule/skills/skills.sqlite`
- 技能包目录：`.stableagent-capsule/skills/packages/`
- 事件日志：`.stableagent-capsule/skills/events/`

**特性**：
- append-only curation event
- 软删除（status=deleted）
- 版本化存储
- 可回滚

### 3.2 SkillRetriever

**职责**：轻量检索，不引入重型 embedding。

**方法**：BM25 + keyword scoring

**评分规则**：
1. trigger phrase exact match (5.0)
2. name match (3.0)
3. description match (2.0)
4. tag match (2.0)
5. 最近成功加权 (+0.5)
6. 最近失败降权 (-1.0)

### 3.3 SkillCuratorService

**职责**：任务结束后自动生成 curation ops。

**双阶段流程**：
1. **Propose**：根据 run outcome 生成候选操作
2. **Review/Apply**：默认需人工确认，低风险可自动应用

**规则**：
- 成功 + 无 skill → insert
- 成功 + 有 skill → update
- 失败 + 有 skill → pitfall update
- 多次失败 → archive

### 3.4 Judges

**OutcomeJudge**：判断 run 是否成功
- task.completed + tests passed → success
- task.failed → failure
- user negative feedback → failure

**ContentJudge**：判断 skill 内容质量
- safety: 是否包含危险命令
- abstractness: 是否过度绑定单个案例
- reusability: 是否可复用
- executability: 是否有明确步骤
- compression: 是否太长

### 3.5 Version Rollback

**机制**：
- 每次变更自动创建版本快照
- 可回滚到任意历史版本
- 回滚生成新版本（不破坏历史）

## 4. 2 核 2GB OpenClaw 部署

### 环境变量

```bash
STABLEAGENT_PROFILE=slim
STABLEAGENT_ENABLE_SKILL_REPO=true
STABLEAGENT_ENABLE_SKILL_LLM_JUDGE=false
STABLEAGENT_ENABLE_GROUPED_REPLAY=true
STABLEAGENT_ENABLE_HEAVY_RL=false
STABLEAGENT_ENABLE_SKILL_DASHBOARD=true
STABLEAGENT_MAX_ACTIVE_SKILLS=200
STABLEAGENT_MAX_SKILL_VERSIONS=20
STABLEAGENT_SKILL_TOP_K=5
```

### systemd 配置

```ini
[Unit]
Description=StableAgent OS Slim
After=network.target

[Service]
Type=simple
User=agent
WorkingDirectory=/opt/os-agent
Environment=STABLEAGENT_PROFILE=slim
ExecStart=/opt/os-agent/.venv/bin/python -m stable_agent.cli serve --host 127.0.0.1 --port 18789 --profile slim
Restart=always
RestartSec=5
MemoryMax=1500M

[Install]
WantedBy=multi-user.target
```

### 限制

- 不加载重型 LLM
- 不加载 embedding 模型
- 不运行 RL
- SQLite 存储
- 每 5 秒轮询 Dashboard

## 5. MCP / CLI / Dashboard 共用

三个入口共享同一个 SkillRepo 实例：

- **MCP**：通过 `stableagent.skill.*` 工具调用
- **CLI**：通过 `stable_agent.cli skill *` 命令
- **Dashboard**：通过 `/api/skills/*` API

所有操作都经过 SkillRepo，确保数据一致性。
