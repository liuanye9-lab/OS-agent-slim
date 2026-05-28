# ROADMAP.md — StableAgent Cloud 路线图

## 已完成

### v0.x (2026年初)
- [x] 记忆管理、上下文预算、工作流引擎
- [x] MCP Gateway V3 → V5
- [x] Dashboard V1 → V2 → V3（iOS玻璃拟态）
- [x] DecisionTrace / 决策可解释

### v5.6 (2026-05)
- [x] 工程治理升级：55→0 静默吞异常
- [x] EventStream.publish_sync()
- [x] 792+ 测试

### v6.5 (2026-05)
- [x] /os-agent MCP tool
- [x] Dashboard V3 + 一键接入页面
- [x] Claude Code / Codex skill 文件

### v6-Professional (2026-05)
- [x] 结构化失败归因
- [x] BadCase→Regression转换
- [x] Validation Gate硬约束
- [x] Human Review Gate硬约束

### SaaS v1.0 (2026-05-28) 🎯 当前版本
- [x] 16个SaaS数据模型
- [x] Workspace/Project多租户
- [x] Run→Project→Workspace归属
- [x] MCP project_context
- [x] Eval→Regression→Skill Review完整闭环
- [x] Usage Counter
- [x] API Key管理
- [x] 871 tests (全部通过)
- [x] 8个文档交付

## 计划中

### SaaS v1.1 (P1 — 2026-06)
- [ ] Workspace成员管理UI
- [ ] API Key创建/撤销UI
- [ ] Usage面板
- [ ] Skill跨project共享
- [ ] Dashboard Run详情页

### SaaS v1.2 (P1 — 2026-07)
- [ ] Policy as Code（声明式Agent策略）
- [ ] OTEL标准化导出
- [ ] Red Team安全测试
- [ ] Billing scaffold 接 Stripe

### SaaS v2.0 (P2 — 2026-Q3)
- [ ] PostgreSQL迁移
- [ ] SSO/OAuth
- [ ] RBAC权限系统
- [ ] 私有部署

### SaaS v3.0 (P2 — 2026-Q4)
- [ ] Multi-agent协作面板
- [ ] Agent技能市场
- [ ] 企业级合规审计
