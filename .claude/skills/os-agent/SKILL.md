---
name: os-agent
description: 启动 StableAgent OS 自优化工作流，每次执行都会在 Dashboard 实时展示 Agent 在做什么、为什么、进度多少
disable-model-invocation: true
---

# OS Agent Skill

当用户输入 `/os-agent` 时：

1. 检查 StableAgent OS 是否在 `http://localhost:8000` 运行（如未运行，告诉用户运行 `bash install.sh`）
2. 调用 MCP 工具: `stableagent.task.os_agent`，参数: `{"task_input": "$ARGUMENTS"}`
3. 读取返回的 `run_id` 和 `dashboard_url`
4. 回复用户:

```
OS Agent 已启动

任务: $ARGUMENTS
运行 ID: {run_id}
当前阶段: {current_stage}
进度: {progress_pct}%
状态: {status_text_zh}

打开 Dashboard 查看实时进度:
→ {dashboard_url}
```

5. 不要暴露内部推理链，只展示可观察决策摘要
6. 如果 `$ARGUMENTS` 为空，询问用户想要执行什么任务
