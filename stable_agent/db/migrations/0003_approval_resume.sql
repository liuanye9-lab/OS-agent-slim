-- Production Hardening: Approval Resume 表
-- 存储被阻断的高风险工具调用，供审批恢复执行

CREATE TABLE IF NOT EXISTS approval_pending_calls (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL DEFAULT '{}',
    workspace_id TEXT DEFAULT '',
    project_id TEXT DEFAULT '',
    created_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting_approval'
);

CREATE INDEX IF NOT EXISTS idx_apc_run_id ON approval_pending_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_apc_status ON approval_pending_calls(status);
