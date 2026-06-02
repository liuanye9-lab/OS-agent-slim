# SKILL_DASHBOARD_GUIDE.md — Skill Dashboard 使用指南

## 1. 查看技能库

访问 `http://127.0.0.1:18789/skills`

Dashboard 显示：
- **Stats**：active/archived/deleted 技能数量、版本数、curation ops 数
- **Skill List**：所有 active 技能的卡片视图
- **Curation Events**：最近的策展事件时间线

## 2. 搜索技能

1. 点击 "Search" tab
2. 输入搜索关键词
3. 支持按 name、description、trigger_phrases、tags 搜索
4. 结果按匹配分数排序

## 3. 查看技能详情

1. 点击任意技能卡片
2. 切换到 "Detail" tab
3. 查看：
   - SKILL.md 内容
   - 元数据（status、version、quality_score）
   - 标签和触发短语
   - 版本历史
   - Curation 事件

## 4. 审核 Curation Op

1. 查看 "Curation Events" tab
2. 找到 requires_human_review=true 的事件
3. 通过 MCP 工具 `stableagent.skill.apply_op` 应用

## 5. 回滚 Skill

CLI 方式：
```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli skill rollback \
  --skill-id <skill_id> \
  --target-version 1 \
  --json
```

Dashboard 方式：
```bash
curl -X POST http://127.0.0.1:18789/api/skills/rollback \
  -H "Content-Type: application/json" \
  -d '{"skill_id": "<skill_id>", "target_version": 1}'
```

## 6. 查看技能效果

```bash
curl http://127.0.0.1:18789/api/skills/attribution/summary
curl http://127.0.0.1:18789/api/skills/attribution/<skill_id>
```

返回：
- usage_count
- success_rate
- quality_score
- stale_score
- pollution_risk_score
