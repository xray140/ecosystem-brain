---
description: Ecosystem health report — secrets, wiring, projects, scheduled tasks, memory, agents.
---
Produce a compact health report by running the checks that already exist. Do not
re-derive any of this by reading files yourself — each tool below judges its
subject on evidence, and several of them exist because reading the file gave the
wrong answer.

Run these and summarise:

1. **Secrets** — `bash {{ECOSYSTEM_ROOT}}/skills/secrets/secrets-doctor.sh`
2. **Wiring** — `uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/doctor.py`
   (live hooks, repo↔`~/.claude` drift, prereqs). On drift or stale hooks,
   advise re-running `scripts/bootstrap.py`.
3. **Projects** — `uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/project_doctor.py`
   Do **not** list projects from `memory/index.json` instead: the manifest says
   what a card claims, not whether the project is still there. Four cards
   currently point at a drive that is not on this machine, and the manifest
   reports all of them as `active`.
4. **Scheduled tasks** — `uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/task_doctor.py`
   Judges each task on its last *result*, not its state. A task sits at
   `State: Ready` forever while every run dies — which is exactly what the
   weekly heartbeat did for three weeks.
5. **Memory** — `uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-search.py --vault {{ECOSYSTEM_ROOT}}/memory status`
   Confirms the search index covers the vault with the intended embedder,
   rather than having quietly gone stale or partial.
6. **Agents** — `uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/agent_usage.py`
   Report the evidence window it prints alongside any "never invoked" counts;
   the counts mean nothing without it.
7. **Tools** — versions of git, node, uv, ruff, gitleaks; note any missing.
8. **MCP** — connected servers and their status.

## How to report it

One status block. For each check, its verdict — not its full output. Quote a
tool's own wording when it flags something, and pass along the fix it suggests
rather than inventing one.

If everything is green, say so in a line. Do not pad a healthy report.

Never print secret values.

The same checks (bar tools/MCP) run weekly via `scripts/maintenance.py`, so a
surprise here usually means the heartbeat has not run — which `task_doctor` will
tell you.
