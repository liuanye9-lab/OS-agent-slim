# V11.2 Trustworthy Capsule Loop

## 核心理念

StableAgent OS 不训练模型权重，而是训练"模型外部使用层"。V11.2 的目标是把当前已经存在的 Agent Capsule / Understanding Trace / Token Budget / Feedback / Dashboard 真正打通成可信闭环。

**闭环路径**：用户反馈 → 结构化记录 → 验证 → 人工确认 → 下次命中 → 可视化证明

## 变更清单

### 1. Feedback → SkillPatch → Validation → HumanReview 真实闭环

**问题**：`/api/feedback/dont-do-this-again` 返回 `generated.skill_patch_candidate=true`，但实际没有创建 `SkillPatchCandidate`。

**修复**：
- 新增 `stable_agent/feedback/feedback_learning_service.py` — `FeedbackLearningService`
- 三个 handler：`handle_remember` / `handle_dont_do_this_again` / `handle_correct_and_remember`
- `dont_do_this_again` 真实执行：BadCase → EvalCase → SkillPatchCandidate → RegressionValidationRunner → (validation_passed) → HumanReviewQueue
- `generated` 字段只标记真实产物，不允许虚假标记

**关键文件**：
- `stable_agent/feedback/feedback_learning_service.py` (新增)
- `web/routes/api.py` (修改)
- `web/app.py` (修改)

### 2. Feedback 事件写入 RunStore / Dashboard

**问题**：用户点击反馈按钮后，Dashboard 时间线看不到反馈结果。

**修复**：
- API 成功后广播 `feedback.received` / `bad_case.recorded` / `eval_case.generated` / `skill.patch.proposed` / `validation.checked` / `human_review.required` / `expression.rule.candidate`
- `register_api_routes` 新增 `gateway_run_store` 参数
- `get_run_learning` 新增 feedback 相关事件类型

**关键文件**：
- `web/routes/api.py` (修改)
- `web/routes/runs.py` (修改)
- `web/app.py` (修改)

### 3. 表达习惯迁移打通

**问题**：`os_agent` 中 `SemanticInterpreter()` 没有加载 `ExpressionProfileManager`。

**修复**：
- `_h_task_os_agent` 中创建 `SemanticInterpreter` 前尝试加载 `ExpressionProfileManager`
- 加载失败时降级为 `SemanticInterpreter()`
- `expression_matches` 通过 `understanding.trace.created` 事件进入 Dashboard

**关键文件**：
- `stable_agent/gateway/unified_tool_registry.py` (修改)

### 4. Token Budget 可信报告

**问题**：Token 报告缺少 `baseline` / `injected` / `estimation_method` / `is_estimated` 字段。

**修复**：
- `TokenRunRecord` 新增 `candidate_context_tokens` / `estimation_method` / `is_estimated`
- `summary_zh` 对空/少 context 说明估算性质
- `saved_tokens` 修正为 `max(0, baseline - injected)`

**关键文件**：
- `stable_agent/token/schemas.py` (修改)
- `stable_agent/gateway/unified_tool_registry.py` (修改)

### 5. Dashboard 干预面板

**问题**：Dashboard 只有观察面板，缺少人为干预动作。

**修复**：
- Understanding Panel：「理解正确」+「有偏差，纠正」按钮
- Memory Health Panel：「保留」+「删除」+「稍后处理」按钮
- Skill Evolution Panel：显示 review 状态
- Bad Case Panel：「生成回归测试」按钮
- Token Budget Panel：显示 `is_estimated` / `estimation_method` / `summary_zh`
- Feedback 提交后自动刷新 V11 Panels

**关键文件**：
- `web/templates/run_observer.html` (修改)
- `web/static/run_observer.js` (修改)

### 6. 清除 except Exception: pass

**问题**：feedback 路径存在静默失败。

**修复**：
- `web/routes/api.py`：所有 `except Exception` 改为 `logger.warning(...)` + `errors` 字段
- `web/routes/runs.py`：`dash_sync.sync_feedback` 和 `BudgetLedger` 失败时记录日志
- API 返回 `errors` 字段（非空时表示有局部失败）

**关键文件**：
- `web/routes/api.py` (修改)
- `web/routes/runs.py` (修改)

## 新增文件

| 文件 | 说明 |
|------|------|
| `stable_agent/feedback/__init__.py` | feedback 包 |
| `stable_agent/feedback/feedback_learning_service.py` | 三动作闭环服务 |
| `tests/test_feedback_learning_service.py` | FeedbackLearningService 测试 |
| `tests/test_feedback_dont_do_this_again_real_loop.py` | 真实闭环测试 |
| `tests/test_feedback_events_to_runstore.py` | 事件广播测试 |
| `tests/test_token_budget_trustworthy_report.py` | Token 可信报告测试 |
| `tests/test_dashboard_v11_intervention_template.py` | Dashboard 干预面板测试 |
| `tests/test_no_silent_feedback_failures.py` | 静默失败消除测试 |
| `docs/V11_2_TRUSTWORTHY_CAPSULE_LOOP.md` | 本文档 |

## API 返回规范

### /api/feedback/dont-do-this-again

```json
{
  "ok": true,
  "action": "dont_do_this_again",
  "run_id": "...",
  "generated": {
    "bad_case": true,
    "eval_case": true,
    "skill_patch_candidate": true,
    "validation_report": true,
    "human_review_required": false
  },
  "ids": {
    "bad_case_id": "...",
    "eval_case_id": "...",
    "patch_id": "...",
    "validation_report_id": "...",
    "review_id": null
  },
  "validation": {
    "passed": false,
    "reason_zh": "..."
  },
  "summary_zh": "...",
  "errors": null
}
```

**规则**：
- `generated.skill_patch_candidate = true` 只在 `SkillPatchCandidate` 真实创建后
- `generated.validation_report = true` 只在 `RegressionValidationRunner` 真实执行后
- `generated.human_review_required = true` 只在 `HumanReviewQueue.submit()` 真实调用后
- `validation_passed = false` 时不得进入 HumanReview
- `errors` 非空时表示有局部失败，但主流程不中断

## 测试

```bash
# 新增测试
pytest tests/test_feedback_learning_service.py -v
pytest tests/test_feedback_dont_do_this_again_real_loop.py -v
pytest tests/test_feedback_events_to_runstore.py -v
pytest tests/test_token_budget_trustworthy_report.py -v
pytest tests/test_dashboard_v11_intervention_template.py -v
pytest tests/test_no_silent_feedback_failures.py -v

# 全量测试
pytest tests/ -q
```
