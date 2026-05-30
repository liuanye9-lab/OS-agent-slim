# CHANGELOG.md

All notable changes to StableAgent OS — AI 降智防御系统.

---

## V8.1 (2026-05-30) — Phase 1-9 闭环硬化

### Added
- `tools/check_closed_loop.py` — 闭环完整性自动检查脚本（审计 → 判定）
- `tools/integration_test.py` — 端到端集成测试自动化
- `scripts/deploy_local.sh` — 一键本地部署（venv + pip + uvicorn）
- `scripts/integration_test.sh` — 集成测试脚本
- `scripts/smoke_test.sh` — 冒烟测试脚本
- Canvas 像素人 17 场景语义渲染（`avatar_scene.js`），替换 emoji 回退
- 完整文档套件: CLOSED_LOOP_AUDIT, DASHBOARD_OBSERVER_AUDIT, DEPLOYMENT_TEST_AUDIT, PRODUCTION_CODE_AUDIT, etc.

### Changed
- `_generate_skill_patches` 不再自动推进状态线（移除 start_validation → mark_validated → submit_for_review 自动链），合规
- 日志面板默认折叠（`toggleLog()` 控制），优化 Dashboard 首屏
- 流体渐变背景（`bgFlow` 20s 动画）

### Fixed
- P1: WorkflowStateMachine._step_learn STUB 标记（已审计，核心逻辑移至 Orchestrator）
- P2: 验证 `except Exception: pass` 已清理至 1 处（ToolRouter L141，非关键）
- P2: 确认 validation_passed 动态覆盖逻辑正确（初始 True → 失败时正确设为 False）

### Verified
- 1083 tests passing, 0 failures
- 闭环 14 环节全部打通（审计报告 CLOSED_LOOP_AUDIT §12）
- Dashboard 事件驱动架构确认有效（DASHBOARD_OBSERVER_AUDIT §3）

---

## V7.1 (2026-05-30) — Review API + 飞书通知 + Best Skill 版本化

### Added
- Human Review API 端点: `/api/reviews` (list/approve/reject)
- 飞书消息通知集成（审核通过/拒绝时通知）
- `best_skill.md` 版本化管理（`_export_best_skill_versioned` 带时间戳）
- `HumanReviewQueue` 正式类（V6.3 内联逻辑 → 独立模块）

### Changed
- Skill Export 逻辑: 审批通过后自动导出版本化 best_skill.md
- 审核队列状态流: pending → under_review → approved/rejected

---

## V7.0 (2026-05-30) — 物理清理

### Removed
- `stable_agent/observation/progress_model.py` — 已由 RunLifecycle 统一接管
- `stable_agent/gateway/run_lifecycle.py` — 已迁移至 `stable_agent/runtime/run_lifecycle.py`
- V3/V4 MCP 遗留代码（MCP Gateway V5 为唯一入口）

### Changed
- `_STAGE_MAP` 从 7 项扩展到 40+ 项精确映射
- obsolete modules 引用全部更新到新路径

---

## V6.3 (2026-05-30) — HumanReviewQueue + Best Skill 自动导出

### Added
- `HumanReviewQueue` — 人工审核队列（pending / approved / rejected 状态机）
- `best_skill.md` 自动导出: `_export_best_skill_versioned`
- `WorkflowStateMachine._step_retrieve_knowledge`: STUB `[]` → 真实 RAG 检索
- `stableagent.skill.patch_review` MCP 工具

### Changed
- Human Review 不再绕过 best_skill.md 导出
- Skill Patch 冻结时间戳，不可修改已审核通过的 patch

---

## V6.2 (2026-05-30) — Dashboard 收敛 + LLM 校验

### Added
- Dashboard RunObserver 页面 (`run_observer.html` + `run_observer.js`)
- WebSocket 实时事件推送 (`/dashboard-sync/ws/runs/{run_id}`)
- LLM 校验模式: 评估输出对 Skill Patch 的真实验证

### Removed
- V3 Dashboard 页面
- V4 MCP 旧端点

### Changed
- Dashboard 从多版本（V2/V3）收敛为单一 RunObserver
- LLM Validation: rule_weight=0.3 + llm_weight=0.7 混合评分

---

## V6.1 (2026-05-30) — TemporalMemoryBridge + ContextCompressionGuard + RegressionValidation

### Added
- `TemporalMemoryBridge` — 连接旧 MemoryRouter 到新 TemporalMemoryRouter（记忆迁移）
- `ContextCompressionGuard` — 6 层保护策略 + `enforce_budget()` 预算强制执行
- `RegressionValidationRunner` — 规则 + LLM 混合回归验证（取代硬置 validation_passed=True）
- `ValidationReport` + `ValidationCaseResult` — 结构化验证报告
- 28 个新测试

### Changed
- RunLifecycle: 20 → 22 阶段（新增 TEMPORAL_MEMORY_RETRIEVING, CONTEXT_COMPRESSING, MEMORY_UPDATE_CANDIDATE）
- Orchestrator: 步骤 6.5 注入 TemporalMemory + CompressionGuard
- `RunStageMeta`: 新增 scene 字段（像素人场景渲染）

### Fixed
- P0: 3 处 `except Exception: pass` 全部替换为 logger.exception
- P0: validation_passed 无条件硬置 True → 真实验证
- P1: Orchestrator run_id 未定义 bug

---

## V6.0 及之前

参见 git log 或旧版 `docs/changelogs/`。
