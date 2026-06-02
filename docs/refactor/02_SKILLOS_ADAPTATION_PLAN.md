# 02_SKILLOS_ADAPTATION_PLAN.md

> 参考论文: SkillOS: Learning Skill Curation for Self-Evolving Agents
> 适配时间: 2026-06-02
> 适配原则: 只借鉴工程思想，不复现 RL 训练

---

## SkillOS 核心思想映射

| SkillOS 概念 | OS-Agent 适配 | 当前状态 | 目标状态 |
|---|---|---|---|
| **Executor** (冻结) | AgentExecutor | 嵌入在 unified_tool_registry.py | 独立 core/executor.py |
| **Curator** (独立) | CuratorService | 嵌入在 proof_loop + _h_task_os_agent | 独立 core/curator.py |
| **SkillRepo** (外部) | SkillRepository | best_skill.md 单文件 | 文件 + SQLite 双层 |
| **Validation Gate** (延迟) | ValidationGate | 嵌入在 proof_loop | 独立 core/validator.py |
| **Skill Candidate** | SkillCandidate | 无显式模型 | 数据类 + markdown schema |
| **Promotion Policy** | PromotionPolicy | 硬编码 | 规则化 + 可配置 |
| **Delayed Validation** | DelayedValidation | 无 | 基于 related tasks 验证 |
| **Reward Proxy** | RewardProxy | eval_score 单一指标 | 多维加权评分 |

---

## Phase 拆分与依赖关系

```
Phase 0: 审计与合同冻结 (无代码变更)
    ↓
Phase 1: Tool Profile 瘦身 (新增 tool_profiles.py，不改旧代码)
    ↓
Phase 2: 拆分 unified_tool_registry.py (新增 core/，逐步抽出)
    ↓
Phase 3: SkillRepo v2 (新增 skills/，独立于现有 skillopt)
    ↓
Phase 4: Curator v1 (规则型，依赖 Phase 2+3)
    ↓
Phase 5: Delayed Validation Gate (依赖 Phase 3+4)
    ↓
Phase 6: CLI + MCP stdio (依赖 Phase 1)
    ↓
Phase 7: Observer Replay 修复 (独立，可并行)
    ↓
Phase 8: 迁移文档 (依赖所有 Phase)
    ↓
Phase 9: 测试与验收 (依赖所有 Phase)
```

---

## 核心闭环设计

```
Task 输入
    ↓
AgentExecutor.run(task)
    ├── 创建 Run
    ├── 构建 Context (memory + skill retrieval)
    ├── 执行 Workflow
    ├── 评估 Eval
    └── 输出 RunTrace + Events
    ↓
CuratorService.analyze_trace(trace)
    ├── 判断 is_learning_worthy
    ├── 提取 failure_mode + evidence
    └── 生成 SkillCandidate
    ↓
ValidationGate.validate(candidate)
    ├── Schema Validation
    ├── Regression Validation
    └── Delayed Related Task Validation
    ↓
Promotion Decision
    ├── Promote → SkillRepo (promoted)
    ├── Reject → SkillRepo (archived)
    └── Keep → SkillRepo (candidate/validated)
    ↓
下次任务检索 promoted skills
```

---

## 关键设计决策

### 1. Executor 冻结原则
- Executor 只负责执行，不负责学习
- 执行结果通过 RunTrace 输出
- Executor 不知道 Curator 的存在

### 2. Curator 独立原则
- Curator 只分析 trace，不修改 executor
- Curator 产出 SkillCandidate，不直接写入 SkillRepo
- Curator 通过 ValidationGate 间接影响 SkillRepo

### 3. SkillRepo 外部化原则
- Skill 不是内存对象，是文件 + 索引
- Skill 有完整生命周期 (draft → candidate → validated → promoted → deprecated → archived)
- Skill 状态变化有审计日志 (promotion_log.jsonl)

### 4. Validation Gate 延迟原则
- Candidate 不允许直接 promoted
- 必须通过 related task 验证
- dry_run_learning=true 时禁止 promote
- 高风险 skill 必须 human_review

### 5. dry_run_learning 安全边界
- 可以生成 candidate
- 可以写 validation record
- 不允许 promote
- 不允许 export best_skill.md
