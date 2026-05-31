# AGENTS.md — StableAgent OS Default Calling Rules

> 适用于所有接入 StableAgent OS 的 AI Coding Agent（Claude Code / Cursor / Codex / Trae 等）。

## 核心规则

在执行**任何非平凡的编码任务**之前，**必须先调用** `stableagent.task.os_agent`。

### 什么是"非平凡"？

满足以下任一条件即视为非平凡任务：
- 需要修改 ≥ 2 个文件
- 涉及架构决策、API 设计、数据模型变更
- 需要引入新的依赖或配置
- 需要理解项目全局上下文（跨模块、跨服务）
- 风险较高的操作（删除、重构、迁移）

### 可以直接执行的任务（无需调用 os_agent）

- 单行修复（拼写错误、格式调整）
- 读取单个文件并回答简单问题
- 运行已知的测试命令
- 执行 git 操作（status、log、diff）

## 调用方式

```json
{
  "method": "tools/call",
  "params": {
    "name": "stableagent.task.os_agent",
    "arguments": {
      "task": "任务描述",
      "context": "相关上下文信息"
    }
  }
}
```

## 返回处理

os_agent 返回结果后：
1. 解析 `result` 字段获取建议方案
2. 如建议包含风险评估，需确认后再执行
3. 如建议标记为 `requires_human_review`，停止并请求人工审批
4. 执行完成后，将结果回传给 os_agent 用于效果评估

## 效果评估数据回传

每次任务完成后，调用 os_agent 记录效果数据：

```json
{
  "method": "tools/call",
  "params": {
    "name": "stableagent.task.os_agent",
    "arguments": {
      "action": "record_effectiveness",
      "task_id": "任务标识",
      "mode": "stableagent | baseline",
      "success": true,
      "edits_made": 5,
      "tokens_used": 12000,
      "intent_drift": 0
    }
  }
}
```
