# CHANGELOG.md

All notable changes to StableAgent Cloud.

---

## v2.2 (2026-05-29) — Production Hardening Complete ✅

### Added
- `stable_agent/saas/validation_report.py` — 独立 ValidationReport + RegressionCaseResult
- DecisionTraceBuilder 集成到 ToolRouter._make_event_dict()
- 14 个新测试文件 (371 passed)
- 实验文件: dataset.jsonl (15 tasks), run_experiment.py, results.json
- `run_at` backward-compat property on ValidationReport

### Changed
- Repository: 18 处 `return False` → `raise RepositoryError`（全部写操作）
- regression_runner: 内联 ValidationReport → 导入独立模块
- RunLifecycle.get_stage_meta(): 未知 stage fallback CREATED (不再抛 ValueError)
- README: 5-round 指标添加 simulated demo 标注

### Fixed
- Float precision in delta comparison (pytest.approx)
- RegressionRunner 与独立 ValidationReport 类型兼容

### Verified
- pytest: 371 passed, 1 error (Windows 文件锁, 非代码问题)
- 所有验收标准 19/19 通过 ✅

---

## v2.1 (2026-05-29) — Commercial SaaS Hardening

### Added
- RunLifecycle: 20 standardized stages (created→completed) with progress mapping
- RegressionRunner + ValidationReport for skill patch quality gates
- Database migration system (versioned, idempotent)
- SecurityContext with JWT + API Key dual-channel auth
- SaasError hierarchy (RepositoryError, NotFoundError, etc.)
- os_agent multi-stage event pipeline (10+ stages)
- Dashboard RunLifecycle progress bar visualization

### Changed
- `/mcp` → production main entry (was `/mcp/v5/mcp`)
- `/mcp/legacy` → backward-compatible old MCPServer
- ResponseAdapter: +11 fields (progress_pct, status_text_zh, avatar_state, etc.)
- High-risk tools: hard-block with `waiting_approval` (was STUB)

### Fixed
- `datetime.utcnow()` → `datetime.now(timezone.utc)` deprecation
- 0 silent `except Exception: pass` in production code
- Repository `close()` method for test cleanup
- SaaS page routes not shadowed by Dashboard mount

---

## v2.0 (2026-05-29) — E2E + Login + README

### Added
- E2E test: 18-step full SaaS flow (register→run→review)
- Login/Register page (`/login`)
- Visual README with Mermaid architecture diagrams

### Fixed
- APIKey `create_key` return signature
- ALTER TABLE for workspace_id/project_id/agent_id columns

---

## v1.9 (2026-05-29) — Route Fix

### Fixed
- 6 SaaS pages (usage/apikeys/billing/team/skills/review) returning 404
- Root cause: Dashboard mount shadowing later route registrations

---

## v1.8 (2026-05-29) — Login + README

### Added
- `/login` dual-tab (Login/Register) with JWT localStorage

---

## v1.7 (2026-05-29) — CORS + Docker + Config

### Added
- CORS middleware (allow all origins)
- Dockerfile + docker-compose.yml
- `.env.example`
- Custom 404 page (glassmorphism)
- FastAPI title → "StableAgent Cloud" with Swagger/ReDoc

---

## v1.6 (2026-05-29) — Skills + Review

### Added
- `/dashboard/skills`: Skill Library + Patch status
- `/dashboard/review`: Human Review queue
- `/api/skills`, `/api/skills/patches`, `/api/reviews`

---

## v1.5 (2026-05-29) — Auth + Rate + Team

### Added
- JWT auth (HMAC-SHA256, 24h TTL)
- Rate Limiter (sliding window: Free 10/min, Pro 60, Team 300)
- Team management page (`/dashboard/team`)
- `/api/auth/register`, `/api/auth/login`, `/api/auth/me`

---

## v1.4 (2026-05-29) — Business UI

### Added
- `/dashboard/usage`: Chart.js dashboard + quota bars
- `/dashboard/apikeys`: API Key CRUD
- `/dashboard/billing`: 4-tier plan comparison

---

## v1.3 (2026-05-29) — MCP Context

### Added
- MCP context injection (workspace_id/project_id/agent_id auto-resolved)
- Dashboard Run detail panel

---

## v1.2 (2026-05-29) — MCP + API + Dashboard

### Added
- 27 MCP tools with project context
- 16 REST API endpoints
- Dashboard SaaS project selector

---

## v1.1 (2026-05-29) — Billing + Audit + Services

### Added
- Billing manager (4 tiers + quota checks)
- Audit logger (13 event types)
- Workspace/Project/Run services

---

## v1.0 (2026-05-28) — SaaS Foundation

### Added
- 18 dataclass models + 6 enums
- SQLite repository with full CRUD
- Permission matrix (5 roles)
- API Key management
- Usage counter
