# FINAL INTEGRATION TEST AUDIT — V8.1 State

## integration_test.py

### Checks Performed

| Test | What It Verifies |
|---|---|
| `tools/list` | MCP tool enumeration returns expected tool set |
| `os_agent` call | Full agent invocation produces non-null response |
| `run_id` | Each invocation returns a unique, non-empty run ID |
| `events` | Event stream is non-empty and contains expected stage names |
| Observer page | Dashboard observer endpoint returns 200 and renders |
| Trace quality | Trace spans exist and are well-formed |
| MCP response fields | Response objects contain `tool`, `args`, `result` keys |

## check_closed_loop.py

### Checks Performed

| Category | Checks |
|---|---|
| Imports | All core modules importable without errors |
| RunLifecycle stages | All expected stages registered and reachable |
| Validation not stubbed | `validation_passed` is bound to real logic, not hardcoded |
| Best skill guard | After proof loop, best skill is non-null and valid |
| RegressionRunner no-cases → fail | Empty regression case list yields `passed=False` |
| Dashboard files | Observer HTML, JS, and event schema files present on disk |
| Scripts | `start_opencode.sh`, `install.sh` are executable |
| Forbidden fields | No `stub`, `mock`, `bypass`, `skip_proof` fields in production config |

## Smoke Test

Checks three endpoints:

| Endpoint | Expected |
|---|---|
| `GET /` | 200, contains "OS Agent" |
| `GET /docs` | 200, Swagger/OpenAPI page renders |
| `POST /connect/mcp` | 200, returns MCP session handshake |

## Test Infrastructure

- `integration_test.py` — run with `pytest tests/integration_test.py`
- `check_closed_loop.py` — run with `python scripts/check_closed_loop.py`
- Smoke test — run with `bash scripts/smoke_test.sh`
- All three are invoked by CI on every push to `main`.
