"""Evaluation and validation package (V4 Phase 4).

Provides evaluation frameworks and validation gating for candidate
skill versions in the Skill Optimization loop.

Modules:
- validation_dataset: JSONL-based validation case management
- regression_suite: Regression detection for critical task types
- rubric_judge: Heuristic-based multi-dimensional scoring
"""

from .validation_dataset import ValidationDataset
from .regression_suite import RegressionSuite
from .rubric_judge import RubricJudge

__all__ = [
    "ValidationDataset",
    "RegressionSuite",
    "RubricJudge",
]
