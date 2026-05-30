# DASHBOARD_OBSERVER_SPEC.md — 解释型可视化面板规范

**版本**: V8.1 | **文件**: `web/templates/run_observer.html`, `web/static/run_observer.js`, `web/static/avatar_scene.js`

---

## 5 区域布局

```
┌──────────────────────────────────────────────────────┐
│ Top Bar: 任务名 | run_id | MCP 状态 | 总进度        │
├───────────┬──────────────────────┬───────────────────┤
│ Left      │ Center               │ Right             │
│ Canvas    │ 状态卡片              │ DecisionTrace     │
│ 像素人    │ 现在: 找时间记忆     │ 时间线            │
│ 语义场景  │ 为什么: 防丢约束     │                   │
│           │ 依据: 5条记忆        │                   │
│           │ 下一步: 压缩上下文   │                   │
│           │ 进度: 28%            │                   │
├───────────┴──────────────────────┴───────────────────┤
│ Bottom: SelfImprovementReport + Eval + Review        │
└──────────────────────────────────────────────────────┘
```

## 核心原则

| 规则 | 说明 |
|------|------|
| 前端只消费后端事件 | 通过 WebSocket SSE 订阅 |
| 不猜进度 | `progress_pct` 来自 `event.progress_pct` |
| 不伪造状态 | `avatar_state` 来自 `event.avatar_state` |
| 日志默认折叠 | JSON/原始事件不展开 |
| 浅色玻璃拟态 | CSS 变量驱动，流动背景动画 |

## 像素人场景映射

Canvas 渲染 `avatar_scene.js`，由 `avatar_state` 驱动：

| avatar_state | scene | labelZh | prop |
|-------------|-------|---------|------|
| listening | desk | 接收任务 | task_card |
| thinking | thinking_board | 理解需求 | magnifier |
| calculating | budget_panel | 计算预算 | abacus |
| reading_notes | memory_wall | 找时间记忆 | memory_cards |
| searching_books | library | 查项目资料 | books |
| organizing | context_table | 压缩上下文 | context_blocks |
| planning | map_table | 规划步骤 | route_map |
| tooling | tool_bench | 调用工具 | wrench |
| watching | monitor | 观察结果 | screen |
| grading | exam_table | 评估结果 | score_sheet |
| diagnosing | diagnosis_board | 分析失败 | warning_card |
| writing_case | case_desk | 生成错题 | case_file |
| learning | skill_book | 提出改法 | skill_patch |
| waiting_approval | approval_gate | 等待审核 | red_card |
| archiving | archive_cabinet | 导出规则 | best_skill |
| done | delivery_desk | 完成任务 | checkmark |
| failed | error_board | 任务失败 | error_sign |
| idle | desk | 空闲 | coffee |

## 事件字段（后端 → 前端）

每个事件必须包含：
```json
{
  "run_id": "...",
  "stage": "temporal_memory_retrieving",
  "stage_label_zh": "找时间记忆",
  "progress_pct": 28,
  "avatar_state": "reading_notes",
  "decision_summary_zh": "上下文压缩可能丢失关键历史约束",
  "why_zh": "需要按时间戳找相关记忆",
  "next_step_zh": "压缩上下文",
  "evidence": ["5条记忆", "3条来自OS-Agent调试"],
  "risk_level": "low"
}
```

## 禁止字段

前端绝不展示：
- `chain_of_thought`
- `hidden_reasoning`
- `model_inner_thought`

## 状态卡片格式

```
现在：找时间记忆
为什么：压缩上下文前需要找最近相关经验，避免丢掉关键约束。
依据：召回 5 条相关记忆，其中 3 条来自最近 OS-Agent 调试。
下一步：压缩上下文。
进度：28%
```
