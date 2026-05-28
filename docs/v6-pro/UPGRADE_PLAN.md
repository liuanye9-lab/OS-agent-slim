# UPGRADE_PLAN.md — StableAgent OS V6-Professional

## 1. 本轮目标

在不破坏现有 792 tests 的前提下，补齐 P0 闭环的 8 个缺口，
使 `Task → Trace → Eval → Failure Attribution → Reflection → Skill Patch → Validation Gate → Human Review → best_skill.md` 全链路无断裂点。

## 2. 不做什么

- ❌ 不重写架构
- ❌ 不换技术栈
- ❌ 不删除旧模块
- ❌ 不引入重型外部依赖
- ❌ 不做完整 GUI Agent
- ❌ 不自动覆盖 best_skill.md

## 3. P0 修改清单

| ID | 修改 | 文件 | 行数 |
|----|------|------|------|
| P0-1 | EvaluationResult 增加 failure_attribution + step_efficiency | models.py | +5 行 |
| P0-2 | BadCase 增加 id/tags/source_run_id，增加 convert_to_regression_case() | models.py + eval_and_bad_case.py | +40 行 |
| P0-3 | Workflow 增加 sub_steps 字段 | models.py | +2 行 |
| P0-4 | 创建 skills/candidates/ + skills/rejected/ | skills/ 目录 | 新建 |
| P0-5 | SkillExporter 增加 requires_human_review 硬约束 | skill_exporter.py | +15 行 |
| P0-6 | SkillOptimizationEngine 在 export 前强制检查 ValidationGate | skill_optimization_engine.py | +10 行 |
| P0-7 | 创建 data/regression_cases.jsonl 空初始化 | data/ 目录 | 新建 |
| P0-8 | 生成 UPDATED_README.md | 根目录 | 新建 |

## 4. 文件级修改计划

```text
修改:
  stable_agent/models.py             — +2 字段 (EvaluationResult + Workflow + BadCase)
  stable_agent/eval_and_bad_case.py  — +convert_to_regression_case()
  stable_agent/skill_optimizer/skill_exporter.py — +human_review gate
  stable_agent/skill_optimizer/skill_optimization_engine.py — +pre-export check
  README.md                          — 不直接覆盖，生成 UPDATED_README.md

新建:
  skills/candidates/.gitkeep
  skills/rejected/.gitkeep
  data/regression_cases.jsonl
  docs/v6-pro/RESEARCH_REPORT.md    (✅ 已完成)
  docs/v6-pro/ARCHITECTURE_AUDIT.md (✅ 已完成)
  docs/v6-pro/UPGRADE_PLAN.md       (当前文件)
  docs/v6-pro/IMPLEMENTATION_LOG.md
  docs/v6-pro/CHANGELOG.md
  docs/v6-pro/ROADMAP.md
  UPDATED_README.md
```

## 5. 测试计划

- 运行 `pytest tests/ -q --ignore=tests/test_mcp_gateway.py`
- 预期：792+ tests passed（新增测试不破坏现有）
- 如失败：只修复本轮引入的，不修既有问题

## 6. 风险控制

| 风险 | 缓解 |
|------|------|
| models.py 新增字段破坏兼容 | 所有新字段用 `field(default=...)` |
| skill_exporter human_review 影响现有流程 | 默认 `requires_human_review=True`，API 不变 |
| regression_cases.jsonl 空文件 | 仅占位，后续数据自动填充 |

## 7. 回滚方案

- `git revert` 本 commit
- models.py 字段是追加，不影响现有序列化
- skills/ 新目录是新增，删除即可

## 8. 进度百分比

```text
[0%]   初始化
[5%]   仓库扫描           ✅
[10%]  研究对标           ✅ (RESEARCH_REPORT.md)
[20%]  架构审计           ✅ (ARCHITECTURE_AUDIT.md)
[30%]  升级计划           ✅ (当前文件)
[55%]  P0 代码修改        🔄
[70%]  测试补充           ⏳
[85%]  pytest             ⏳
[95%]  文档收尾           ⏳
[100%] 最终总结 + push    ⏳
```
