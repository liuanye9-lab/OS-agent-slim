# CORE_LOOP_AUDIT.md — 核心闭环审计

**审计日期**: 2026-05-29  
**审计者**: OS-Agent Architecture Audit  
**版本**: V5.6 → V6.0 refactor

---

## 总体发现

**关键问题**: 代码库存在 **两条分离的流水线**，而非统一闭环：

1. **P0/P1/V3 主循环** (`StableAgentOrchestrator`) — Task → Trace → Eval → BadCase（部分链）
2. **V4 SkillOpt 循环** (`SkillOptimizationEngine`) — SkillPatch → ValidationGate → SkillExporter → best_skill.md（完全独立）
3. **SaaS 审核层** (`SkillReviewService`, `RegressionService`) — 通过 MCP 网关独立运行

**Orchestrator 和 SkillOpt/HumanReview 之间零连接**。两条链未经桥接。

---

## 逐模块审计

### 1. ContextDecisionEngine
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/context_decision_engine.py` (378行) |
| 真实调用 | ✅ Orchestrator `process_task()` 调用 `classify_task_multi`, `get_primary_task`, `detect_risk_level`, `should_require_approval` |
| 测试 | ✅ `tests/test_p0_core.py` |
| 服务主链 | ✅ Task → Classify |
| Stub | 无严重 stub（纯关键词匹配规则引擎） |
| 风险 | 分类为纯关键词匹配，可能漏掉新任务类型 |

### 2. ContextBudgetManager
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/context_budget_manager.py` (356行) |
| 真实调用 | ✅ Orchestrator 调用 `compute_budget`, `prune_memory` |
| 测试 | ✅ `tests/test_p0_core.py` |
| 服务主链 | ✅ Token预算分配 |
| Stub | `compress_documents` 标注为 **STUB**（仅字符截断，无语义压缩）；`route_model` 标注为 STUB |
| 静默失败 | `set_bad_case_count` 存在但 Orchestrator 中**从未被调用** |

### 3. MemoryRouter
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/memory_router.py` (537行) — MemoryBank + MemoryRouter |
| 真实调用 | ✅ Orchestrator 调用 `query_for_task`, `retrieve_by_task`, `add_memory_candidate`, `promote_candidate` |
| 测试 | ✅ `tests/test_p0_core.py` |
| 服务主链 | ✅ 记忆检索、候选记忆管理 |
| Stub | MemoryBank 为内存列表（无持久化），`query_relevant` 为关键词非语义 |
| 风险 | 进程重启记忆丢失；**add_memory_candidate 直接设置 status="active"**（lifecycle="candidate" 但 status 也是 active，筛选时会被检索到！）|

### 4. TemporalKnowledgeGraph
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/temporal_knowledge_graph.py` (384行) |
| 真实调用 | ❌ Orchestrator **实例化但从未在 process_task 中调用** |
| 测试 | ✅ `tests/test_p1_extensions.py` |
| 服务主链 | ❌ 未接入任何流程 |
| Stub | `query_facts` 标注需 Graphiti/Zep 图数据库 |
| 风险 | **高**: 已实例化但零使用。`from_memory_item`, `add_or_update_fact` 方法已实现但从未被调用 |

### 5. RAG Context Pack (RagContextManager)
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/rag_context_pack.py` |
| 真实调用 | ✅ Orchestrator 调用 `retrieve_rich`, `build_context_pack` |
| 测试 | ✅ `tests/test_p1_extensions.py` |
| 服务主链 | ✅ RAG 检索 |
| Stub | 多个 STUB：`index_documents`（应使用 faiss/Qdrant）、`retrieve`（应调用 embedding 模型） |
| 风险 | 倒排索引关键词匹配，非语义检索；大文件可能 OOM |

### 6. WorkflowEngine
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/workflow_state_machine.py` |
| 真实调用 | ✅ Orchestrator 实例化并注入依赖 |
| 测试 | ✅ `tests/test_p0_core.py` |
| 服务主链 | ✅ 工作流状态管理 |
| Stub | `_step_retrieve_knowledge` STUB；`_step_learn` STUB |
| 风险 | **中**: `SKILLOPT_WORKFLOW_STATES` 已定义但 WorkflowEngine 不处理 SkillOpt 状态；`is_skillopt_state` 静态方法从未被调用 |

### 7. Trace EventBus
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/trace_event_bus.py` |
| 真实调用 | ✅ 广泛用于 publish/subscribe/TraceStorage |
| 测试 | ✅ 多个测试覆盖 |
| 服务主链 | ✅ Trace → Event |

### 8. Evaluator & BadCaseManager
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/eval_and_bad_case.py` |
| 真实调用 | ✅ Orchestrator 调用 `evaluator.evaluate`, `bad_case_manager.record_case` |
| 测试 | ✅ `tests/test_p0_core.py` |
| 服务主链 | ✅ Eval + BadCase |
| Stub | `_compute_hallucination_score` 标注需专门幻觉检测模型；`user_preference_score` 硬编码 0.7 |
| 风险 | **中**: 评估完全启发式/规则式，无 LLM-as-judge；`convert_to_regression_case` 已实现但 Orchestrator 中**无调用** |

### 9. RegressionService
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/saas/regression_service.py` |
| 真实调用 | ❌ **未被 Orchestrator 调用**，仅通过 MCP 工具调用 |
| 测试 | ✅ `tests/test_regression_from_badcase.py` |
| 服务主链 | ❌ 断层：BadCase → Regression 转换未自动触发 |

### 10. SkillOpt (SkillOptimizationEngine)
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/skill_optimizer/skill_optimization_engine.py` |
| 真实调用 | ❌ **未被 Orchestrator 调用**，仅通过 MCP 工具调用 |
| 测试 | ✅ `tests/test_skill_optimization_engine.py` |
| 服务主链 | ❌ 断层：Eval → SkillPatch 完全独立 |

### 11. ValidationGate
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/skill_optimizer/validation_gate.py` |
| 真实调用 | ❌ 只由 SkillOptimizationEngine 调用，Orchestrator 不调用 |
| 测试 | ✅ `tests/test_validation_gate.py` |
| 服务主链 | ❌ 验证门使用模拟执行（`_simulate_execution`），非真实验证 |

### 12. Human Review (SkillReviewService)
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/saas/skill_review_service.py` |
| 真实调用 | ❌ 仅通过 MCP 工具调用 |
| 测试 | ✅ `tests/test_skill_validation_review.py` |
| 服务主链 | ❌ baseline skill 硬编码占位内容 |

### 13. best_skill.md Export
| 属性 | 详情 |
|------|------|
| 存在 | ✅ `stable_agent/skill_optimizer/skill_exporter.py` |
| 真实调用 | ❌ 只由 SkillOptimizationEngine 调用 |
| 测试 | ✅ 通过引擎集成测试 |
| 文件存在 | ✅ `skills/best_skill.md` — 但仅含 111 字节占位内容 |
| 自动覆盖风险 | ⚠️ 有安全控制（validation_passed=False 或 human_reviewed=False 时抛 PermissionError），但引擎可在无验证时调用 |

### 14. ContextCompressionGuard（缺失）
- ❌ **不存在**。无独立 compression guard 模块
- 压缩由 `ContextTriage._compact_items` 处理（基于 token 预算丢弃条目）
- 无语义压缩、无保护清单（用户当前目标、项目约束、高置信记忆等）

### 15. Self-Improvement 目录（缺失）
- ❌ **不存在**。无 `self_improvement/` 目录
- 全代码库搜索 `self_improvement` — 零匹配

---

## 链路完整性分析

### 目标链
```
Task → Trace → Eval → Regression → SkillPatch → ValidationGate → HumanReview → best_skill.md
```

### 实际状态

| 步骤 | 状态 | 说明 |
|------|------|------|
| Task | ✅ 已连接 | Orchestrator `process_task()` |
| Trace | ✅ 已连接 | EventBus + TraceStorage |
| Eval | ✅ 已连接 | Evaluator（但为启发式/模拟评分） |
| Regression | ❌ **断开** | RegressionService 已实现但不被 Orchestrator 调用 |
| SkillPatch | ❌ **断开** | SkillOptimizationEngine 是独立系统 |
| ValidationGate | ❌ **断开** | 由 SkillOpt 引擎调用，Orchestrator 不调用 |
| HumanReview | ❌ **断开** | SkillReviewService 仅通过 MCP 暴露 |
| best_skill.md | ❌ **断开** | 仅独立 SkillOpt 引擎可导出 |

### 实际链 (Orchestrator):
```
Task → Classify → Budget → Memory Retrieval → RAG → ContextPack → 
Approval → Workflow(INIT→...→EXECUTE→EVALUATE→LEARN→COMPLETE) → 
Evaluation → BadCase → Result
```

### 实际链 (SkillOpt 引擎 — 完全独立):
```
RolloutCollection → Split(S/F) → Analyze → MergePatches → Rank → 
Apply → ValidationGate → Accept/Reject → SlowMeta → Export best_skill.md
```

---

## 风险汇总

| 风险 | 严重性 | 受影响模块 |
|------|--------|------------|
| Orchestrator 和 SkillOpt 之间零连接 | **严重** | 全链 |
| TemporalKnowledgeGraph 已实例化但零调用 | 高 | TKG |
| ValidationGate 使用模拟执行 | 高 | ValidationGate |
| SkillReviewService 使用硬编码 baseline | 高 | SkillReviewService |
| Evaluator 纯启发式（无 LLM judge） | 中 | Evaluator |
| user_preference_score 硬编码 0.7 | 中 | Evaluator |
| MemoryBank 纯内存无持久化 | 中 | MemoryRouter |
| compress_documents 仅字符截断 | 中 | ContextBudgetManager |
| 失败经验可绕过 candidate 进 active | 中 | MemoryRouter.add_memory_candidate |
| 缺失 ContextCompressionGuard | 中 | 上下文压缩 |
| 缺失 Self-Improvement 闭环 | 中 | 自优化 |
| best_skill.md 仅占位内容 | 低 | SkillExporter |
| 10+ 处 STUB 标记 | 信息 | 多模块 |

---

## 下一步行动

见 `CORE_LOOP_REFACTOR_PLAN.md`
