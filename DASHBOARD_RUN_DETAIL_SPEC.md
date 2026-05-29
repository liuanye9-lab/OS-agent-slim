# Dashboard Run Detail Specification

> Dashboard Run Detail 规范
> 版本: v2.2

## 概述

Run Detail 页面 (`/runs/{run_id}`) 展示 Agent 单次运行的完整闭环状态。

## 必须展示的字段

| 字段 | 来源 | 说明 |
|------|------|------|
| run_id | RunContext | 运行唯一标识 |
| workspace_id | RunContext | 工作空间归属 |
| project_id | RunContext | 项目归属 |
| 当前阶段 | RunLifecycle | 20 阶段之一 |
| 进度百分比 | RunStageMeta.progress_pct | 0-100 |
| 状态文本 | RunStageMeta.status_text_zh | 中文描述 |
| 为什么这样做 | DecisionTrace.why_zh | 大白话解释 |
| 下一步 | RunStageMeta.default_next_step_zh | 下一步指引 |
| DecisionTrace timeline | EventStream | 决策时间线 |
| Eval score | EvalResult | 评测分数 |
| Failure Attribution | RunRecord | 失败归因 |
| Regression Case | RegressionRunner | 回归用例 |
| Skill Patch | SkillPatchRecord | 技能补丁 |
| Validation Report | ValidationReport | 验证报告 |
| Human Review status | HumanReviewRecord | 审核状态 |
| Audit Log | AuditLogRecord | 审计日志 |
| Usage | UsageEventRecord | 用量统计 |

## 数据流

```
后端事件源 (唯一真相)
    ↓
EventStream.publish_sync(run_id, event)
    ↓
DecisionTraceBuilder.build_for_dashboard()
    ↓
SSE Event (/mcp?run_id=xxx)
    ↓
Dashboard V3 JS 消费
    ↓
前端渲染 (状态来自事件，不允许前端猜)
```

## 关键约束

- ❌ 不允许前端猜测进度（必须来自后端 event）
- ❌ 不允许静态进度条（必须实时更新）
- ✅ high risk 工具显示 waiting approval 状态
- ✅ approval approve/reject 后实时更新
- ✅ 所有决策有 why_zh 大白话解释
