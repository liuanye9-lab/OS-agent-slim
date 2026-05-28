# CHANGELOG.md — V6-Professional

## Unreleased (V6-Professional)

### Added
- `EvaluationResult.failure_attribution`: 结构化失败归因（failed_stage + reason + step_index）
- `EvaluationResult.step_efficiency`: 步数效率评分
- `Workflow.sub_steps`: 层级规划子步骤列表
- `BadCase.id` / `BadCase.tags` / `BadCase.source_run_id`: 可追踪案例标识
- `BadCaseManager.convert_to_regression_case()`: 失败案例 → 回归用例转换
- `skills/candidates/` + `skills/rejected/` 目录（用于 Skill Patch 管理）
- `data/regression_cases.jsonl`: 回归测试数据文件
- `SkillExporter.export()` Human Review Gate: 未通过验证或未人工确认时抛出 PermissionError
- `SkillOptimizationEngine.export_best_skill()` 新增 validation_passed / human_reviewed 参数

### Changed
- `EvaluationResult`: 新增 2 字段（向后兼容，field(default=...)）
- `Workflow`: 新增 sub_steps 字段
- `BadCase`: 新增 3 字段（向后兼容，field(default=...) / field(default_factory=...))
- `SkillExporter.export()`: 签名变更，新增 4 个必需参数（breaking change）
- `SkillOptimizationEngine.export_best_skill()`: 签名变更，新增 4 个参数

### Fixed
- BadCase → Regression Case 路径断裂：新增 convert_to_regression_case()
- Validation Gate 非硬约束：SkillExporter 现在强制检查
- Skill Export 无人确认：新增 human_reviewed 硬约束

### Tests
- 792/792 passed，0 回归
- 更新 `test_skill_optimization_engine.py` 中 2 个测试适配新签名

### Docs
- `docs/v6-pro/RESEARCH_REPORT.md`: 研究对标报告（Agent-S/OpenHands/AutoGen Studio/MCP/OSWorld-Human/Reflexion/Voyager/MemGPT）
- `docs/v6-pro/ARCHITECTURE_AUDIT.md`: 闭环节点审计 + 8 个 P0 差距识别
- `docs/v6-pro/UPGRADE_PLAN.md`: P0 修改清单 + 风险控制
- `docs/v6-pro/IMPLEMENTATION_LOG.md`: 逐阶段实施记录
- `docs/v6-pro/CHANGELOG.md`: 本轮变更日志
- `docs/v6-pro/ROADMAP.md`: P0/P1/P2/P3 路线图
- `UPDATED_README.md`: 面试级更新版 README
