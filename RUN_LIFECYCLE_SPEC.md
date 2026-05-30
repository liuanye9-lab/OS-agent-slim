# RUN_LIFECYCLE_SPEC.md — 统一运行生命周期规范

**版本**: V8.1 | **文件**: `stable_agent/runtime/run_lifecycle.py`

---

## 概述

RunLifecycle 是 StableAgent OS 的**唯一状态源**。ToolRouter、DecisionTraceBuilder、Dashboard Observer 的进度、状态标签、头像状态均由此模块驱动。

## 22 阶段定义

```python
class RunStage(StrEnum):
    CREATED = "created"                         # 已创建
    RECEIVED = "received"                       # 接收任务
    INTENT_PARSING = "intent_parsing"           # 理解需求
    CONTEXT_BUDGETING = "context_budgeting"     # 计算预算
    TEMPORAL_MEMORY_RETRIEVING = "temporal_memory_retrieving"  # 找时间记忆
    RAG_RETRIEVING = "rag_retrieving"           # 查找资料
    CONTEXT_COMPRESSING = "context_compressing"  # 压缩上下文
    CONTEXT_BUILDING = "context_building"        # 整理上下文
    PLANNING = "planning"                        # 规划步骤
    ACTING = "acting"                            # 执行任务
    OBSERVING = "observing"                      # 观察结果
    EVALUATING = "evaluating"                    # 评估结果
    FAILURE_ATTRIBUTION = "failure_attribution"   # 分析失败
    REGRESSION_GENERATION = "regression_generation" # 生成错题
    MEMORY_UPDATE_CANDIDATE = "memory_update_candidate" # 候选记忆
    SKILL_PATCH_PROPOSAL = "skill_patch_proposal"   # 提出改法
    VALIDATION = "validation"                    # 验证改法
    HUMAN_REVIEW = "human_review"                # 等待审核
    EXPORTING = "exporting"                      # 导出规则
    COMPLETED = "completed"                      # 完成任务
    FAILED = "failed"                            # 任务失败
    CANCELLED = "cancelled"                      # 已取消
```

## 进度映射

| stage | progress_pct | avatar_state | scene | label_zh |
|-------|-------------|-------------|-------|----------|
| created | 0 | idle | desk | 已创建 |
| received | 5 | listening | desk | 接收任务 |
| intent_parsing | 10 | thinking | thinking_board | 理解需求 |
| context_budgeting | 18 | calculating | budget_panel | 计算预算 |
| temporal_memory_retrieving | 28 | reading_notes | memory_wall | 找时间记忆 |
| rag_retrieving | 38 | searching_books | library | 查找资料 |
| context_compressing | 48 | organizing | context_table | 压缩上下文 |
| context_building | 55 | organizing | context_table | 整理上下文 |
| planning | 63 | planning | map_table | 规划步骤 |
| acting | 72 | tooling | tool_bench | 执行任务 |
| observing | 80 | watching | monitor | 观察结果 |
| evaluating | 86 | grading | exam_table | 评估结果 |
| failure_attribution | 90 | diagnosing | diagnosis_board | 分析失败 |
| regression_generation | 93 | writing_case | case_desk | 生成错题 |
| memory_update_candidate | 95 | reading_notes | memory_wall | 候选记忆 |
| skill_patch_proposal | 96 | learning | skill_book | 提出改法 |
| validation | 97 | grading | exam_table | 验证改法 |
| human_review | 98 | waiting_approval | approval_gate | 等待审核 |
| exporting | 99 | archiving | archive_cabinet | 导出规则 |
| completed | 100 | done | delivery_desk | 完成任务 |
| failed | -1 | failed | error_board | 任务失败 |
| cancelled | -1 | failed | error_board | 已取消 |

## API

```python
from stable_agent.runtime.run_lifecycle import RunStage, RunStageMeta, get_stage_meta

meta = get_stage_meta("planning")
# RunStageMeta(stage=PLANNING, progress_pct=63, status_text_zh="规划步骤",
#              avatar_state="planning", scene="map_table", ...)
```

## 消费者

| 消费者 | 用途 |
|--------|------|
| `ToolRouter._make_event_dict` | 每个事件的 progress_pct/status_text_zh/avatar_state |
| `DecisionTraceBuilder.build_for_dashboard` | Dashboard 事件字典 |
| `Dashboard Observer` (前端) | 进度条、状态卡片、像素人场景 |

## 规则
- ToolRouter **禁止**自己写 progress
- Dashboard **禁止**自己猜进度
- DecisionTraceBuilder 从 RunLifecycle 读取状态
