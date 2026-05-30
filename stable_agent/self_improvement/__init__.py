"""self_improvement — Agent 自我优化闭环。

实现从 Eval → Failure Attribution → Regression Case → 
Memory Update Candidate → Skill Patch Candidate → 
Validation Gate → Human Review → best_skill.md 的完整闭环。

关键约束：
- 失败经验只能进入 candidate，不能直接 promoted
- Skill patch 不能绕过 validation gate
- best_skill.md 不能绕过 human review
"""

from stable_agent.self_improvement.proof_loop import SelfImprovementProofLoop
from stable_agent.self_improvement.memory_update_candidate import (
    MemoryUpdateCandidate,
    MemoryUpdateStatus,
    MemoryUpdateStore,
)
from stable_agent.self_improvement.skill_patch_candidate import (
    SkillPatchCandidate,
    SkillPatchStatus,
    SkillPatchStore,
)
from stable_agent.self_improvement.self_improvement_report import (
    MemoryCandidateEntry,
    RegressionCaseEntry,
    SelfImprovementReport,
    SkillPatchEntry,
)
from stable_agent.self_improvement.regression_validation_runner import (
    RegressionValidationRunner,
)
from stable_agent.self_improvement.validation_report import (
    ValidationReport,
    ValidationCaseResult,
)
from stable_agent.self_improvement.human_review_queue import (
    HumanReviewQueue,
    ReviewRequest,
)

__all__ = [
    "SelfImprovementProofLoop",
    "MemoryUpdateCandidate",
    "MemoryUpdateStatus",
    "MemoryUpdateStore",
    "SkillPatchCandidate",
    "SkillPatchStatus",
    "SkillPatchStore",
    "MemoryCandidateEntry",
    "RegressionCaseEntry",
    "SelfImprovementReport",
    "SkillPatchEntry",
    "RegressionValidationRunner",
    "ValidationReport",
    "ValidationCaseResult",
]
