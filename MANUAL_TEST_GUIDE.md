# StableAgent Cloud — 手动测试指南 (V10)

## 1. 如何配置 .env

```bash
# 复制 .env.example 为 .env
cp .env.example .env

# 填入真实 key（阿里云 DashScope / OpenAI 兼容）
# .env 已加入 .gitignore，不会被提交
OPENAI_API_KEY=sk-your-real-key-here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
STABLE_AGENT_LLM_MODEL=qwen-plus
STABLE_AGENT_ENABLE_REAL_LLM=true
```

## 2. 如何确认 key 不会提交

```bash
# .gitignore 包含 .env
grep "\.env" .gitignore

# git status 不应显示 .env
git status | grep -c ".env"  # 应为 0
```

## 3. 如何启动项目

```bash
VENV=/Users/Zhuanz/.workbuddy/binaries/python/envs/default/bin
cd /path/to/OS-agent

# 加载 .env
set -a; source .env; set +a

# 启动 Web 服务
$VENV/uvicorn web.server:app --host 0.0.0.0 --port 8000
```

## 4. 如何调用 /mcp tools/list

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

预期: 返回工具列表，包含 `stableagent.task.os_agent`。

## 5. 如何调用正常 os_agent run

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":"normal-test",
    "method":"tools/call",
    "params":{
      "name":"stableagent.task.os_agent",
      "arguments":{
        "task_input":"帮我分析这个 bug 的根因",
        "mode":"auto",
        "open_dashboard":true
      }
    }
  }'
```

预期: structuredContent 包含 run_id, eval_passed, event_sync_ok=true, event_api_ok=true, dashboard_replay_ok=true。

## 6. 如何调用失败学习 os_agent run

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":"failure-test",
    "method":"tools/call",
    "params":{
      "name":"stableagent.task.os_agent",
      "arguments":{
        "task_input":"测试失败学习路径",
        "mode":"auto",
        "open_dashboard":true,
        "force_eval_failed":true,
        "force_failure_mode":"intent_drift",
        "force_regression_case":true,
        "force_skill_patch":true,
        "force_validation_passed":false,
        "dry_run_learning":true
      }
    }
  }'
```

预期:
- eval_passed=false, eval_score <= 0.4
- si_report.learning_triggered=true
- event_api_ok=true, dashboard_replay_ok=true
- best_skill_exported != true

## 7. 如何查看 /api/runs/{run_id}/events

```bash
curl http://localhost:8000/api/runs/{run_id}/events
```

预期: 返回结构化 JSON:
```json
{
  "run_id": "run_xxx",
  "event_count": 13,
  "events": [...]
}
```

## 8. 如何打开 Dashboard Observer

浏览器访问: `http://localhost:8000/observer?run_id={run_id}`

页面加载时:
1. 先请求 `/api/runs/{run_id}/events` 回放历史事件
2. 再连接 WebSocket 接收实时事件
3. 无事件时显示同步异常提示

## 9. 如何判断 event_api_ok

在 MCP 响应的 structuredContent 中检查:
- `event_api_ok = true` → RunStore 写入 + API 读取链路通畅
- `api_event_count > 0` → API 返回的事件数量
- `api_missing_required_events = []` → 所有必需事件都已通过 API 可查

> ⚠️ **如果 event_api_ok=false，则 Dashboard 没有真实同步。**

## 10. 如何判断 dashboard_replay_ok

- `dashboard_replay_ok = true` → Dashboard 可以回放完整事件
- 在 Dashboard Observer 页面看到时间线有事件
- `event_count` 显示在页面上

> ⚠️ **如果 dashboard_replay_ok=false，则解释型可视化面板没有真正打通。**

## 11. 如何判断自我优化闭环是否触发

1. 调用失败学习路径 (force_eval_failed=true)
2. 检查 `si_report.learning_triggered=true`
3. 检查事件包含: regression.generated / skill.patch.proposed / validation.checked

## 12. 如何确认 best_skill.md 没有在 dry_run 下被导出

1. 调用失败学习路径 (dry_run_learning=true)
2. 检查 `si_report.best_skill_exported` 不是 `true`
3. 检查 `skills/best_skill.md` 修改时间未变

```bash
ls -la skills/best_skill.md
```

## 13. 如何运行 real_llm_e2e_test

```bash
# 确保 .env 已配置真实 key
bash scripts/real_llm_e2e_test.sh

# 或直接运行
python tools/real_llm_e2e_test.py --base-url http://127.0.0.1:8000
```

脚本不输出 key，报告写入 `REAL_LLM_E2E_REPORT.md`。

## 14. V10 硬性判定标准

以下任一条件不满足，则闭环未打通：

1. **如果 `/api/runs/{run_id}/events` 返回空** → Dashboard 同步未打通
2. **如果 integration_test fallback 到 emitted_events** → 不能算通过
3. **如果 event_api_ok=false** → Dashboard 没有真实同步
4. **如果 dashboard_replay_ok=false** → 解释型可视化面板没有真正打通
5. **如果 event_sync_ok=false** → 事件链不完整
6. **如果 best_skill_exported=true 但没有 human review** → 不能算通过
7. **如果 missing_required_events 非空** → 事件链不完整
8. **如果 api_missing_required_events 非空** → API 读取链路不通
9. **如果关键事件缺少 next_step_zh 字段** → 解释性不足
10. **如果日志中出现真实 API key** → 安全违规

---

## 运行自动测试

```bash
VENV=/Users/Zhuanz/.workbuddy/binaries/python/envs/default/bin

# 单元测试
$VENV/pytest tests/ -q --ignore=tests/test_mcp_gateway.py

# 闭环结构检查
PYTHONPATH=. $VENV/python tools/check_closed_loop.py

# 集成测试 (需要服务器运行)
$VENV/python tools/integration_test.py --base-url http://127.0.0.1:8000

# 真实 LLM E2E 测试 (需要 key)
bash scripts/real_llm_e2e_test.sh
```
