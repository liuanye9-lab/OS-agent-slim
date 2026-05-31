# Effectiveness Evaluation Guide — V11.3.1

> A/B 对比实验可信数据评测系统使用指南。

## 概述

Effectiveness 模块用于对 StableAgent 模式与 Baseline 模式在相同任务上的表现进行量化对比。核心产出为四级判定 verdict（有效 / 有潜力 / 未见效 / 数据不足）。

## 快速开始

### 1. 创建任务

```bash
curl -X POST http://localhost:8000/api/effectiveness/task \
  -H "Content-Type: application/json" \
  -d '{"task_id":"my-task-001","description":"修复登录超时 bug","category":"bugfix"}'
```

### 2. 记录 Baseline 运行数据

```bash
curl -X POST http://localhost:8000/api/effectiveness/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "my-task-001",
    "run_id": "baseline-run-1",
    "mode": "baseline",
    "success": false,
    "edits_made": 5,
    "tokens_used": 2000,
    "intent_drift": 0.5,
    "constraint_preservation": 0.6
  }'
```

### 3. 记录 StableAgent 运行数据

```bash
curl -X POST http://localhost:8000/api/effectiveness/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "my-task-001",
    "run_id": "stableagent-run-1",
    "mode": "stableagent",
    "success": true,
    "edits_made": 8,
    "tokens_used": 1000,
    "intent_drift": 0.1,
    "constraint_preservation": 0.95
  }'
```

### 4. 查看评估结果

```bash
# 查看所有任务汇总
curl http://localhost:8000/api/effectiveness/summary

# 通过 run_id 查询特定任务的评估
curl "http://localhost:8000/api/effectiveness/summary?run_id=stableagent-run-1"
```

## Verdict 判定逻辑

系统根据 4 个正面信号计算 verdict：

| 信号 | 条件 | 含义 |
|------|------|------|
| success delta | stableagent 成功率 > baseline + 10% | 任务成功率高 |
| intent_drift delta | stableagent 意图漂移 < baseline - 0.1 | 意图保持更好 |
| edit_efficiency delta | stableagent 编辑效率 > baseline + 0.01 | 每 token 更多有效编辑 |
| constraint_preservation delta | stableagent 约束保持力 > baseline + 5% | 约束保护更好 |

判定阈值：
- **≥ 3 个正面信号** → `effective`（已验证有效）
- **2 个正面信号** → `promising`（有潜力）
- **0-1 个正面信号** → `not_effective`（未见效）
- **任一模式 run < 2** → `insufficient_data`（数据不足）

## V11.3 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | string | 使用的 LLM 模型（如 "qwen-plus"） |
| `stableagent_run_id` | string | 关联的 StableAgent 运行 ID，用于追溯 |
| `test_passed` | bool | 编辑后自动化测试是否通过 |
| `over_editing` | bool | 是否检测到过度编辑 |
| `rework_count` | int | 返工迭代次数 |
| `user_satisfaction` | float | 用户满意度评分（1-5） |
| `constraint_preservation` | float | 约束保持力比例（0-1） |

## 前端使用

- **Dashboard**: `/effectiveness` — 总览所有任务的 A/B 对比
- **Observer 联动**: `/dashboard/observer?run_id=XXX` — 页面顶部"效果评估 →"链接自动带上 run_id，如果有对应评估数据会在状态卡片下方显示效果评估 badge

## 数据位置

所有数据存储在 `.stableagent-capsule/effectiveness/` 目录下：
- `effectiveness_tasks.jsonl` — 任务定义
- `effectiveness_runs.jsonl` — 运行记录
- `effectiveness.lock` — 并发锁文件

## 可靠性保证

- 所有 API 端点统一返回 `{ok: true/false, data/error}` 结构
- 空数据不返回 500 错误
- 全部新增/修改均有测试覆盖（83 个有效性相关测试全部通过）
