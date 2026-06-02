# CLI_FIRST_GUIDE.md — CLI-first 接入指南

> 版本: V11.5

---

## 1. 快速开始

### 1.1 一键启动
```bash
bash scripts/quickstart.sh
```

### 1.2 手动启动
```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .

# 启动服务器
PYTHONPATH=. python -m stable_agent.cli serve
```

---

## 2. CLI 命令

### 2.1 核心命令
```bash
stableagent doctor              # 综合健康检查
stableagent serve               # 启动服务器
stableagent health              # 健康检查
stableagent task run -t "..."   # 执行任务
```

### 2.2 技能管理
```bash
stableagent skill list          # 列出技能
stableagent skill show <id>     # 显示技能详情
stableagent skill validate <id> # 验证技能
stableagent skill promote <id>  # 晋升技能
```

### 2.3 反馈管理
```bash
stableagent feedback remember --run-id ID --note "..."
stableagent feedback dont --run-id ID --note "..."
stableagent feedback correct --run-id ID --phrase "..." --meaning "..."
```

### 2.4 胶囊管理
```bash
stableagent capsule init
stableagent capsule status
stableagent capsule doctor
```

---

## 3. MCP 接入

### 3.1 Claude Code
```bash
# 生成 .mcp.json
bash scripts/connect_claude_code.sh

# 在 Claude Code 中
claude
/mcp
```

### 3.2 stdio MCP
```bash
PYTHONPATH=. python -m stable_agent.mcp_stdio --profile minimal
```

### 3.3 HTTP MCP
```bash
curl -X POST http://127.0.0.1:8000/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"stableagent.task.os_agent","arguments":{"task_input":"test"}},"id":"1"}'
```

---

## 4. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STABLE_AGENT_TOOL_PROFILE` | minimal | 工具暴露级别 |
| `STABLE_AGENT_CURATOR_V2` | 0 | 启用 Curator v2 |
| `STABLE_AGENT_SKILL_REPO_BACKEND` | file+sqlite | SkillRepo 后端 |
| `STABLE_AGENT_OBSERVER_MODE` | replay_api | Observer 模式 |

---

## 5. 验证

### 5.1 运行测试
```bash
python -m pytest tests/ -q
```

### 5.2 集成测试
```bash
bash scripts/integration_test.sh
```

### 5.3 闭环检查
```bash
python tools/check_closed_loop.py
```
