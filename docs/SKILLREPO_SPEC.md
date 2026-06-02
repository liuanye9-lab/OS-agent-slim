# SKILLREPO_SPEC.md — SkillRepo 技能库规范

## 1. 技能包格式

每个技能以目录形式存储：

```
.stableagent-capsule/skills/packages/<skill_id>/
├── SKILL.md          # 技能文档（必须）
├── metadata.json     # 元数据（必须）
├── CHECKLIST.md      # 检查清单（可选）
├── TEMPLATE.md       # 模板（可选）
├── examples.md       # 示例（可选）
└── scripts/          # 辅助脚本（可选，默认不执行）
```

## 2. Metadata Schema

```json
{
  "skill_id": "skill_xxx",
  "name": "avoid-over-editing",
  "description": "避免大范围重构无关文件",
  "version": 1,
  "status": "active",
  "scope": "global",
  "tags": {
    "topic": ["coding"],
    "capabilities": ["code-editing"],
    "concepts": [],
    "heuristics": ["minimal-diff"],
    "pitfalls": ["global-refactor"]
  },
  "trigger_phrases": ["不要大范围重构"],
  "source_runs": ["run_xxx"],
  "quality_score": 0.8,
  "usage_count": 10,
  "success_count": 8,
  "failure_count": 2,
  "risk_level": "low",
  "created_by": "seed"
}
```

## 3. Version Schema

```json
{
  "id": "ver_xxx",
  "skill_id": "skill_xxx",
  "version": 1,
  "parent_version": null,
  "op_id": "op_xxx",
  "content_hash": "md5hash",
  "metadata_snapshot": {},
  "created_at": 1234567890.0
}
```

## 4. Curation Event Schema

```json
{
  "op_id": "op_xxx",
  "op": "insert_skill",
  "skill_id": "skill_xxx",
  "source_run": "run_xxx",
  "reason": "successful run without matching skill",
  "confidence": 0.8,
  "requires_human_review": true,
  "payload": {},
  "created_at": 1234567890.0
}
```

## 5. 回滚机制

1. 每次 insert/update 自动创建版本快照
2. 回滚 = 从快照恢复元数据 + 创建新版本
3. 回滚不破坏历史版本
4. 回滚生成 curation event

## 6. Lint 规则

1. SKILL.md 必须存在
2. frontmatter 必须完整
3. name 必须 slug 格式
4. 不能包含危险命令
5. 不能过度绑定单个 run
6. 必须有 Procedure
7. 必须有 Verification
8. 不能太长（< 1500 words）
