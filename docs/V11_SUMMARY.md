# V11 Agent Capsule 升级完成

[██████████] 100% - V11 Agent Capsule 升级完成

## 核心指标

| 指标 | V10 | V11 |
|------|-----|-----|
| 测试通过 | 1157 | **1274** (+117) |
| MCP 工具 | 28 | **55** (+27) |
| 闭环检查 | 30/30 | **30/30** |

## 新增模块 (7 个, ~4700 行源码)

1. **capsule/** — 本地胶囊层 (create/load/export/import/doctor/status)
2. **understanding/** — 语义理解轨迹 (SemanticInterpreter + ExpressionProfile + CorrectionStore)
3. **token/** — Token Budget Ledger (TokenEstimator + BudgetLedger + SavingsReport)
4. **model_profile/** — Model Student Profile (ModelProfile + ModelRouter + AdapterLoader)
5. **personal_eval/** — Personal Eval + A-B Regression + Feedback Loop
6. **cli.py** — CLI 入口
7. **27 个 MCP 工具** — 胶囊/记忆/理解/模型/评测/反馈/Token

## 如何使用

```bash
# 初始化
python -m stable_agent.cli capsule init

# 启动
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 接入 MCP
{"mcpServers": {"stableagent": {"url": "http://127.0.0.1:8000/mcp"}}}
```

## 安全约束

所有 V10 安全约束完整保留：13 事件链、失败学习路径、dry_run 阻止导出、validation_failed 不进 HumanReview。

详见 [V11_UPGRADE_REPORT.md](V11_UPGRADE_REPORT.md) 和 [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md)。
