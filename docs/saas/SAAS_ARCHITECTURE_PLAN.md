# SAAS_ARCHITECTURE_PLAN.md — 架构升级计划

> 版本：SaaS v1.0-MVP | 日期：2026-05-28

## 1. 当前架构

```
┌──────────────────────────────────────────────────────────┐
│                   web/server.py (FastAPI)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ /mcp/v5  │  │ /mcp     │  │ /dashboard, /runs/*  │   │
│  │ Gateway  │  │ Legacy   │  │ HTML template render  │   │
│  └────┬─────┘  └──────────┘  └──────────────────────┘   │
│       │                                                   │
│  ┌────┴──────────────────────────────────────────┐      │
│  │  stable_agent/ (单机模式)                       │      │
│  │  ├── models.py         (dataclass, 无workspace) │      │
│  │  ├── storage.py        (SQLite, 7张表)         │      │
│  │  ├── gateway/          (MCP Gateway V5)        │      │
│  │  ├── skill_optimizer/  (Validation+Export)     │      │
│  │  ├── observation/      (RunStore+EventStream)  │      │
│  │  ├── eval_and_bad_case.py                      │      │
│  │  └── ...                                       │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  Data: data/stable_agent.sqlite3 (单文件)                 │
└──────────────────────────────────────────────────────────┘
```

## 2. 目标架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     web/server.py (FastAPI)                      │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────────────┐   │
│  │ /mcp/v5  │  │ /mcp     │  │ /dashboard/v3                │   │
│  │ Gateway  │  │ Legacy   │  │ /runs/{id}                   │   │
│  │ + SaaS   │  │          │  │ /api/projects/*   ★新增     │   │
│  └────┬─────┘  └──────────┘  │ /api/runs/*                   │   │
│       │                       │ /connect                      │   │
│  ┌────┴───────────────────────┴──────────────────────────┐   │
│  │  stable_agent/ (SaaS模式)                              │   │
│  │  ├── models.py         (扩展 SaaS models)              │   │
│  │  ├── storage.py        (扩展 SaaS tables)              │   │
│  │  ├── gateway/          (MCP Gateway + project context) │   │
│  │  ├── saas/             ★新增                            │   │
│  │  │   ├── models.py           (Workspace/Project/...)   │   │
│  │  │   ├── repository.py      (数据访问层)               │   │
│  │  │   ├── service.py         (业务逻辑层)               │   │
│  │  │   ├── usage.py           (用量计数器)               │   │
│  │  │   ├── permissions.py     (权限校验)                 │   │
│  │  │   ├── api_keys.py        (API Key管理)              │   │
│  │  │   ├── regression_service.py  (回归服务)            │   │
│  │  │   └── skill_review_service.py (Skill审核服务)      │   │
│  │  ├── skill_optimizer/  (Validation+Export, 已有)      │   │
│  │  ├── observation/      (RunStore+EventStream, 已有)   │   │
│  │  └── eval_and_bad_case.py (已有)                      │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Data: data/stable_agent.sqlite3 (扩展 SaaS 表)                │
│  SaaS表: workspaces, projects, api_keys, usage_events, ...    │
└──────────────────────────────────────────────────────────────────┘
```

## 3. 兼容策略

### 3.1 双模式运行

```python
# local 模式（现有行为，不破坏）
Mode.LOCAL:
  - project_id optional，fallback到default
  - 无权限校验

# saas 模式（新增）
Mode.SAAS:
  - project_id required
  - API Key校验
  - 权限隔离
```

### 3.2 数据模型扩展到SaaS

```python
# 现有 RunRecord（不变）
@dataclass
class RunRecord:
    run_id: str
    user_task: str
    # ... 现有字段不变

# 新增 SaaS 扩展（在 saas/models.py 中）
@dataclass
class AgentRun:  # SaaS版本，包装RunRecord
    run_id: str
    workspace_id: str
    project_id: str
    agent_id: str
    # 委托给 RunRecord 的字段
```

**策略**：不修改现有RunRecord，在saas层创建AgentRun包装类。storage.py增加project_id列（默认NULL兼容旧数据）。

### 3.3 向后兼容保证

1. 所有现有MCP工具参数不变
2. 新的project_id参数为optional（local模式）
3. 现有792个测试不受影响
4. 现有API端点不变

## 4. 迁移策略

### Phase 1: Scaffold（本轮）
1. 新增 `stable_agent/saas/` 模块
2. SaaS数据模型定义
3. 数据库表扩展（ALTER TABLE加列 + 新表）
4. RunContext升级
5. MCP project_context
6. 回归+审核服务

### Phase 2: Dashboard升级（本轮）
7. 路由扩展
8. 前端workspace/project selector
9. Run详情页

### Phase 3: 测试+文档（本轮）
10. 新增测试覆盖
11. 文档产出
12. pytest验证

### Phase 4: 部署（未来）
13. 环境变量配置
14. SaaS模式启动
15. CI/CD

## 5. 数据模型

### 5.1 新增表（SQLite）

```sql
-- 工作空间
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at REAL NOT NULL,
    settings TEXT DEFAULT '{}'
);

-- 项目
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at REAL NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
);

-- API Keys
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at REAL NOT NULL,
    revoked_at REAL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
);

-- 用量事件
CREATE TABLE usage_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    run_id TEXT,
    event_type TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0.0,
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);

-- 回归用例
CREATE TABLE regression_cases (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_input TEXT NOT NULL,
    expected_behavior TEXT DEFAULT '',
    failure_mode TEXT DEFAULT 'unknown',
    source_run_id TEXT,
    source_bad_case_id TEXT,
    tags TEXT DEFAULT '[]',
    overall_score REAL,
    created_at REAL NOT NULL
);

-- Skill记录
CREATE TABLE skill_records (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    current_version TEXT DEFAULT 'v1.0',
    content TEXT NOT NULL,
    score REAL DEFAULT 0.0,
    created_at REAL NOT NULL,
    updated_at REAL
);

-- 审核记录
CREATE TABLE human_reviews (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    reviewer TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    comment TEXT DEFAULT '',
    created_at REAL NOT NULL,
    resolved_at REAL
);
```

### 5.2 现有表扩展

```sql
-- runs 表：新增3列（NULL兼容旧数据）
ALTER TABLE runs ADD COLUMN workspace_id TEXT;
ALTER TABLE runs ADD COLUMN project_id TEXT;
ALTER TABLE runs ADD COLUMN agent_id TEXT;

-- trace_spans 表：新增1列
ALTER TABLE trace_spans ADD COLUMN project_id TEXT;

-- bad_cases 表：新增2列
ALTER TABLE bad_cases ADD COLUMN workspace_id TEXT;
ALTER TABLE bad_cases ADD COLUMN project_id TEXT;

-- eval_cases 表：新增2列
ALTER TABLE eval_cases ADD COLUMN workspace_id TEXT;
ALTER TABLE eval_cases ADD COLUMN project_id TEXT;
```

## 6. API 边界

### 6.1 MCP 边界

```
/mcp/v5/mcp  → JSON-RPC 2.0
  ├── tools/list     (返回所有工具)
  ├── tools/call     (执行工具，携带 project_id)
  └── initialize     (初始化，可带 API Key)

/mcp/v5/mcp?run_id=xxx  → SSE events
```

### 6.2 REST 边界

```
/api/projects        → CRUD 项目
/api/runs/{id}       → 运行数据（已有，扩展返回project_id）
/api/usage           → 用量查询（新增）
/api/keys            → API Key管理（新增）
/dashboard/v3        → HTML Dashboard（已有）
/runs/{id}           → Run 详情页（已有）
```

## 7. MCP 边界

### 7.1 工具路由变更

```
tools/call 请求新增字段:
  {
    "name": "stableagent.task.os_agent",
    "arguments": {
      "task_input": "...",
      "project_id": "proj_xxx",     // 新增
      "agent_id": "agent_xxx"       // 新增
    }
  }
```

### 7.2 新增工具（在 UnifiedToolRegistry 注册）

```
stableagent.project.create
stableagent.project.list
stableagent.run.get
stableagent.run.list
stableagent.trace.get
stableagent.eval.run
stableagent.regression.create
stableagent.skill.patch_propose
stableagent.skill.validate
stableagent.skill.review
stableagent.skill.export_best
stableagent.usage.get
```

## 8. Worker 边界

当前无独立Worker。本轮不引入异步Worker队列。所有操作同步执行（MCP tools/call → 即时处理）。

## 9. Dashboard 边界

```
当前 Dashboard：
  / → dashboard.html (V1)
  /dashboard/v2 → dashboard_v2.html
  /dashboard/v3 → dashboard_v3.html
  /runs/{run_id} → run详情

SaaS 新增：
  /api/projects → JSON API
  /api/projects/{id}/runs → 项目运行列表
  /api/projects/{id}/usage → 用量
  Dashboard V3 前端升级：
    - Workspace/Project selector
    - Runs list（侧栏）
    - Usage panel（底部）
```

## 10. 安全边界

### MVP安全模型
- API Key → Workspace级访问
- Key = SHA256 hash 存储
- 请求头携带：`X-API-Key: sk_xxx`
- SaaS模式下未携带或无效key返回401
- local模式下跳过key校验

### P1安全模型（后续）
- Key → Project级访问
- Rate limiting
- IP白名单

## 11. 文件变更清单

### 新增文件
```
stable_agent/saas/__init__.py
stable_agent/saas/models.py
stable_agent/saas/repository.py
stable_agent/saas/service.py
stable_agent/saas/usage.py
stable_agent/saas/permissions.py
stable_agent/saas/api_keys.py
stable_agent/saas/regression_service.py
stable_agent/saas/skill_review_service.py
```

### 修改文件
```
stable_agent/models.py                  (新增 SaaS 相关 dataclass)
stable_agent/storage.py                 (扩展表)
stable_agent/gateway/run_context.py     (加 workspace_id/project_id)
stable_agent/gateway/mcp_gateway.py     (project_context 注入)
stable_agent/gateway/unified_tool_registry.py (新增工具注册)
web/server.py                           (新增 REST API 路由)
web/templates/dashboard_v3.html         (Workspace/Project selector)
web/static/liquid_glass.css             (SaaS 样式)
```

### 新增测试
```
tests/test_saas_models.py
tests/test_workspace_project.py
tests/test_project_run_scope.py
tests/test_usage_counter.py
tests/test_api_keys.py
tests/test_mcp_project_context.py
tests/test_regression_from_badcase.py
tests/test_skill_validation_review.py
tests/test_saas_dashboard_routes.py
```

### 新增文档
```
docs/saas/SAAS_ARCHITECTURE_AUDIT.md  ✅ 已完成
docs/saas/PRD.md                       ✅ 已完成
docs/saas/SAAS_ARCHITECTURE_PLAN.md    ✅ 当前文件
docs/saas/RESEARCH_REPORT.md          (进行中)
docs/saas/UPGRADE_PLAN.md             (进行中)
docs/saas/IMPLEMENTATION_LOG.md       (进行中)
docs/saas/CHANGELOG.md                (进行中)
docs/saas/ROADMAP.md                  (进行中)
UPDATED_README.md                     (待更新)
```
