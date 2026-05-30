# CLOSED_LOOP_REFACTOR_PLAN.md — 闭环重构计划

基于 `CLOSED_LOOP_AUDIT.md`（审计日期 2026-05-30，1083 passed / 0 failures）。

## 已连接链路（审计确认）

```
用户/MCP Client                     ✅ MCP tools/call
    ↓
MCP Gateway → UnifiedToolRegistry   ✅ stableagent.task.os_agent
    ↓
RunLifecycle 状态创建                ✅ ToolRouter → RunContext
    ↓
TemporalMemoryRouter 时间召回        ✅ Orchestrator 步骤 6.5
    ↓
ContextCompressionGuard 防降智       ✅ Orchestrator 步骤 6.5（6层保护）
    ↓
Orchestrator 17步 process_task      ✅ 全流程
    ↓
TraceEvent 执行记录                  ✅ ToolRouter._make_event_dict
    ↓
DecisionTraceBuilder 可解释状态     ✅ 从 RunLifecycle 读取
    ↓
Dashboard Observer 实时显示          ✅ /runs/{id} WebSocket SSE
    ↓
Eval → Failure Attribution          ✅ _attribute_failure
    ↓
BadCase → Regression Case            ✅ _generate_regression_cases + 持久化
    ↓
Memory Update Candidate              ✅ _generate_memory_candidates (CANDIDATE 状态)
    ↓
Skill Patch Candidate                ✅ _generate_skill_patches
    ↓
RegressionValidationRunner 验证      ✅ validate_patch (规则 + LLM 混合)
    ↓
Human Review 审核                    ✅ HumanReviewQueue + approve_patch
    ↓
Export best_skill.md                 ✅ _export_best_skill_versioned (带版本归档)
```

## 本轮 3 项代码变更

### (a) 移除 `_generate_skill_patches` 中的自动推进状态线

- **文件**: `stable_agent/self_improvement/proof_loop.py` line 614–618
- **旧行为**: 生成 patch 后自动调用 `start_validation → mark_validated → submit_for_review`
- **新行为 (V8.0)**: 不自动推进状态线。验证由 `evaluate_and_learn()` 中的 `RegressionValidationRunner.validate_patch()` 驱动，审核由 `HumanReviewQueue` 守卫
- **注释已更新**: `# V8.0: 不自动推进状态线...旧行为：start_validation → mark_validated → submit_for_review（已移除）`

### (b) 添加 Canvas 像素头像渲染

- **文件**: `web/static/avatar_scene.js` (新增)
- **功能**: 将 17 种 `avatar_state` 映射为 Canvas 像素画渲染
  - `SCENE_CONFIGS` 定义每个场景的背景色、道具 emoji、mood
  - `drawCharacter()` 根据 mood 渲染不同表情（头、眼、嘴、身）
  - `renderAvatarScene(state, canvasId)` 为公开 API
- **集成**: `run_observer.js` 的 `updateAvatar()` 调用 `renderAvatarScene(info.scene, "avatarCanvas")`
- **HTML**: `<canvas id="avatarCanvas" width="220" height="220">` 替换了旧 text label

### (c) 确认 RunLifecycle 为唯一状态源

- **文件**: `stable_agent/runtime/run_lifecycle.py`
- **审计确认** (CLOSED_LOOP_AUDIT.md section 1):
  - 8 个阶段完整（TEMPORAL_MEMORY_RETRIEVING → COMPLETED）
  - 每个阶段有 `progress_pct`（0→100 统一分配）
  - 每个阶段有 `status_text_zh`、`avatar_state`、`scene`
  - 每个阶段有 `default_why_zh` + `next_step_zh`
  - 被 `DecisionTraceBuilder` 和 `ToolRouter` 真实调用
  - 无 stub/TODO/pass，无静默失败
- **前端依赖**: `run_observer.js` 的 `applyEvent()` 从 `evt.progress_pct` 和 `evt.avatar_state` 读取，不做本地推算

## 审计揭示的剩余风险（P1/P2/P3）

| 风险 | 严重度 | 说明 | 状态 |
|------|--------|------|------|
| Orchestrator 中 TemporalMemory/CompressionGuard 静默 catch | P1 | 异常只记录 warning，不阻断主流程 | 有意为之的优雅降级 |
| `validation_passed = True` 初始值 | P2 | 语义正确（会被动态覆盖），check_closed_loop.py 已通过检查 | 已确认 |
| `_generate_skill_patches` 自动推进状态 | P2 | 已在本轮修复 (V8.0) | **已解决** |
| WorkflowStateMachine._step_learn 有 STUB 标记 | P3 | 核心学习已移至 Orchestrator，不阻塞主流程 | 低优先级 |
| ToolRouter line 141 except: pass | P3 | 非关键 RunLifecycle 注入失败 | 低优先级 |

## 测试覆盖

全部 1083 tests passed，0 failures。关键测试文件:
- `test_run_lifecycle.py`
- `test_temporal_memory_router.py`
- `test_context_compression_guard.py`
- `test_self_improvement_proof_loop.py`
- `test_regression_validation_runner.py`
- `test_validation_report.py`
- `test_decision_trace_builder.py`
- `test_tool_router_events.py`
- `test_avatar_scene_mapping.py`
- `test_dashboard_run_detail.py`

## 闭环检查命令

```bash
python tools/check_closed_loop.py
# 期望: [PASS] Closed-loop structural checks completed.
```
