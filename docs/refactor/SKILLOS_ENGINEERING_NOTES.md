# SKILLOS_ENGINEERING_NOTES.md — SkillOS 工程适配笔记

> 论文: SkillOS: Learning Skill Curation for Self-Evolving Agents
> 适配日期: 2026-06-02

---

## 1. 论文核心思想 (工程视角)

### 1.1 三组件架构
- **Executor** (冻结): 执行任务，不参与学习
- **Curator** (独立): 分析执行轨迹，提炼技能候选
- **SkillRepo** (外部): 存储和管理技能

### 1.2 延迟验证
- 技能不立即写入长期记忆
- 只有通过后续相关任务验证的技能才能 promote
- 失败经验不会直接写入 SkillRepo

### 1.3 技能进化闭环
```
Task → Executor → Trace → Curator → Candidate → Validation → Promote/Reject → SkillRepo → 下次任务
```

---

## 2. 工程适配决策

### 2.1 不复现的部分
- ❌ RL Curator 训练
- ❌ 复杂 split 策略
- ❌ 大规模向量召回
- ❌ 多租户计费系统

### 2.2 已实现的部分
- ✅ Executor 独立 (`core/executor.py`)
- ✅ Curator 独立 (`core/curator.py`)
- ✅ SkillRepo 文件+SQLite (`skills/`)
- ✅ ValidationGate (`core/validator.py`)
- ✅ 规则型 learning-worthy 判断
- ✅ 多维 reward proxy
- ✅ Promotion policy
- ✅ dry_run_learning 安全边界
- ✅ Skill 生命周期 (draft→candidate→validated→promoted→deprecated→archived)

### 2.3 待实现的部分
- ⏳ Delayed validation (基于 related tasks 的真实验证)
- ⏳ 回归测试自动化
- ⏳ Canary 灰度发布
- ⏳ Human review UI 集成

---

## 3. Reward Proxy 设计

### 3.1 权重分配
```python
REWARD_WEIGHTS = {
    "task_outcome": 0.35,       # 任务结果分数
    "event_completeness": 0.20, # 事件链完整性
    "content_quality": 0.15,    # 输出内容质量
    "compression": 0.15,        # 上下文压缩效率
    "token_efficiency": 0.10,   # Token 使用效率
    "latency": 0.05,            # 响应延迟
    "regression_penalty": 0.30, # 回归惩罚
}
```

### 3.2 计算公式
```
reward = 0.35 * task_outcome
       + 0.20 * event_completeness
       + 0.15 * content_quality
       + 0.15 * compression
       + 0.10 * token_efficiency
       + 0.05 * latency
       - 0.30 * regression_penalty
```

### 3.3 说明
- 这是工程推断，不声称复现论文公式
- 第一版使用简单启发式，后续可根据数据调整权重

---

## 4. Promotion Policy

### 4.1 Promotion 条件
- schema_valid = true
- validations >= 2
- regression_count = 0
- score_delta >= +0.03
- event_completeness = 1.0
- token_delta <= +0.10
- high-risk skill 必须 human_review

### 4.2 Canary 条件
- validations >= 1
- score_delta >= +0.01
- regression_count = 0

### 4.3 dry_run_learning 安全边界
- 可以生成 candidate
- 可以写 validation record
- 不允许 promote
- 不允许 export best_skill.md

---

## 5. Skill 生命周期

```
draft → candidate → validated → promoted → deprecated → archived
```

### 5.1 状态转换规则
- draft → candidate: schema 通过
- candidate → validated: 至少一次 validation 通过
- validated → promoted: 达到 promotion policy
- promoted → deprecated: 失败次数过多或被新版替代
- deprecated → archived: 长期不用

### 5.2 检索策略
- 只有 `promoted` 才进入默认检索
- `candidate` 不参与检索
- `deprecated` 不参与检索
