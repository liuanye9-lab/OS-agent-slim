# DEPLOYMENT_AND_TESTING_GUIDE.md — 部署与测试指南

**版本**: V8.1

---

## 部署

### 一键部署

```bash
bash scripts/deploy_local.sh
```

步骤：
1. 创建 venv
2. 安装依赖 (`requirements.txt`)
3. 初始化目录 (`data/`, `logs/`, `skills/`, `reports/`)
4. 启动 uvicorn (`web.server:app --host 127.0.0.1 --port 8000`)

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 8000 | 服务端口 |
| `HOST` | 127.0.0.1 | 绑定地址 |
| `PYTHON_BIN` | python3 | Python 路径 |
| `STABLE_AGENT_MODE` | local | 运行模式 |
| `STABLE_AGENT_DB_PATH` | data/stable_agent.db | 数据库路径 |

### 访问

| 页面 | URL |
|------|-----|
| API 文档 | `http://127.0.0.1:8000/docs` |
| MCP 入口 | `http://127.0.0.1:8000/mcp` |
| Dashboard | `http://127.0.0.1:8000` |
| 连接指南 | `http://127.0.0.1:8000/connect` |

---

## 测试

### 全量测试

```bash
pytest -q --ignore=tests/test_mcp_gateway.py
# → 1083 passed, 0 failures
```

### 冒烟测试

```bash
bash scripts/smoke_test.sh
```

检测：
- `/` 根路径可访问
- `/docs` API 文档可访问
- `/connect` 连接页面可访问
- `/mcp` tools/list 返回正常 JSON-RPC

### 集成测试

```bash
bash scripts/integration_test.sh
```

检测：
- MCP tools/list 正常
- `stableagent.task.os_agent` 调用返回 run_id
- `/api/runs/{run_id}/events` 事件字段完整
- Dashboard Observer 页面可访问
- DecisionTrace 不含 chain_of_thought

### 闭环结构检查

```bash
python tools/check_closed_loop.py
```

检测：
1. 核心模块可导入
2. RunLifecycle 22 阶段完整
3. SelfImprovementProofLoop 非硬编码验证
4. best_skill.md 受 Human Review 保护
5. Dashboard Observer 文件存在
6. 自动化脚本存在
7. 无隐藏 chain-of-thought 字段

---

## Docker

```bash
docker-compose up
```
