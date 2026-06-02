# SKILLOS_ADAPTATION.md — SkillOS 工程适配笔记

> 参考论文: SkillOS: Learning Skill Curation for Self-Evolving Agents
> 适配日期: 2026-06-02
> 适配原则: 只借鉴工程思想，不复现 RL 训练

---

## 1. SkillOS 核心思想

### 1.1 Executor 冻结
- Executor 只负责执行，不负责学习
- 执行结果通过 RunTrace 输出
- Executor 不知道 Curator 的存在

### 1.2 Curator 独立
- Curator 只分析 trace，不修改 executor
- Curator 产出 SkillCandidate，不直接写入 SkillRepo
- Curator 通过 ValidationGate 间接影响 SkillRepo

### 1.3 SkillRepo 外部化
- Skill 不是内存对象，是文件 + 索引
- Skill 有完整生命周期
- Skill 状态变化有审计日志

### 1.4 Validation Gate 延迟
- Candidate 不允许直接 promoted
- 必须通过 related task 验证
- dry_run_learning=true 时禁止 promote

---

## 2. 工程适配

### 2.1 不复现的部分
- ❌ RL 训练
- ❌ 复杂 split 策略
- ❌ 大规模向量召回
- ❌ 多租户计费

### 2.2 已实现的部分
- ✅ Executor 独立 (core/executor.py)
- ✅ Curator 独立 (core/curator.py)
- ✅ SkillRepo 文件 + SQLite (skills/)
- ✅ ValidationGate (core/validator.py)
- ✅ 规则型 learning-worthy 判断
- ✅ Reward proxy 计算
- ✅ Promotion policy
- ✅ dry_run_learning 安全边界

### 2.3 待实现的部分
- ⏳ Delayed validation (基于 related tasks)
- ⏳ 真正的回归测试
- ⏳ Canary 灰度发布
- ⏳ Human review 集成

---

## 3. 核心闭环

```
Task → AgentExecutor 执行 → RunTrace
  → CuratorService 分析 → SkillCandidate
  → ValidationGate 验证 → ValidationResult
  → Promotion Decision → SkillRepo
  → 下次任务检索使用
```

---

## 4. Reward Proxy

### 4.1 权重分配
```python
REWARD_WEIGHTS = {
    "task_outcome": 0.35,       # 任务结果
    "event_completeness": 0.20, # 事件完整性
    "content_quality": 0.15,    # 内容质量
    "compression": 0.15,        # 压缩效率
    "token_efficiency": 0.10,   # Token 效率
    "latency": 0.05,            # 延迟
    "regression_penalty": 0.30, # 回归惩罚
}
```

### 4.2 计算公式
```python
reward = (
    0.35 * task_outcome
    + 0.20 * event_completeness
    + 0.15 * content_quality
    + 0.15 * compression
    + 0.10 * token_efficiency
    + 0.05 * latency
    - 0.30 * regression_penalty
)
```

---

## 5. Promotion Policy

### 5.1 Promotion 条件
- schema_valid = true
- validations >= 2
- regression_count = 0
- score_delta >= +0.03
- event_completeness = 1.0
- token_delta <= +0.10
- high-risk skill 必须 human_review

### 5.2 Canary 条件
- validations >= 1
- score_delta >= +0.01
- regression_count = 0
