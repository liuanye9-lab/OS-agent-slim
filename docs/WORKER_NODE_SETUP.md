# Worker 节点设置指南

## 概述

Worker 运行在你的本地电脑上，向云端 OpenClaw Control Center 注册、
心跳、拉取任务并执行。

## 前置条件

1. Python 3.11+
2. 项目代码已 clone
3. `.venv` 已创建并安装依赖
4. 能访问云端 Control Center (直接或通过 tunnel)

## 电脑 A: MacBook Pro

```bash
cd /path/to/OS-Agent

# 确保云端服务已启动（通过 SSH tunnel 或直接访问）
# 如果云端在 localhost:18789 (通过 tunnel):

PYTHONPATH=. .venv/bin/python -m stable_agent.cli worker start \
  --server http://127.0.0.1:18789 \
  --worker-id macbook_pro \
  --name "Lay MacBook Pro" \
  --machine-type macos \
  --capability coding \
  --capability shell \
  --poll-interval 5
```

## 电脑 B: Desktop PC

```bash
cd /path/to/OS-Agent

PYTHONPATH=. .venv/bin/python -m stable_agent.cli worker start \
  --server http://127.0.0.1:18789 \
  --worker-id desktop_pc \
  --name "Desktop PC" \
  --machine-type linux \
  --capability coding \
  --capability browser \
  --capability shell \
  --poll-interval 5
```

## 如果两台电脑不在同一网络

推荐方案 (按复杂度排序):

1. **SSH Reverse Tunnel** — 最简单
   ```bash
   # 在本地电脑上:
   ssh -R 18789:127.0.0.1:18789 root@39.97.240.254
   ```

2. **Tailscale** — 零配置 VPN
   - 安装: https://tailscale.com
   - 两台电脑加入同一 tailnet
   - 使用 Tailscale IP 访问

3. **ZeroTier** — 类似 Tailscale
   - 安装: https://www.zerotier.com

4. **Cloudflare Tunnel** — 企业级
   - 需要域名

## 安全模式

### 默认模式 (dry-run)

默认情况下，Worker 不会真正执行 shell 命令，只记录和返回 dry-run 结果。

### 启用 Shell 执行

```bash
export STABLEAGENT_WORKER_ALLOW_SHELL=1

PYTHONPATH=. .venv/bin/python -m stable_agent.cli worker start \
  --server http://127.0.0.1:18789 \
  --worker-id macbook_pro \
  --allow-shell \
  --capability coding \
  --capability shell
```

### 安全白名单

即使启用 shell，以下命令也会被拒绝:
- `rm -rf /`
- `sudo`
- `shutdown` / `reboot`
- `mkfs`
- `chmod -R 777 /`
- `curl | sh`

允许的命令:
- `pwd`, `ls`, `cat`
- `git status`, `git diff`, `git log`
- `npm test`, `npm run build`
- `pytest`, `python -m pytest`

## 验证 Worker 连接

### 从 Worker 端

Worker 启动后会自动:
1. 注册到云端
2. 每隔 poll_interval 发送心跳
3. 等待任务

### 从 Dashboard

访问 `http://127.0.0.1:18789/slim`，查看 Worker Panel 是否显示你的 Worker。

### 从 CLI

```bash
# 列出 Workers
PYTHONPATH=. .venv/bin/python -m stable_agent.cli worker list --port 18789 --json

# 健康检查
PYTHONPATH=. .venv/bin/python -m stable_agent.cli cloud health --port 18789 --json
```

## 带 Token 认证

如果云端设置了 `STABLEAGENT_CLOUD_TOKEN`:

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli worker start \
  --server http://127.0.0.1:18789 \
  --worker-id macbook_pro \
  --token your-token-here \
  --capability coding \
  --capability shell
```
