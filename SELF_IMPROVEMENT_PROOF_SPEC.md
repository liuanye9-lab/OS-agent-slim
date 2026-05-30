# SELF_IMPROVEMENT_PROOF_SPEC.md — 自我优化闭环证明规范

**版本**: V8.1 | **文件**: `stable_agent/self_improvement/`

---

## 闭环流程

```
Eval Result
  ↓
Failure Attribution (_attribute_failure)
  ↓
Regression Case (_generate_regression_cases)
  ↓
Memory Update Candidate (_generate_memory_candidates) [不直接 promote]
  ↓
Skill Patch Candidate (_generate_skill_patches) [只生成 candidate]
  ↓
Validation Gate (RegressionValidationRunner.validate_patch)
  ↓
Human Review (HumanReviewQueue.submit)
  ↓
best_skill.md (approve_patch → _export_best_skill_versioned)
```

## 关键约束

| 约束 | 实现 | 状态 |
|------|------|------|
| 失败经验只能进入 candidate | MemoryUpdateStatus.CANDIDATE | ✅ |
| Skill patch 不能绕过 validation gate | RegressionValidationRunner | ✅ |
| best_skill.md 不能绕过 human review | approve_patch() → export | ✅ |
| 不在无失败时强制触发学习 | eval_passed or score >= min_confidence → skip | ✅ |
| 不自动覆盖 best_skill.md | _export_best_skill_versioned 保留版本 | ✅ |

## ValidationReport

```python
@dataclass
class ValidationReport:
    report_id: str
    run_id: str
    patch_id: str | None
    old_score: float
    new_score: float
    delta: float
    passed: bool              # new_score > old_score AND all cases passed
    case_results: list[ValidationCaseResult]
    reason_zh: str
    created_at: float
```

## 验证规则

| 条件 | 结果 |
|------|------|
| new_score <= old_score | passed=False |
| 无 regression cases | passed=False (低置信度) |
| 无 failure_attribution | passed=False |
| 无 source_run_id | passed=False |
| passed=False | 不进 Human Review |
| passed=True | 进入 Human Review |
| Human Review approved | 允许 export best_skill.md |

## RegressionValidationRunner

```python
class RegressionValidationRunner:
    min_delta: float = 0.01
    llm_weight: float = 0.7    # LLM 评分权重
    rule_weight: float = 0.3   # 规则评分权重

    def validate_patch(patch, regression_cases, old_skill, candidate_skill) -> ValidationReport:
        # 规则评分：specificity + actionability + constraint_clarity + safety
        # LLM 评分（可选）：提供 llm_client 时启用混合模式
        # 混合：score = llm_score * 0.7 + rule_score * 0.3
        # delta > min_delta → passed
```

## V8.1 变更

**_generate_skill_patches 不再自动推进状态线**（原行为：start_validation → mark_validated → submit_for_review）。现在只生成 candidate，验证由 evaluate_and_learn 中的 RegressionValidationRunner 驱动。
