# StableAgent Cloud — 手动测试指南 (V9.2)

## 1. 如何启动项目

```bash
VENV=/Users/Zhuanz/.workbuddy/binaries/python/envs/default/bin
cd /path/to/OS-agent

# 启动 Web 服务
$VENV/uvicorn web.server:app --host 0.0.0.0 --port 8000
```

服务启动后访问: http://localhost:8000

## 2. 如何调用 /mcp tools/list

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

预期: 返回 27 个工具列表，包含 `stableagent.task.os_agent`。

## 3. 如何调用正常 os_agent run

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

预期: structuredContent 包含 run_id, eval_passed=true (大概率), progress_pct=100, event_sync_ok=true。

## 4. 如何调用失败学习 os_agent run

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
        "dry_run_learning":true
      }
    }
  }'
```

预期:
- eval_passed=false, eval_score <= 0.4
- si_report.learning_triggered=true
- 事件包含 regression.generated / skill.patch.proposed / validation.checked

## 5. 如何打开 /runs/{run_id}

浏览器访问: `http://localhost:8000/runs/{run_id}`

将 {run_id} 替换为步骤 3 或 4 返回的 run_id。

## 6. 如何查看 /api/runs/{run_id}/events

```bash
curl http://localhost:8000/api/runs/{run_id}/events
```

预期: 返回事件列表，每个事件包含 run_id, event_type, stage, progress_pct, status_text_zh, avatar_state 等字段。

## 7. 如何判断正常路径是否打通

检查以下条件:

1. structuredContent 中 `eval_passed=true` (或评分合理通过)
2. `event_sync_ok=true`
3. `emitted_event_count >= 10`
4. `missing_required_events` 必须为空 `[]`
5. 事件包含: task.received → intent.parsed → eval.completed → task.completed
6. Dashboard Observer 页面显示进度 100%
7. `/api/runs/{run_id}/events` 返回非空事件列表
8. **每个关键事件必须包含 `next_step_zh` 字段**

> ⚠️ **如果 `/api/runs/{run_id}/events` 返回空，则 Dashboard 同步未打通，不能算通过。**

## 8. 如何判断失败学习路径是否打通

检查以下条件:

1. `eval_passed=false`, `eval_score <= 0.4`
2. `si_report.learning_triggered=true`
3. 事件包含: regression.generated / skill.patch.proposed
4. 如果 validation_passed=true: 事件包含 human_review.required
5. 如果 validation_passed=false: human_review_status = "validation_failed"
6. `dry_run_learning=true` 标记存在
7. `missing_required_events` 必须为空 `[]`

> ⚠️ **如果 `integration_test` 出现 SKIP event chain，则不能算通过。**

## 9. 如何确认 best_skill.md 没有被自动覆盖

1. 调用失败学习路径 (dry_run_learning=true)
2. 检查 `skills/best_skill.md` 文件修改时间
3. 验证 approve_patch() 后不会自动写入 best_skill.md
4. 只有显式调用 export_approved_patch() 才会写 best_skill.md

```bash
# 检查 best_skill.md 修改时间
ls -la skills/best_skill.md
```

## 10. 如何确认 Dashboard 是后端事件驱动

1. 打开 Dashboard Observer 页面
2. 调用 os_agent 任务
3. 观察 Dashboard 实时更新:
   - 进度条从 0% → 100% (不是前端猜测)
   - 时间线逐条添加事件

## 11. V9.2 事件链硬性判定标准

以下任一条件不满足，则闭环未打通：

1. **如果 `/api/runs/{run_id}/events` 返回空** → Dashboard 同步未打通
2. **如果 `integration_test` 出现 SKIP event chain** → 不能算通过
3. **如果 `event_sync_ok=false`** → 不能算通过
4. **如果 `best_skill_exported=true` 但没有 human review** → 不能算通过
5. **如果 `missing_required_events` 非空** → 事件链不完整
6. **如果关键事件缺少 `next_step_zh` 字段** → 解释性不足
   - 头像状态随阶段变化
   - 如果 event_sync_ok=false，顶部显示同步异常 banner
4. 事件字段包含后端生成的 why_zh / decision_summary_zh / avatar_state

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
```
