# DASHBOARD_OBSERVER_REFACTOR_PLAN.md — Dashboard Observer 重构计划

**日期**: 2026-05-30

---

## 重构目标

将 Dashboard Observer 升级为真正的 **后端事件驱动、可解释、极简、非技术用户可理解** 的可视化面板。

## 已完成改进

### 1. Canvas 像素人渲染
- **Before**: emoji fallback (`$avatarScene.textContent = emoji`)
- **After**: `renderAvatarScene(scene, "avatarCanvas")` — Canvas 像素人
- **文件**: `run_observer.html` (+canvas element, +avatar_scene.js), `run_observer.js`

### 2. 日志默认折叠
- 事件日志/JSON 默认折叠（`.log-panel { display: none }`）
- 用户点击 "📋 事件日志" 按钮展开

### 3. 流动背景渐变
- CSS `@keyframes bgFlow` 20s 循环
- 玻璃拟态 UI: `backdrop-filter: blur(24px) saturate(180%)`

### 4. 5 区域布局确认
| 区域 | 元素 | 状态 |
|------|------|------|
| Top Bar | task_name, run_id, MCP status, progress bar | ✅ |
| Left | Canvas avatar, scene label, prop | ✅ |
| Center | Status card (now/why/evidence/next/progress) | ✅ |
| Right | Decision timeline | ✅ |
| Bottom | SelfImprovementReport + Eval + Review | ✅ |

### 5. 事件驱动架构确认
- 前端通过 WebSocket SSE 订阅: `ws://host/dashboard-sync/ws/runs/{run_id}`
- `applyEvent()` 处理每个事件: progress → avatar → status card → timeline → SI report
- 前端永不自算进度

## 涉及文件

| 文件 | 变更 |
|------|------|
| `web/templates/run_observer.html` | Canvas avatar element, avatar_scene.js 引入, 样式调整 |
| `web/static/run_observer.js` | updateAvatar 调用 renderAvatarScene, DOM ref 更新 |
| `web/static/avatar_scene.js` | 无变更（已存在） |
