# Experiment Reproducibility Report

> Self-Iteration 5-Round 实验复现报告
> 版本: v2.2

## 实验状态

⚠️ **当前数据为 simulated demo result，不代表生产基准。**

完整生产级复现需要:
1. 真实 LLM 后端 (当前使用简化评估)
2. 5 次完整 Task → Trace → Eval → Regression → Skill Patch 闭环
3. 每轮 10 个真实任务

## 实验文件

| 文件 | 说明 |
|------|------|
| `dataset.jsonl` | 15 个实验任务 (simple/complex/creative) |
| `run_experiment.py` | 通过 MCP tools/call 逐轮执行 |
| `results.json` | 5 轮 demo 数据 |
| `report.md` | 实验设计 + 结果 + 指标计算方法 |

## 如何复现

```bash
# 1. 启动服务
uvicorn web.server:app --host 0.0.0.0 --port 8000

# 2. 运行实验
python experiments/self_iteration_5_rounds/run_experiment.py

# 3. 查看结果
cat experiments/self_iteration_5_rounds/results.json
```

## 指标计算方法

### Quality Score
- correctness × 0.4 + completeness × 0.3 + clarity × 0.3
- 范围: 0.0 - 1.0

### Hallucination Rate
- (含幻觉任务数 / 总任务数) × 100%

### Token Usage
- input + output tokens 累计

### Learning Triggered
- delta > 0 且 eval 中发现 BadCase

## Demo 数据

| Round | Quality | Hallucination | Tokens | Learning |
|-------|---------|---------------|--------|----------|
| R1 | 0.55 | 35% | 4,200 | — |
| R2 | 0.60 | 30% | 3,900 | ✅ |
| R3 | 0.75 | 18% | 3,000 | ✅ |
| R4 | 0.82 | 12% | 2,600 | ✅ |
| R5 | 0.85 | 10% | 2,310 | ✅ |

## 改进方向

1. 使用真实 LLM evaluator 替代简化检查
2. 增加任务多样性 (代码/分析/创意)
3. 多轮平均以减少方差
4. 添加统计显著性检验
5. A/B testing 框架
