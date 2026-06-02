# StableAgent OS Slim Cloud Edition — OpenClaw 部署指南

## 概述

StableAgent OS Slim Cloud Edition 是为 2 核 2G 云服务器优化的轻量版本，
作为 OpenClaw Control Center 运行，负责任务调度、Worker 管理和 Dashboard 展示。

## 架构

```
User / Claude Code / Codex
        ↓
OpenClaw Control Center (云端)
        ↓
Task Queue / Scheduler
        ↓
Local Worker A / Local Worker B (本地电脑)
        ↓
Result / Event / Logs
        ↓
Dashboard / Capsule / Feedback Loop
```

## 服务器配置

- **CPU**: 2 核
- **RAM**: 2GB (MemoryMax=1200M)
- **端口**: 18789
- **绑定**: 127.0.0.1 (仅本地访问，通过 SSH tunnel)
- **数据库**: SQLite
- **Profile**: slim

## 部署步骤

### 1. 一键部署

```bash
# 在本地执行（会复制到服务器）
bash scripts/deploy_openclaw_slim.sh
```

### 2. 启动服务

```bash
# SSH 到服务器
ssh -i "your-key.pem" root@39.97.240.254

# 启动
systemctl start stableagent-openclaw
systemctl status stableagent-openclaw

# 查看日志
journalctl -u stableagent-openclaw -f
```

### 3. 本地 SSH Tunnel

```bash
ssh -fN -i "/Users/Zhuanz/Library/Mobile Documents/com~apple~CloudDocs/lay-ecs-key.pem" \
  -o IdentitiesOnly=yes \
  -o ExitOnForwardFailure=yes \
  -L 18789:127.0.0.1:18789 \
  root@39.97.240.254
```

### 4. 本地访问

打开浏览器访问:

```
http://127.0.0.1:18789/slim
```

### 5. 健康检查

```bash
curl http://127.0.0.1:18789/api/cloud/health
```

预期返回:
```json
{
  "ok": true,
  "profile": "slim",
  "server_role": "control_center",
  "workers_online": 0,
  "queued_tasks": 0,
  "running_tasks": 0,
  "total_events": 0
}
```

## 安全说明

1. **默认绑定 127.0.0.1** — Dashboard 不直接暴露公网
2. **SSH Tunnel** — 通过 SSH 加密隧道访问
3. **可选 Token 认证** — 在 `.env.slim` 中设置 `STABLEAGENT_CLOUD_TOKEN`
4. **Worker API Token** — 如果 Worker 通过公网连接，必须设置 Token

### 启用 Token 认证

编辑 `/opt/os-agent/.env.slim`:

```bash
STABLEAGENT_CLOUD_TOKEN=your-random-token-here
```

重启服务:
```bash
systemctl restart stableagent-openclaw
```

Worker 连接时需要带上 Token:
```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli worker start \
  --server http://127.0.0.1:18789 \
  --worker-id macbook_pro \
  --token your-random-token-here
```

## MCP 接入

### HTTP MCP (推荐)

在 Claude Code / Codex / Trae 中配置:

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://127.0.0.1:18789/mcp"
    }
  }
}
```

### CLI 调用

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "你的任务描述" \
  --port 18789 \
  --json
```

## 配置参考

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `STABLEAGENT_PROFILE` | `slim` | 运行 profile |
| `STABLEAGENT_PORT` | `18789` | 服务端口 |
| `STABLEAGENT_BIND_HOST` | `127.0.0.1` | 绑定地址 |
| `STABLEAGENT_MAX_EVENTS` | `1000` | 最大事件数 |
| `STABLEAGENT_MAX_TASK_LOGS` | `200` | 每任务最大日志数 |
| `STABLEAGENT_WORKER_TIMEOUT` | `60` | Worker 超时秒数 |
| `STABLEAGENT_CLOUD_TOKEN` | (空) | API Token |
