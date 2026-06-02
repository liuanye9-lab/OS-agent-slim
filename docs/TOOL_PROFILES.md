# TOOL_PROFILES.md — 工具暴露策略

> 版本: V11.5

---

## Profile 级别

| Profile | 工具数 | 说明 |
|---------|--------|------|
| minimal | 10 | 只暴露核心闭环工具 (默认) |
| default | ~20 | 核心 + eval/skill 调试工具 |
| full | 55 | 暴露所有旧工具 (兼容旧行为) |

---

## Minimal 工具列表 (10 个)

1. `stableagent.task.os_agent` — 主入口
2. `stableagent.trace.get_run` — 运行轨迹查询
3. `stableagent.feedback.correct_and_remember` — 纠正并记住
4. `stableagent.feedback.remember` — 记住这个
5. `stableagent.feedback.dont_do_this_again` — 下次别这样
6. `stableagent.token.report` — Token 报告
7. `stableagent.capsule.status` — 胶囊状态
8. `stableagent.capsule.doctor` — 胶囊健康检查
9. `stableagent.memory.health` — 记忆健康
10. `stableagent.token.summary` — Token 摘要

---

## Default 额外工具 (+10 个)

11. `stableagent.eval.case.create` — 创建评估用例
12. `stableagent.eval.case.list` — 列出评估用例
13. `stableagent.eval.run_ab` — A/B 回归测试
14. `stableagent.eval.evaluate` — 评测输出质量
15. `stableagent.skill.validate` — 验证 Skill
16. `stableagent.skill.export_best` — 导出最佳 Skill
17. `stableagent.memory.retrieve` — 记忆检索
18. `stableagent.skillopt.status` — SkillOpt 状态
19. `stableagent.skillopt.get_current_skill` — 当前技能文档
20. `stableagent.memory.search` — 记忆搜索

---

## 环境变量

```bash
export STABLE_AGENT_TOOL_PROFILE=minimal  # 默认
export STABLE_AGENT_TOOL_PROFILE=default
export STABLE_AGENT_TOOL_PROFILE=full
```

---

## 设计原则

1. **默认安全**: minimal 只暴露必需工具
2. **向后兼容**: full 保留所有旧工具
3. **渐进暴露**: default 增加调试工具
4. **不删除旧工具**: 只是隐藏
