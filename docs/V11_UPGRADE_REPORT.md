# V11 Agent Capsule 升级报告

## 完成状态

[██████████] 100% - V11 Agent Capsule 升级完成

## 测试结果

| 指标 | V10 | V11 | 变化 |
|------|-----|-----|------|
| pytest 通过 | 1157 | 1274 | **+117** |
| pytest 失败 | 0 | 0 | 保持 |
| 闭环检查 | 30/30 | 30/30 | 保持 |
| MCP 工具 | 28 | 55 | **+27** |

## 代码规模

| 类别 | 行数 |
|------|------|
| 新增源码 | ~4700 行 |
| 新增测试 | ~2100 行 |
| 总新增文件 | 38 个 |

## 新增模块

### 1. stable_agent/capsule/ (7 文件)
本地胶囊层 — 用户长期 AI 使用资产的本地容器。

### 2. stable_agent/understanding/ (6 文件)
语义理解轨迹 — 解决"用户表达被模型误解"的问题。

### 3. stable_agent/token/ (5 文件)
Token 预算账本 — 让用户看到 token 节省。

### 4. stable_agent/model_profile/ (5 文件)
模型学生档案 — 不同模型有不同偏科。

### 5. stable_agent/personal_eval/ (7 文件)
个人评测 + A-B 回归 + 反馈闭环。

### 6. stable_agent/cli.py
CLI 入口。

## 新增 MCP 工具 (27 个)

| 工具 | 说明 |
|------|------|
| `stableagent.capsule.status` | 胶囊状态 |
| `stableagent.capsule.doctor` | 胶囊体检 |
| `stableagent.memory.health` | 记忆健康报告 |
| `stableagent.memory.review` | 记忆审核建议 |
| `stableagent.memory.prune` | 修剪低价值记忆 |
| `stableagent.memory.promote` | 晋升记忆为长期 |
| `stableagent.memory.delete` | 删除记忆 |
| `stableagent.understanding.trace` | 语义理解轨迹 |
| `stableagent.understanding.correct` | 用户纠正 |
| `stableagent.expression.list` | 表达习惯列表 |
| `stableagent.expression.add` | 添加表达习惯 |
| `stableagent.expression.delete` | 删除表达习惯 |
| `stableagent.model.profile` | 模型画像 |
| `stableagent.model.list` | 列出模型画像 |
| `stableagent.model.suggest` | 推荐模型 |
| `stableagent.model.update` | 更新模型画像 |
| `stableagent.eval.case.create` | 创建评测用例 |
| `stableagent.eval.case.list` | 列出评测用例 |
| `stableagent.eval.run_ab` | 运行 A-B 回归 |
| `stableagent.eval.rubric.get` | 获取评分标准 |
| `stableagent.eval.rubric.update` | 更新评分标准 |
| `stableagent.feedback.remember` | 记住这个 |
| `stableagent.feedback.dont_do_this_again` | 下次别这样 |
| `stableagent.feedback.correct_and_remember` | 纠正并记住 |
| `stableagent.token.report` | Token 报告 |
| `stableagent.token.run` | 运行 Token 记录 |
| `stableagent.token.summary` | Token 摘要 |

## 如何运行

```bash
pip install -r requirements.txt
python -m stable_agent.cli capsule init
uvicorn web.server:app --host 0.0.0.0 --port 8000
```

## 如何接入 MCP

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 如何测试

```bash
pytest tests/ -q --ignore=tests/test_mcp_gateway.py
python tools/check_closed_loop.py
```

## 安全约束保留确认

- [x] 13 个必需事件链不破坏
- [x] 失败学习路径不破坏
- [x] dry_run_learning=True 不导出 best_skill.md
- [x] validation_failed 不进入 HumanReview
- [x] best_skill.md 只能显式人工审核后导出
- [x] 闭环检查 30/30 PASS
- [x] 无新增 except Exception: pass
- [x] 1274 tests passed (0 failures)
