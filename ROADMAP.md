# ROADMAP.md

StableAgent Cloud 产品路线图。

---

## ✅ Done (v1.0 → v2.1)

- [x] SaaS data models + SQLite repository
- [x] JWT auth + permission matrix (5 roles)
- [x] API Key lifecycle
- [x] Usage metering + billing tiers
- [x] Audit log (13 event types)
- [x] Rate limiter (sliding window)
- [x] MCP Gateway (28 tools, unified `/mcp` entry)
- [x] Workspace/Project/Run CRUD
- [x] CORS + Docker + .env
- [x] 12 frontend pages
- [x] SkillLibrary + HumanReview
- [x] RunLifecycle 20-stage pipeline
- [x] RegressionRunner + ValidationReport
- [x] Database migration system
- [x] E2E test (18-step full flow)
- [x] 923 tests passed
- [x] Commercial SaaS hardening (high-risk blocking, ResponseAdapter fields, permissions)

---

## 🔜 Near Term (v2.2)

- [ ] PostgreSQL support (optional backend)
- [ ] SMTP email notifications (member invite, review request)
- [ ] Webhook integration (run completion → Slack/Teams)
- [ ] Skill patch diff viewer in Dashboard
- [ ] Export formats (JSON, CSV, PDF)
- [ ] Localization: Japanese, Korean

---

## 📋 Mid Term (v3.0)

- [ ] Enterprise SSO (SAML/OIDC)
- [ ] Multi-region deployment
- [ ] Real-time collaboration (WebSocket sync)
- [ ] Advanced analytics (trend detection, anomaly alerting)
- [ ] Skill marketplace (publish/subscribe skills)
- [ ] Team templates (pre-built workspace configs)

---

## 🌟 Long Term (v4.0)

- [ ] AI-powered skill recommendation (auto-apply best patches)
- [ ] Federated learning (privacy-preserving skill sharing)
- [ ] Multi-agent orchestration (agent squad)
- [ ] On-premise deployment package
- [ ] Compliance certifications (SOC2, GDPR)
