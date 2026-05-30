# FINAL DASHBOARD SYNC AUDIT — V8.1 State

## Event Schema

Every event published by the backend now carries these fields:

| Field | Type | Purpose |
|---|---|---|
| `progress_pct` | float 0–100 | Normalized progress |
| `status_text_zh` | string | Human-readable status (Chinese) |
| `avatar_state` | string | Avatar visual state key (e.g. "thinking", "acting", "done") |
| `decision_summary_zh` | string | What was decided at this stage |
| `why_zh` | string | Rationale for the decision |
| `next_step_zh` | string | What happens next |

## Published Event Sequence

Events flow in this order (not all emit every run):

1. `task.received`
2. `intent.parsed`
3. `context.budgeted`
4. `temporal_memory.retrieved`
5. `rag.retrieved`
6. `context.compression_guard.checked`
7. `context.built`
8. `workflow.plan.created`
9. `workflow.step.started` … `workflow.step.completed` (per step, can repeat)
10. `eval.completed`
11. `self_improvement.checked`
12. `task.completed`

Each event is enriched with the full schema above.

## WebSocket SSE Subscription

The dashboard maintains a live Server-Sent Events subscription via WebSocket.
**Status:** Active. Connection is established on page load and persists through
the run lifecycle.

## Frontend Data Policy

- Frontend renders **only** data received from backend events.
- No client-side guessing of progress, state, or avatar status.
- If no event arrives, the dashboard shows the last known state (nothing fabricated).

## Sync Verification

- Event `timestamp` field allows frontend to detect out-of-order events.
- Event `run_id` field prevents cross-run contamination.
- Frontend ignores events whose `run_id` does not match the active session.
