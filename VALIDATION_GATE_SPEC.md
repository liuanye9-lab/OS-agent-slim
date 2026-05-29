# Validation Gate Specification

> Skill Patch 验证门规范
> 版本: v2.2

## 概述

Validation Gate 确保任何 Skill Patch 不会降低 Agent 质量。核心规则:

> **new_score > old_score** → 通过
> **new_score <= old_score** → 不通过

## 流程

```
Skill Patch Proposed
    ↓
RegressionRunner.run_cases()
    ↓
    ├── 加载回归用例 (来自 BadCase)
    ├── 使用旧 Skill 作为 baseline → baseline_score
    ├── 使用新 Skill 作为 candidate → candidate_score
    └── 生成 ValidationReport
    ↓
ValidationReport.passed?
    ├── True → 进入 Human Review
    └── False → 打回 Skill Patch，附失败原因
```

## ValidationReport 数据结构

```python
@dataclass
class ValidationReport:
    patch_id: str           # 关联的 Skill Patch ID
    baseline_score: float   # 旧 Skill 评分 (0.0-1.0)
    candidate_score: float  # 新 Skill 评分 (0.0-1.0)
    delta: float            # candidate - baseline
    passed: bool            # candidate > baseline
    case_results: list[RegressionCaseResult]
    failure_summary: str    # 失败原因摘要
    recommendation: str     # 验证建议
```

## RegressionCaseResult

```python
@dataclass
class RegressionCaseResult:
    case_id: str       # 用例 ID
    passed: bool       # 候选 Skill 是否修复了该 BadCase
    score: float       # 0.0-1.0
    failure_reason: str # 未通过原因
```

## 实现位置

- `stable_agent/saas/validation_report.py` — 数据模型
- `stable_agent/saas/regression_runner.py` — 执行器
- MCP Tool: `stableagent.skill.validate` — 对外接口
