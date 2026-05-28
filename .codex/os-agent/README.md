# OS Agent — Codex 快捷接入

将 StableAgent OS 接入 Codex，通过 `/os-agent` 启动自优化工作流。

## 快速开始

```bash
# 1. 启动服务
cd "/Users/Zhuanz/Documents/OS agent"
uvicorn web.server:app --host 127.0.0.1 --port 8000

# 2. 在 Codex 中配置 MCP
# 复制 mcp_config.example.json 到 Codex 配置

# 3. 使用
# 在 Codex 中输入: /os-agent 分析项目架构
```
