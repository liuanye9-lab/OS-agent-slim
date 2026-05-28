# RESEARCH_REPORT.md — StableAgent OS V6-Professional

## 1. 本轮研究目标

从开源项目（Agent-S、OpenHands、AutoGen Studio、MCP 生态）和前沿论文中，
提取可借鉴的架构模式、评估方法和安全机制，指导 StableAgent OS 的 P0 闭环升级。
**边界**：只做研究驱动的收敛式升级，不做大规模重构。

---

## 2. 研究对象清单

| 类别 | 对象 | 研究维度 |
|------|------|----------|
| 开源项目 | `simular-ai/Agent-S` | experience-augmented hierarchical planning |
| 开源项目 | `OpenHands` | sandbox + REST/WebSocket + 多模型路由 + 安全分析 |
| 开源项目 | `AutoGen Studio` | 可视化构建、调试和评估多智能体工作流 |
| 开源项目 | `Aider` | 代码编辑 agent 的 diff-patch 模式 |
| 开源项目 | `SWE-agent` | agent-computer-interface (ACI) 设计 |
| 协议 | MCP (Model Context Protocol) | 统一协议暴露工具和上下文 |
| 论文 | Agent-S / Agent-S2 | 经验增强的层级规划 |
| 论文 | OSWorld / OSWorld-Human | Agent 评估不只关注成功率，还要关注执行步数、延迟和效率 |
| 论文 | Reflexion | 基于语言反馈的自我反思 |
| 论文 | ReAct | 推理与行动交替 |
| 论文 | Voyager | 技能库的自动发现和积累 |
| 论文 | MemGPT / Mem0 | 分层记忆管理 |

---

## 3. 开源项目对标

### 3.1 Agent-S（simular-ai/Agent-S）

**核心机制**：experience-augmented hierarchical planning。Agent 在执行任务时，先做高层规划，
再做低层执行；在遇到类似场景时，从经验库中检索过去的成功规划作为参考。

**借鉴点**：
- **经验检索作为规划输入**：StableAgent OS 的 MemoryRouter 已有类似能力（检索过去记忆），
  但缺少"将检索到的经验注入规划阶段"的显式路径。应补齐。
- **层级规划 (hierarchical planning)**：WorkflowStateMachine 已有阶段划分，但缺少
  高层 Plan → 低层 Step 的显式分解。应考虑在 `Workflow` 结构中增加 `sub_steps`。
- **步数效率**：OSWorld-Human 提醒我们，成功率之外还要关注执行步数。
  EvaluationResult 可增加 `step_efficiency` 字段。

**不适合照搬**：
- Agent-S 依赖 GUI screenshot 做视觉规划，StableAgent OS 不需要。
- Agent-S 的 experience-augmented 机制依赖大量 rollout 数据，稳定性要求高。

**对 StableAgent OS 的升级建议**：
- P0：EvaluationResult 增加 `failure_attribution` 和 `step_efficiency` 字段。
- P0：Workflow 增加 `sub_steps` 字段支持层级规划。
- P1：MemoryRouter 显式暴露 `retrieve_experience_for_planning()` 接口。

### 3.2 OpenHands

**核心机制**：sandbox 内运行 agent、REST + WebSocket 通信、多模型路由、安全分析。

**借鉴点**：
- **Sandbox 隔离**：StableAgent OS 已有 `swe_sandbox.py` 和 `git_diff_checkpoint.py`，
  但 Sandbox 和主体流程之间的通信是单向的。应参考 OpenHands 的双向事件流。
- **WebSocket 实时同步**：Dashboard V2 已有 WebSocket 订阅，但缺少双向确认。
  应确保 Dashboard 能发回 approval 响应。
- **多模型路由**：`llm_client.py` 已有基础，但缺少 cost-aware routing。
- **安全分析**：`security_policy.py` 已有风险分级，但缺少 sandbox 内的执行回滚。

**不适合照搬**：
- OpenHands 的 Docker sandbox 太重，适合 GUI 场景，不适合轻量 MCP 场景。
- OpenHands 的前端是完整 IDE，StableAgent OS 只需要轻量 Dashboard。

**对 StableAgent OS 的升级建议**：
- P0：确保 MCP tools/call 返回结构中的 `structuredContent` 包含 `dashboard_url`。
- P1：`security_policy.py` 增加 sandbox 回滚机制。
- P2：`llm_client.py` 增加 cost-aware routing。

### 3.3 AutoGen Studio

**核心机制**：可视化构建、调试和评估多智能体工作流。

**借鉴点**：
- **可视化调试**：Dashboard V2 已有决策时间线和语义场景，但缺少"可交互的调试面板"。
  应增加 `run_id` 级别的 replay/step-through 功能。
- **评估集成**：AutoGen Studio 在 UI 中内建评估面板。StableAgent OS 应把 Eval 结果
  直接映射到 Dashboard 的 RunInsight 卡片。

**不适合照搬**：
- AutoGen 是多 agent 框架，StableAgent OS 当前是单 agent + 工具编排。
  本轮不做多 agent 迁移。

**对 StableAgent OS 的升级建议**：
- P0：RunInsight 卡片展示 Eval 结果（已有，需验证数据流完整性）。
- P1：Dashboard 增加 replay/step-through 功能。

### 3.4 MCP (Model Context Protocol)

**核心机制**：通过统一 JSON-RPC 2.0 协议暴露工具和上下文。

**对齐状态**：
- ✅ StableAgent OS V5.6 已实现统一 MCP Gateway（`/mcp/v5/mcp`）。
- ✅ 15 个工具通过 `UnifiedToolRegistry` 注册。
- ✅ JSON-RPC 2.0 兼容（`initialize`/`tools/list`/`tools/call`）。
- ✅ 返回结构含 `content` + `structuredContent`。

**差距**：
- `tools/call` 返回中的 `structuredContent` 字段在某些工具中未被充分填充。
- `progress_token` 机制未实现（MCP 的进度通知）。
- 缺少 `resources/list` 实现（MCP 资源暴露）。

**对 StableAgent OS 的升级建议**：
- P0：确保所有 15 个工具的 `structuredContent` 包含完整字段。
- P1：实现 MCP `notifications/progress` 机制。
- P2：实现 `resources/list`。

---

## 4. 论文对标

### 4.1 Agent-S / Agent-S2（层级规划 + 经验增强）

**核心问题**：如何让 Agent 在复杂 GUI 任务中既高效又可泛化？
**方法机制**：将任务分为 High-Level Plan（自然语言，可检索经验）和 Low-Level Action（具体操作）。
**和 StableAgent OS 的关系**：
- WorkflowStateMachine 已有阶段划分，`Workflow` 数据类可扩展 `sub_steps`。
- MemoryRouter 检索的记忆可以直接注入 `Plan` 阶段。
**不能照搬**：Agent-S 的 GUI-specific 经验编码不适用。
**对 P0 闭环的启发**：Plan 阶段应显式引用检索到的经验，Workflow 结构应支持层级。

### 4.2 Reflexion（基于语言反馈的自我反思）

**核心问题**：Agent 执行失败后，如何自动改进？
**方法机制**：Agent 在失败后生成一段"反思文本"，作为下次执行的额外上下文。
**和 StableAgent OS 的关系**：
- `BadCaseManager` 已有 `record_case()` 和 `convert_to_eval_case()`。
- `generate_improvement_rule()` 的反思基于模板，非 LLM 生成。
- `SkillOptimizationEngine.run_epoch()` 包含 `_analyze_failures()`。
**不能照搬**：Reflexion 的 LLM 生成反思成本高，不适合每次都做。
**对 P0 闭环的启发**：
- `EvaluationResult` 缺少 `failure_attribution` 字段（即"具体是哪一步失败的"）。
- BadCase 应能直接转为 regression case，而非仅作提示。

### 4.3 Voyager（技能库的自发现和积累）

**核心问题**：Agent 如何自动发现、验证并积累可复用技能？
**方法机制**：Agent 在执行 Minecraft 任务时，自动发现可复用的行为模式，
并将它们编码为 JavaScript 技能函数存入技能库。
**和 StableAgent OS 的关系**：
- `SkillOptimizationEngine` 的设计理念与 Voyager 相似：rollout → pattern → patch → validation。
- `SkillDocumentStore` 管理 `best_skill.md` + 版本管理。
**不能照搬**：Voyager 的技能是代码函数，StableAgent OS 的技能是 Markdown 规则文档。
**对 P0 闭环的启发**：
- Voyager 强调"验证通过才能进入技能库"，StableAgent OS 的 ValidationGate 应强化此约束。
- Voyager 的 Curriculum Learning 暗示我们需要更多 regression cases 来训练 ValidationGate。

### 4.4 MemGPT / Mem0（分层记忆管理）

**核心问题**：LLM 的上下文窗口有限，如何高效记忆？
**方法机制**：将记忆分为 Working Memory（当前对话）、Recall Memory（可检索的长期记忆）、
Archival Memory（外部存储）。
**和 StableAgent OS 的关系**：
- `MemoryRouter` + `MemoryLayer` 枚举已有类似分层设计。
- `ContextBudgetManager` 管理 token 预算。
**不能照搬**：MemGPT 的 OS-level 内存管理太重，StableAgent OS 的 SQLite 方案已足够。
**对 P0 闭环的启发**：记忆检索应在 Plan 阶段显式注入，并有证据溯源。

### 4.5 OSWorld-Human

**核心发现**：评估 Agent 不仅要看 success rate，还要看 step count、latency、efficiency。
**对 P0 闭环的启发**：
- EvaluationResult 应增加 `step_efficiency` 和 `latency_ms` 字段。
- RunInsight 应展示这些指标。

---

## 5. 迁移到 StableAgent OS 的模式

| 来源 | 模式 | 迁移方式 | 优先级 |
|------|------|----------|--------|
| Agent-S | experience → plan 注入 | MemoryRouter 在 Plan 阶段显式注入 | P0 |
| Agent-S | hierarchical planning | Workflow 增加 sub_steps | P0 |
| OSWorld-Human | 步数效率评估 | EvaluationResult 增加 step_efficiency | P0 |
| Reflexion | failure → attribution | EvaluationResult 增加 failure_attribution | P0 |
| Voyager | validation gate | ValidationGate 强化为硬约束 | P0 |
| SWE-agent | ACI 设计 | Tool interface 规范化 | P1 |
| MCP | progress通知 | tools/call 返回 progress_pct | P1 |
| MemGPT | 分层记忆 | 已对齐 ✅ | - |
| OpenHands | sandbox 隔离 | 已对齐 ✅ | - |
| AutoGen Studio | 可视化调试 | Dashboard V2 已对齐 ✅ | - |

---

## 6. 不应迁移的模式

| 来源 | 模式 | 原因 |
|------|------|------|
| Agent-S | GUI screenshot planning | 不适用轻量 MCP 场景 |
| OpenHands | Docker sandbox | 太重 |
| AutoGen | 多 agent 框架 | 本轮不做多 agent |
| Voyager | 代码技能函数 | skill 是 Markdown 规则 |
| MemGPT | OS-level 内存管理 | SQLite 已足够 |
| Reflexion | 每次 LLM 反思 | token 成本高 |

---

## 7. 对本轮 P0 / P1 的影响

### 直接影响 P0 闭环的发现：

1. **EvaluationResult 缺少 failure_attribution**（来自 Reflexion）：需增加字段，标明"哪一步失败、为什么失败"。
2. **BadCase → Regression Case 路径不完整**（来自 Voyager）：需增加 `convert_to_regression_case()` 方法，导出 `data/regression_cases.jsonl`。
3. **ValidationGate 不是硬约束**（来自 Voyager）：需确保 `best_skill.md` 只由 `SkillExporter` 在验证通过后导出，不自动覆盖。
4. **Workflow 缺少层级规划**（来自 Agent-S）：需增加 `sub_steps` 字段。
5. **步数效率未评估**（来自 OSWorld-Human）：EvaluationResult 需增加 `step_efficiency`。

### 不影响本轮但值得记录的发现：

6. MCP progress 通知机制（P1）。
7. 可交互的 Dashboard replay（P1）。
8. cost-aware model routing（P2）。

---

## 8. 后续研究缺口

- SWE-bench 规模的 benchmark 集成（需要真实 Docker sandbox）
- 多 agent 协作模式（依赖 AutoGen 或 LangGraph）
- 真实 OS 操作能力（依赖 OSWorld 环境）
- 安全审计的自动化测试集
