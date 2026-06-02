# OPENCLAW_SKILLOS_SLIM_DEPLOYMENT.md — OpenClaw Slim 部署指南

## 1. 2 核 2GB 运行建议

**推荐配置**：
- CPU: 2 核
- 内存: 2GB
- 存储: 20GB SSD
- OS: Ubuntu 22.04 LTS

**资源限制**：
- 进程内存上限: 1.5GB
- 不运行本地大模型
- 不运行 Docker Compose
- 不运行 npm run dev

## 2. 环境变量

```bash
# .env
STABLEAGENT_PROFILE=slim
STABLEAGENT_ENABLE_SKILL_REPO=true
STABLEAGENT_ENABLE_SKILL_LLM_JUDGE=false
STABLEAGENT_ENABLE_GROUPED_REPLAY=true
STABLEAGENT_ENABLE_HEAVY_RL=false
STABLEAGENT_ENABLE_SKILL_DASHBOARD=true
STABLEAGENT_MAX_ACTIVE_SKILLS=200
STABLEAGENT_MAX_SKILL_VERSIONS=20
STABLEAGENT_SKILL_TOP_K=5
```

## 3. systemd 配置

```ini
# /etc/systemd/system/stableagent.service
[Unit]
Description=StableAgent OS Slim
After=network.target

[Service]
Type=simple
User=agent
Group=agent
WorkingDirectory=/opt/os-agent
EnvironmentFile=/opt/os-agent/.env
ExecStart=/opt/os-agent/.venv/bin/python -m stable_agent.cli serve --host 127.0.0.1 --port 18789 --profile slim
Restart=always
RestartSec=5
MemoryMax=1500M
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

**启用服务**：
```bash
sudo systemctl daemon-reload
sudo systemctl enable stableagent
sudo systemctl start stableagent
sudo systemctl status stableagent
```

## 4. SSH Tunnel 访问

**不要公网裸奔**，使用 SSH tunnel：

```bash
# 本地电脑
ssh -L 18789:127.0.0.1:18789 user@your-server

# 然后访问
http://127.0.0.1:18789/skills
```

## 5. 日志轮转

```ini
# /etc/logrotate.d/stableagent
/var/log/stableagent/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 agent agent
}
```

## 6. 健康检查

```bash
# 本地检查
curl http://127.0.0.1:18789/api/cloud/health

# 技能库检查
PYTHONPATH=. .venv/bin/python -m stable_agent.cli skill health --json
```

## 7. 限制 Active Skill 数量

默认上限 200 个 active skills。超过时：
- Dashboard 提示人工审核
- 建议 archive low score skills
- 不自动删除

修改上限：
```bash
export STABLEAGENT_MAX_ACTIVE_SKILLS=500
```

## 8. 备份

```bash
# 备份技能库
cp -r .stableagent-capsule/skills /backup/skills-$(date +%Y%m%d)

# 导出 bundle
PYTHONPATH=. .venv/bin/python -c "
from stable_agent.skills.repo import SkillRepo
repo = SkillRepo()
repo.export_bundle('/backup/skills-bundle.json')
"
```
