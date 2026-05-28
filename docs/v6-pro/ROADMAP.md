# ROADMAP.md — StableAgent OS V6-Professional+

## 当前版本：V6-Professional（2026-05-28）
闭环完成度：90%。792 tests。15 MCP 工具。

---

## P0：真实自我迭代闭环 ✅ (V6-Professional)

```text
Task → Trace → Eval → Failure Attribution → Reflection → Skill Patch
→ Validation Gate → Human Review → Export best_skill.md
```

- [x] EvaluationResult 增加 failure_attribution + step_efficiency
- [x] BadCase → Regression Case 转换
- [x] skills/candidates/ + skills/rejected/ 目录
- [x] SkillExporter Human Review Gate (PermissionError on non-validated)
- [x] SkillOptimizationEngine pre-export check
- [x] Architecture audit complete
- [x] Research report (Agent-S, OpenHands, AutoGen, MCP, OSWorld, Reflexion, Voyager)

---

## P1：Benchmark 与 Regression (计划中)

- [ ] MCP progress 通知机制 (`notifications/progress`)
- [ ] Dashboard replay/step-through 功能
- [ ] `llm_client.py` cost-aware routing
- [ ] `security_policy.py` sandbox 回滚机制
- [ ] `MemoryRouter.retrieve_experience_for_planning()` 显式接口
- [ ] 扩充 `data/regression_cases.jsonl`
- [ ] `ValidationGate` smoke test suite（5-10 固定场景）

---

## P2：GUI / OS Agent 能力

- [ ] `Workflow.sub_steps` 的 GUI 可视化
- [ ] `SandboxResult` 的 Docker sandbox 集成
- [ ] `resources/list` MCP 资源暴露
- [ ] SWE-bench 规模的 benchmark scaffold

---

## P3：多 Agent 和真实自动化执行

- [ ] 多 Agent 编排（依赖 AutoGen / LangGraph）
- [ ] 真实 OS 操作（依赖 OSWorld 环境）
- [ ] 安全审计自动化测试集
- [ ] 生产级部署方案（Docker Compose / k8s）
