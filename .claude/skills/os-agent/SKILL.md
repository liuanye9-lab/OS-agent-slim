---
name: os-agent
description: Trigger StableAgent OS self-optimization workflow through MCP and open the live dashboard.
disable-model-invocation: true
---

# OS Agent Skill

When the user invokes `/os-agent`, perform the following:

1. Check whether StableAgent OS server is running at http://127.0.0.1:8000.
2. If not running, ask permission to start it with:
   `uvicorn web.server:app --host 127.0.0.1 --port 8000`
3. Call the MCP tool:
   `stableagent.task.os_agent`
4. Pass the current task or `$ARGUMENTS` as `task_input`.
5. Read the returned `run_id` and `dashboard_url`.
6. Show the user:
   - run_id
   - dashboard_url
   - current stage
   - short Chinese status
7. Tell the user to open `/runs/{run_id}` to observe the execution.
8. Do not expose hidden chain-of-thought.
9. Only summarize observable decision traces.

If `$ARGUMENTS` is empty, ask the user what task they want OS Agent to optimize.
