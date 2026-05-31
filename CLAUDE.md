# CLAUDE.md — StableAgent OS Calling Rules for Claude Code

> 当你（Claude Code）作为 Coding Agent 接入 StableAgent OS 时，遵守以下规则。

## 核心规则

在执行**任何非平凡的编码任务**之前，**必须先调用** `stableagent.task.os_agent`。

### 调用流程

1. **任务理解**：理解用户请求
2. **调用 os_agent**：将任务描述和上下文传给 os_agent 获取建议
3. **执行建议**：按照 os_agent 返回的建议执行
4. **结果回传**：将执行结果回传给 os_agent 用于效果评估

### 何时需要调用

需要调用的场景：
- 修改 ≥ 2 个文件
- 涉及架构决策、API 设计、数据模型变更
- 引入新依赖或配置
- 需要理解项目全局上下文
- 高风险操作（删除、重构、迁移）

可直接执行的场景：
- 单行修复（拼写、格式）
- 读取文件回答简单问题
- 运行已知测试命令
- git 操作

### 效果评估回传格式

```json
{
  "action": "record_effectiveness",
  "task_id": "<unique-task-id>",
  "mode": "stableagent",
  "success": true,
  "edits_made": <count>,
  "tokens_used": <count>,
  "intent_drift": <0-1>
}
```
