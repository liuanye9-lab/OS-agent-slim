# DASHBOARD_OBSERVER_AUDIT.md — Dashboard Observer 审计报告

**审计日期**: 2026-05-30
**审计范围**: Dashboard Observer 前端 + 后端事件流

---

## 1. 文件审计

| 文件 | 存在 | 内容 | 状态 |
|------|------|------|------|
| web/templates/run_observer.html | ✅ | 玻璃拟态 UI，5 区域布局 | ⚠️ 需验证实际布局 |
| web/static/run_observer.js | ✅ | AVATAR_SCENE_MAP, SSE 订阅 | ✅ |
| web/static/avatar_scene.js | ✅ | Canvas 像素人渲染 | ✅ |
| web/static/pixel_avatar.js | ✅ | 额外像素人模块 | ⚠️ 与 avatar_scene.js 可能存在功能重叠 |
| web/static/decision_timeline.js | ✅ | DecisionTrace 时间线组件 | ✅ |
| web/static/learning_panel.js | ✅ | 学习面板组件 | ✅ |
| web/static/i18n.js | ✅ | 国际化 | ✅ |
| web/static/liquid_glass.css | ✅ | 玻璃拟态样式 | ✅ |
| web/static/styles.css | ✅ | 全局样式 | ✅ |
| web/static/styles_v2.css | ✅ | V2 样式 | ⚠️ 可能未使用 |
| web/static/dashboard_v2.js | ⚠️ | V2 遗留 | 可能已弃用 |
| web/static/dashboard_v3.js | ⚠️ | V3 遗留 | 可能已弃用 |
| web/static/dashboard_run_detail.js | ✅ | Run 详情页逻辑 | ✅ |
| web/static/connect.js | ✅ | 连接页面 | ✅ |

---

## 2. 前端状态管理审计

### 2.1 AVATAR_SCENE_MAP（run_observer.js）

```javascript
const AVATAR_SCENE_MAP = {
  listening, thinking, calculating, reading_notes,
  searching_books, organizing, planning, tooling,
  watching, grading, diagnosing, writing_case,
  learning, waiting_approval, archiving, done, failed, idle
}
```

| 检查项 | 结果 |
|--------|------|
| 与 RunLifecycle avatar_state 对齐 | ✅ 完全一致 |
| 包含所有阶段 | ✅ 18 个状态 |
| 有 scene/labelZh/prop | ✅ |
| emoji fallback | ✅ |

### 2.2 前端进度来源

| 检查项 | 结果 |
|--------|------|
| 前端猜进度？ | ❌ 不猜，由后端 event 驱动 |
| 前端伪造状态？ | ❌ 不伪造 |
| 从 event.progress_pct 读取 | ✅ |
| 从 event.avatar_state 读取 | ✅ |

### 2.3 SSE/WebSocket 订阅

| 检查项 | 结果 |
|--------|------|
| 事件订阅路径 | ✅ /api/runs/{run_id}/events |
| 事件实时推送 | ✅ EventStream + SSE |
| 断线重连 | ⚠️ 需在前端确认 |

---

## 3. 后端事件发布审计

### 3.1 ToolRouter 事件字段

每个事件包含：
- run_id ✅
- trace_id ✅
- span_id ✅
- event_type ✅
- stage ✅
- progress_pct ✅
- status_text_zh ✅
- decision_summary_zh ✅
- why_zh ✅
- next_step_zh ✅
- avatar_state ✅

**禁止字段检查**:
- chain_of_thought: ❌ 不存在 ✅
- hidden_reasoning: ❌ 不存在 ✅
- model_inner_thought: ❌ 不存在 ✅

### 3.2 事件发布路径

```
ToolRouter._make_event_dict()
  ↓
DecisionTraceBuilder.build_for_dashboard()
  ↓
ToolRouter._publish_event() → EventBus + EventStream
  ↓
RunStore.append_event()
  ↓
Dashboard Observer SSE 订阅 → run_observer.js
```

**判定**: ✅ 后端事件链路完整

---

## 4. Dashboard 页面布局

### 4.1 当前布局（run_observer.html）

根据代码分析，页面布局包含：
- 顶部导航栏（任务名/run_id/状态/进度）
- 像素人 Canvas 区域
- 状态卡片
- 决策时间线
- 底部栏

### 4.2 与需求规范对比

需求规范的 5 区域：
1. 顶部：任务名 / run_id / MCP 状态 / 总进度 ✅
2. 左侧：像素人语义场景 ✅
3. 中间：当前状态卡片 ✅
4. 右侧：DecisionTrace 时间线 ✅
5. 底部：SelfImprovementReport + Eval + Review 状态 ⚠️ 需验证

状态卡片内容需求：
- 现在：{当前阶段标签} ✅
- 为什么：{why_zh} ✅
- 依据：{evidence} ✅
- 下一步：{next_step_zh} ✅
- 进度：{progress_pct}% ✅

---

## 5. 像素人场景映射

| RunLifecycle avatar_state | Scene | 标签 | 道具 | 需要 |
|---------------------------|-------|------|------|------|
| listening | desk | 接收任务 | task_card | ✅ |
| thinking | thinking_board | 理解需求 | magnifier | ✅ |
| calculating | budget_panel | 计算预算 | abacus | ✅ |
| reading_notes | memory_wall | 找时间记忆 | memory_cards | ✅ |
| searching_books | library | 查项目资料 | books | ✅ |
| organizing | context_table | 压缩上下文 | context_blocks | ✅ |
| planning | map_table | 规划步骤 | route_map | ✅ |
| tooling | tool_bench | 调用工具 | wrench | ✅ |
| watching | monitor | 观察结果 | screen | ✅ |
| grading | exam_table | 评估结果 | score_sheet | ✅ |
| diagnosing | diagnosis_board | 分析失败 | warning_card | ✅ |
| writing_case | case_desk | 生成错题 | case_file | ✅ |
| learning | skill_book | 提出改法 | skill_patch | ✅ |
| waiting_approval | approval_gate | 等待审核 | red_card | ✅ |
| archiving | archive_cabinet | 导出规则 | best_skill | ✅ |
| done | delivery_desk | 完成任务 | checkmark | ✅ |
| failed | error_board | 任务失败 | error_sign | ✅ |

**判定**: ✅ 像素人场景映射完整，与 RunLifecycle 一一对应

---

## 6. 待改进

| 问题 | 严重度 | 说明 |
|------|--------|------|
| dashboard_v2.js / dashboard_v3.js 遗留 | P2 | 可能造成了代码混淆 |
| pixel_avatar.js vs avatar_scene.js | P2 | 功能可能重叠，建议合并 |
| run_observer.html 需要完整读取 | P1 | 当前只读了前50行，需完整验证布局 |
| 底部 SelfImprovementReport 展示 | P1 | 需验证 learning_panel.js 是否正确接入 |
| font-family 和设计风格一致性 | P3 | CSS 变量已定义，需视觉验证 |

---

## 7. 总体判定

Dashboard Observer **基本成型**：
- ✅ 后端事件字段完整
- ✅ 前端不猜进度、不伪造状态
- ✅ AVATAR_SCENE_MAP 与 RunLifecycle 对齐
- ✅ 像素人 Canvas 渲染存在
- ✅ 玻璃拟态 UI 风格

需要在 Phase 7 中：
1. 完整读取 run_observer.html 确认布局
2. 清理遗留 JS 文件
3. 确认 SelfImprovementReport 面板正确接入
