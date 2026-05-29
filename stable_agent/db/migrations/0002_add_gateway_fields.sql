-- Migration 0002: Gateway Fields
-- Created: 2026-05-29

ALTER TABLE agent_runs ADD COLUMN intent_alignment_score REAL;
ALTER TABLE agent_runs ADD COLUMN learning_triggered INTEGER DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN skill_updated INTEGER DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN bad_case_count INTEGER DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN regression_case_count INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace ON audit_logs(workspace_id, created_at);
