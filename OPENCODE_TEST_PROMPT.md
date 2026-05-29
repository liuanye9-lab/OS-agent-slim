# StableAgent Cloud — Open Code 测试提示词

> 复制下面全部内容，粘贴到 Open Code 对话框，回车即可。

---

## 项目信息

你正在操作的是 StableAgent Cloud 项目，位于 `D:\Vibe coding\OS agent\`。
这是一个 AgentOps + SkillOps SaaS 平台，已通过生产级硬化（371 测试，19/19 验收）。

核心技术栈：Python 3.13 / FastAPI / SQLite / Vanilla JS / MCP JSON-RPC 2.0

---

## 任务：运行完整测试并验证

### 第一步：确认环境

```bash
cd "D:\Vibe coding\OS agent"
C:/Users/Lay/.workbuddy/binaries/python/versions/3.13.12/python.exe --version
```

预期输出：`Python 3.13.12`

### 第二步：单元测试

```bash
cd "D:\Vibe coding\OS agent"
set PYTHONPATH=.
C:/Users/Lay/.workbuddy/binaries/python/versions/3.13.12/python.exe -m pytest tests/test_p0_core.py tests/test_run_lifecycle.py tests/test_decision_trace_builder.py tests/test_mcp_entrypoint.py tests/test_response_adapter_fields.py tests/test_high_risk_approval_block.py tests/test_approval_resume_service.py tests/test_repository_errors.py tests/test_migration_runner.py tests/test_security_context.py tests/test_permission_guard.py tests/test_regression_runner.py tests/test_validation_report.py tests/test_dashboard_run_detail.py tests/test_self_iteration_experiment_files.py -q --tb=line
```

**预期结果**：128 passed, 0 failed

### 第三步：启动服务器

```bash
cd "D:\Vibe coding\OS agent"
set PYTHONPATH=.
start /B C:/Users/Lay/.workbuddy/binaries/python/versions/3.13.12/python.exe -m uvicorn web.server:app --host 127.0.0.1 --port 8000
```

等待 5 秒后验证：

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/
```

**预期结果**：`200`

### 第四步：验证 12 个页面

```bash
for p in / /login /connect /dashboard/v3 /dashboard/usage /dashboard/apikeys /dashboard/billing /dashboard/team /dashboard/skills /dashboard/review /docs /redoc; do
  code=$(curl -s -o /dev/null -w "%%{http_code}" http://127.0.0.1:8000$p)
  echo "  $p → $code"
done
```

**预期结果**：全部 `200`

### 第五步：验证 MCP 入口

**5.1 工具列表**（28 个工具）

```bash
curl -s -X POST http://127.0.0.1:8000/mcp/ -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}" | python -c "import sys,json; d=json.load(sys.stdin); tools=d['result']['tools']; names=[t['name'] for t in tools]; print(f'工具数: {len(tools)}'); print(f'含 os_agent: {\"stableagent.task.os_agent\" in names}'); print(f'含 export_best: {\"stableagent.skill.export_best\" in names}')"
```

**预期结果**：`工具数: 28`，`含 os_agent: True`，`含 export_best: True`

**5.2 调用低风险工具**（直接执行，不阻断）

```bash
curl -s -X POST http://127.0.0.1:8000/mcp/ -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"id\":2,\"params\":{\"name\":\"stableagent.memory.retrieve\",\"arguments\":{\"task_input\":\"测试\"}}}" | python -c "import sys,json; sc=json.load(sys.stdin)['result']['structuredContent']; print(f'OK: {sc[\"ok\"]}'); print(f'run_id: {sc[\"run_id\"]}'); print(f'dashboard: {sc[\"dashboard_url\"]}')"
```

**预期结果**：`OK: True`，有 `run_id` 和 `dashboard_url`

**5.3 调用高风险工具**（必须阻断，返回审批 ID）

```bash
curl -s -X POST http://127.0.0.1:8000/mcp/ -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"id\":3,\"params\":{\"name\":\"stableagent.skill.export_best\",\"arguments\":{\"patch_id\":\"sp_test\"}}}" | python -c "import sys,json; sc=json.load(sys.stdin)['result']['structuredContent']; d=sc.get('data',{}); print(f'阻断: {d.get(\"approval_required\")}'); print(f'审批ID: {d.get(\"approval_id\",\"无\")[:30]}...')"
```

**预期结果**：`阻断: True`，有 `审批ID`

### 第六步：验证 ResponseAdapter 字段完整性

```bash
curl -s -X POST http://127.0.0.1:8000/mcp/ -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"id\":4,\"params\":{\"name\":\"stableagent.context.build\",\"arguments\":{\"task_input\":\"测试\"}}}" | python -c "
import sys,json
sc=json.load(sys.stdin)['result']['structuredContent']
fields=['ok','run_id','dashboard_url','status_text_zh','status_text_en','plain_text_zh','plain_text_en']
missing=[f for f in fields if f not in sc]
has_bad='chain_of_thought' in sc
print(f'缺失字段: {missing or \"无\"}')  
print(f'chain_of_thought泄露: {has_bad}')  
print(f'样例: status_text_zh={sc.get(\"status_text_zh\",\"?\")[:30]}')
"
```

**预期结果**：`缺失字段: 无`，`chain_of_thought泄露: False`

### 第七步：验证 SaaS API

```bash
echo "=== 工作区 ===" && curl -s http://127.0.0.1:8000/api/workspaces | python -c "import sys,json; d=json.load(sys.stdin); print(f'  workspaces数量: {len(d.get(\"workspaces\",[]))}')"
echo "=== 注册用户 ===" && curl -s -X POST http://127.0.0.1:8000/api/auth/register -H "Content-Type: application/json" -d "{\"email\":\"opencode@test.com\",\"password\":\"test123456\",\"name\":\"OpenCode\"}" | python -c "import sys,json; d=json.load(sys.stdin); print(f'  成功: {\"token\" in d}, user_id={d.get(\"user_id\",\"?\")[:20]}...')"
echo "=== 创建项目 ===" && curl -s -X POST http://127.0.0.1:8000/api/projects -H "Content-Type: application/json" -d "{\"workspace_id\":\"ws_local\",\"name\":\"opencode-test\"}" | python -c "import sys,json; d=json.load(sys.stdin); print(f'  结果: {d}')"
echo "=== 用量查询 ===" && curl -s http://127.0.0.1:8000/api/usage | python -c "import sys,json; d=json.load(sys.stdin); print(f'  total_tokens={d.get(\"total_tokens\",\"?\")}, total_events={d.get(\"total_events\",\"?\")}')"
```

### 第八步：本地验收测试（一键）

```bash
cd "D:\Vibe coding\OS agent"
set PYTHONPATH=.
C:/Users/Lay/.workbuddy/binaries/python/versions/3.13.12/python.exe tests/run_acceptance_tests.py
```

**预期结果**：`✅ Passed: 33, ❌ Failed: 0, 🎉 ALL TESTS PASSED!`

---

## 验收标准速查表

| # | 检查项 | 预期 | 命令 |
|---|--------|------|------|
| 1 | 服务器启动 | HTTP 200 | `curl http://127.0.0.1:8000/` |
| 2 | 12 页面可达 | 全部 200 | 第四步循环 |
| 3 | MCP tools/list | 28 个工具 | 第五步 5.1 |
| 4 | 低风险工具直接执行 | ok=True + run_id | 第五步 5.2 |
| 5 | 高风险工具阻断 | approval_required=True | 第五步 5.3 |
| 6 | ResponseAdapter 字段 | 7 字段 + 无泄露 | 第六步 |
| 7 | SaaS API 可用 | 工作区/注册/项目/用量 | 第七步 |
| 8 | 验收测试 | 33 passed | 第八步 |
| 9 | 单元测试 | 128 passed | 第二步 |

---

## 常见问题排查

**Q: `No module named 'stable_agent'`**
A: 缺 `set PYTHONPATH=.`，或者用 `cd D:\Vibe coding\OS agent` 确认在项目根目录

**Q: 端口被占用**
A: `netstat -ano | findstr 8000` 找到进程，`taskkill /PID xxx /F` 杀掉

**Q: curl 报 307 重定向**
A: MCP 端点必须用 `/mcp/`（带尾部斜杠），不是 `/mcp`

**Q: pytest 报 import error**
A: 安装依赖 `pip install fastapi uvicorn httpx websockets`
