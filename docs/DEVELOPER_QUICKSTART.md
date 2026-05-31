# V11 Agent Capsule

## 什么是 Agent Capsule？

Agent Capsule 是面向 Vibe Coding 用户的可迁移 AI 使用层外接工具。它通过 MCP 接入 Codex / Claude Code / Cursor / Cline 等 AI Coding 工具，把用户的长期偏好、项目记忆、工作流规则、失败经验、模型适配策略、表达习惯和个人评测标准沉淀为本地可迁移胶囊。

## 为什么不是训练模型权重？

Agent Capsule 不训练模型，而是：
- **记忆层**：保存你的偏好、项目事实、工作流规则
- **理解层**：学习你的表达习惯，减少语义误解
- **评测层**：用你的标准验证 AI 输出质量
- **适配层**：给不同模型加载不同 adapter

## 安装

```bash
git clone https://github.com/liuanye9-lab/OS-Agent.git
cd OS-Agent
pip install -r requirements.txt
```

## 初始化胶囊

```bash
python -m stable_agent.cli capsule init
```

## 启动服务

```bash
uvicorn web.server:app --host 0.0.0.0 --port 8000
```

## 接入 MCP

在你的 AI Coding 工具配置中添加：

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 导入导出胶囊

```bash
# 导出
python -m stable_agent.cli capsule export my_capsule.zip

# 导入
python -m stable_agent.cli capsule import my_capsule.zip --target ./.stableagent-capsule
```

## 查看 token 节省

```bash
python -m stable_agent.cli token summary --days 7
```

## 记忆体检

```bash
python -m stable_agent.cli memory health
```

## 使用"下次别这样"

通过 MCP 调用：
```json
{
  "tool": "stableagent.feedback.dont_do_this_again",
  "arguments": {
    "run_id": "run_xxx",
    "user_note": "不要大范围重构"
  }
}
```

## CLI 命令

```bash
python -m stable_agent.cli capsule init      # 初始化胶囊
python -m stable_agent.cli capsule status    # 查看状态
python -m stable_agent.cli capsule doctor    # 健康检查
python -m stable_agent.cli capsule export    # 导出为 ZIP
python -m stable_agent.cli capsule import    # 从 ZIP 导入
python -m stable_agent.cli memory health     # 记忆健康报告
python -m stable_agent.cli token summary     # Token 使用摘要
python -m stable_agent.cli mcp config        # 输出 MCP 配置
```
