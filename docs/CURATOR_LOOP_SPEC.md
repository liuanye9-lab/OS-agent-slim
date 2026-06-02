# CURATOR_LOOP_SPEC.md — Skill Curator Loop 规范

## 1. 触发条件

### insert_skill
- 任务成功
- 没有命中任何 skill
- 有明确的 task_input

### update_skill
- 任务成功且命中了 skill → 补充成功路径
- 任务失败且命中了 skill → 增加 pitfall

### delete_skill
- 仅通过人工审核触发

### archive_skill
- 某 skill 多次失败（failure_count > success_count * 2）
- 30 天未使用
- quality_score < 0.3

### merge_skill
- 两个 skill trigger 高度相似
- 必须人工审核

## 2. Human Review 策略

默认 requires_human_review=true 的操作：
- update（除非 confidence >= 0.8 且 risk_level=low）
- delete
- archive
- merge

可自动应用的操作：
- insert（confidence >= 0.8 且 risk_level=low）

## 3. Auto Apply 策略

```python
if auto_apply and op.confidence >= 0.8:
    if op.op == INSERT_SKILL and op.new_skill.risk_level == LOW:
        # 自动应用
```

## 4. Bad Case → Skill

用户反馈 "dont-do-this-again" →
1. 记录 BadCase
2. 创建 EvalCase
3. 生成 SkillPatchCandidate
4. Curator 生成 anti-pattern skill

## 5. Feedback → Skill

用户纠正表达习惯 →
1. 记录 ExpressionProfile
2. Curator 生成 expression skill
3. 例如："不要AI味" → no-ai-flavor-writing

## 6. Judge 逻辑

### OutcomeJudge
- task.completed + tests.passed → success (confidence=0.9)
- task.completed → success (confidence=0.7)
- task.failed → failure (confidence=0.8)
- user negative feedback → failure (confidence=0.7)

### ContentJudge
- safety: 检查危险命令
- abstractness: 检查是否过度绑定
- reusability: 检查可复用性
- executability: 检查步骤明确性
- compression: 检查内容长度
