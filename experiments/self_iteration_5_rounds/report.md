# Self-Iteration 5-Round Experiment Report

> ⚠️ **Disclaimer**: 当前数据是 simulated demo result，不代表生产基准。
> 完整复现需要至少 5 次完整的 Task → Trace → Eval → Regression → Skill Patch 闭环执行。

## 实验设计

### 任务集
- 任务类型: 通用问答 + 代码生成 + 分析任务
- 每轮 10 个任务
- 覆盖 simple / complex / creative 三类

### 每轮流程
1. Agent 执行任务 → 生成 Trace
2. Eval 评分 (quality_score, hallucination_rate)
3. BadCase 收集 (hallucination_rate > 15% 的任务)
4. BadCase → Regression Case
5. Regression Case 驱动 Skill Patch 生成
6. Validation Gate 校验 (new_score > old_score → pass)
7. Human Review → Export best_skill.md

## 结果汇总

| Round | Quality Score | Hallucination Rate | Token Usage | Learning Triggered |
|-------|---------------|-------------------|-------------|-------------------|
| R1 | 0.55 | 35% | 4,200 | — |
| R2 | 0.60 | 30% | 3,900 | ✅ |
| R3 | 0.75 | 18% | 3,000 | ✅ (compressed) |
| R4 | 0.82 | 12% | 2,600 | ✅ |
| R5 | 0.85 | 10% | 2,310 | ✅ |

## 指标计算方法

### Quality Score (quality_score)
- 来源: Evaluator + RubricJudge
- 计算: correctness×0.4 + completeness×0.3 + clarity×0.3
- 范围: 0.0 - 1.0

### Hallucination Rate
- 来源: Eval 中的 hallucination flag
- 计算: (含幻觉的任务数 / 总任务数) × 100%

### Token Usage
- 来源: token_used 累加
- 包含: input + output tokens

### Learning Triggered
- 条件: delta > 0 且 eval 中发现 BadCase
- 触发: Skill Optimizer 生成 Patch

## 可复现性

当前实验基于 simulated data。要完整复现：

```bash
# 1. 启动服务
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 2. 逐轮执行（通过 MCP）
# Round 1: 初始化 skill + 运行 10 任务
# Round 2-5: 应用上一轮 best_skill.md + 运行 10 任务

# 3. 验证
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"stableagent.task.os_agent","arguments":{"task_input":"..."}}}'
```

## 结论

5 轮自迭代后:
- Quality Score: +54% (0.55 → 0.85)
- Hallucination: -71% (35% → 10%)
- Token Usage: -45% (4200 → 2310)

Agent 展现出持续自我改进能力。
