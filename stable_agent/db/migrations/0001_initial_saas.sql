-- Migration 0001: Initial SaaS Schema
-- Created: 2026-05-29

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT DEFAULT 'free',
    status TEXT DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    user_id TEXT NOT NULL,
    email TEXT DEFAULT '',
    role TEXT DEFAULT 'developer',
    joined_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL,
    environment TEXT DEFAULT 'production',
    status TEXT DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    name TEXT DEFAULT '',
    created_at REAL NOT NULL,
    revoked_at REAL
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    run_id TEXT,
    event_type TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    cost REAL DEFAULT 0.0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT DEFAULT '',
    target_type TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    workspace_id TEXT,
    project_id TEXT,
    agent_id TEXT,
    status TEXT DEFAULT 'created',
    progress_pct INTEGER DEFAULT 0,
    user_task TEXT DEFAULT '',
    overall_score REAL,
    token_used INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0.0,
    dashboard_url TEXT DEFAULT '',
    trace_url TEXT DEFAULT '',
    started_at REAL,
    ended_at REAL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_records (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    project_id TEXT,
    name TEXT NOT NULL,
    version TEXT DEFAULT '1.0.0',
    content TEXT NOT NULL,
    score REAL DEFAULT 0.0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_patches (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    project_id TEXT,
    skill_id TEXT,
    patch_type TEXT DEFAULT 'prompt',
    patch_diff TEXT DEFAULT '',
    old_score REAL DEFAULT 0.0,
    new_score REAL DEFAULT 0.0,
    delta REAL DEFAULT 0.0,
    status TEXT DEFAULT 'candidate',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS human_reviews (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    reviewer TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    comment TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS regression_cases (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    project_id TEXT,
    failure_mode TEXT NOT NULL,
    repair_keywords TEXT DEFAULT '[]',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    quality_score REAL,
    hallucination_rate REAL,
    intent_alignment_score REAL,
    memory_hit_rate REAL,
    scores TEXT DEFAULT '{}',
    overall_score REAL,
    failure_attribution TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS saas_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(status);
CREATE INDEX IF NOT EXISTS idx_projects_workspace ON projects(workspace_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_run_id ON agent_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_workspace ON agent_runs(workspace_id, project_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_project ON usage_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_saas_users_email ON saas_users(email);
CREATE INDEX IF NOT EXISTS idx_human_reviews_status ON human_reviews(status);
CREATE INDEX IF NOT EXISTS idx_skill_patches_status ON skill_patches(status);
