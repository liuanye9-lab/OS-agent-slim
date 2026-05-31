# V11.1 Production Wiring

## 概述

V11.1 将 V11 Agent Capsule 后端能力真正接入 os_agent 主流程、API 路由和 Dashboard 前端。

## 核心变更

### 1. os_agent 主流程接入

在 `_h_task_os_agent` 中新增两个可选事件（不破坏 V10 必需事件链）：

- `understanding.trace.created` — 在 task.received 后立即生成语义理解轨迹
- `token.budget.estimated` — 在 context.compression_guard.checked 后记录 token 预算

### 2. V11 API 路由

Run 级 API：
- `GET /api/runs/{run_id}/understanding` — 语义理解轨迹
- `GET /api/runs/{run_id}/token` — Token 预算报告
- `GET /api/runs/{run_id}/learning` — 自我优化事件
- `GET /api/runs/{run_id}/badcases` — 失败案例

全局 API：
- `GET /api/token/summary?days=7` — Token 使用摘要
- `GET /api/capsule/status` — 胶囊状态
- `GET /api/memory/health` — 记忆健康报告
- `POST /api/feedback/remember` — 记住这个
- `POST /api/feedback/dont-do-this-again` — 下次别这样
- `POST /api/feedback/correct-and-remember` — 纠正并记住

### 3. Dashboard V11 六大面板

在 run_observer.html 中新增六个面板：
1. **理解轨迹** — 用户原话、系统理解、假设、保护约束、不确定点
2. **Token 预算** — baseline/injected/saved tokens、saving ratio、risk level
3. **记忆地图** — 记忆统计
4. **失败案例库** — 本次记录的失败案例
5. **Skill 进化** — 学习触发、回归用例、验证状态
6. **记忆健康** — 保留/合并/删除建议

### 4. 反馈三按钮

在 Dashboard 中新增三个按钮：
- 记住这个 → POST /api/feedback/remember
- 下次别这样 → POST /api/feedback/dont-do-this-again
- 纠正并记住 → POST /api/feedback/correct-and-remember

## 安全约束

- V10 必需事件链 13 个不变
- V11 事件为可选事件，不在 REQUIRED_NORMAL_EVENTS 中
- SemanticInterpreter 异常时降级继续执行
- Token Budget 写入失败时降级继续执行
- 反馈不会直接写 best_skill.md
