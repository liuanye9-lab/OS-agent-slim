# CORE_LOOP_REFACTOR_PLAN.md — 核心闭环重构计划

**版本**: V6.0  
**日期**: 2026-05-29

---

## 目标

将 OS-Agent 从"模块堆积"升级为"闭环自优化"系统。

核心问题：
- Orchestrator 和 SkillOpt / Regression / Validation / HumanReview **零连接**
- 三条分离流水线各自独立运行

解决方案：
- 建立统一闭环：Task → Trace → Eval → Regression → Memory → SkillPatch → Validation → HumanReview → Export
- 新增 SelfImprovementProofLoop 作为桥梁引擎
- 所有新模块通过 `stable_agent.self_improvement` 包统一管理

---

## 已实施变更

### P0: 冗余收敛
- [x] 添加 `@deprecated V6.0` 到 V3 MCP、V4 SkillOpt MCP、旧 approval.py、progress_model.py
- [x] gateway/run_lifecycle.py 标记为 re-export deprecated
- [x] 未使用 JS 文件标记 @deprecated

### P1: 基础设施
- [x] 新建 `stable_agent/memory/` 包: TemporalMemoryRouter + MemoryCandidateStore
- [x] 新建 `stable_agent/context/` 包: ContextCompressionGuard
- [x] 新建 `stable_agent/self_improvement/` 包: ProofLoop + MemoryUpdate + SkillPatch + Report

### P2: Dashboard
- [x] 新建 `run_observer.html` + `run_observer.js` — WebSocket 实时观察页
- [x] 路由注册: `/observe/{run_id}`

---

## 待实施变更

### P3: 集成连接（下一轮）
- [ ] Orchestrator 集成 SelfImprovementProofLoop
- [ ] ToolRouter 事件注入 RunLifecycle progress_pct / why_zh
- [ ] Dashboard V3 使用 RunLifecycle 替代 ProgressModel
- [ ] SkillOptimizationEngine 连接到 ProofLoop

### P4: V3/V4 清理（V7.0）
- [ ] 移除 V3 MCP `/mcp/legacy` 端点
- [ ] 移除 V4 SkillOpt MCP 工具
- [ ] 移除 `approval.py` 旧文件
- [ ] 移除 `progress_model.py`
- [ ] 移除 `gateway/run_lifecycle.py`
- [ ] 删除未使用 JS/CSS 文件

---

## 架构图

```
用户任务输入
    │
    ▼
Orchestrator.process_task()
    │
    ├── ContextDecisionEngine ─── 分类 + 风险
    ├── ContextBudgetManager ─── 预算
    ├── MemoryRouter ─── 记忆检索
    ├── TemporalMemoryRouter ─── 时间记忆 ← NEW
    ├── RAG ─── 知识检索
    ├── ContextCompressionGuard ─── 压缩保护 ← NEW
    │
    ├── WorkflowEngine ─── 执行
    ├── Evaluator ─── 评估
    │
    └── SelfImprovementProofLoop ─── 自优化 ← NEW
         │
         ├── MemoryUpdateCandidate ─── 记忆候选
         ├── SkillPatchCandidate ─── 补丁候选
         ├── Validation ─── 验证
         ├── HumanReview ─── 审核
         └── Export best_skill.md ─── 导出
```

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `stable_agent/memory/__init__.py` | 记忆包入口 |
| 新建 | `stable_agent/memory/temporal_memory_router.py` | 时间记忆路由 |
| 新建 | `stable_agent/memory/memory_candidate.py` | 候选记忆管理 |
| 新建 | `stable_agent/context/__init__.py` | 上下文包入口 |
| 新建 | `stable_agent/context/context_compression_guard.py` | 压缩保护 |
| 新建 | `stable_agent/self_improvement/__init__.py` | 自优化包入口 |
| 新建 | `stable_agent/self_improvement/proof_loop.py` | 闭环引擎 |
| 新建 | `stable_agent/self_improvement/memory_update_candidate.py` | 记忆更新 |
| 新建 | `stable_agent/self_improvement/skill_patch_candidate.py` | 补丁管理 |
| 新建 | `stable_agent/self_improvement/self_improvement_report.py` | 学习报告 |
| 新建 | `web/templates/run_observer.html` | 观察页 |
| 新建 | `web/static/run_observer.js` | 观察页 JS |
| 新建 | `docs/CORE_LOOP_AUDIT.md` | 审计报告 |
| 新建 | `docs/DASHBOARD_SYNC_AUDIT.md` | 同步审计 |
| 新建 | `docs/REDUNDANCY_AUDIT.md` | 冗余审计 |
| 新建 | `docs/IMPLEMENTATION_LOG.md` | 实现日志 |
| 更新 | `stable_agent/mcp_server.py` | +deprecated |
| 更新 | `stable_agent/mcp/skillopt_tools.py` | +deprecated |
| 更新 | `stable_agent/approval.py` | +deprecated |
| 更新 | `stable_agent/observation/progress_model.py` | +deprecated |
| 更新 | `stable_agent/gateway/run_lifecycle.py` | +deprecated |
| 更新 | `stable_agent/run_replay.py` | +deprecated |
| 更新 | `web/static/progress_bar.js` | +deprecated |
| 更新 | `web/static/decision_panel.js` | +deprecated |
| 更新 | `web/static/dashboard_run_client.js` | +deprecated |
| 更新 | `web/static/avatar_scene.js` | Canvas 场景动画 |
| 更新 | `web/routes/dashboard.py` | +observer 路由 |
