---
description: Ecosystem health report — secrets hygiene, tool versions, MCP status, active projects.
---
Produce a health report:

1. Secrets: run `bash {{ECOSYSTEM_ROOT}}/skills/secrets/secrets-doctor.sh` and summarize.
2. Tools: report versions of git, node, uv, ruff, gitleaks, ollama (note any missing).
3. MCP: list connected servers and their status.
4. Wiring: run `uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/doctor.py` — checks live hooks + repo↔`~/.claude` drift + prereqs. If it reports drift/stale hooks, advise re-running `scripts/bootstrap.py`.
5. Projects: from `{{ECOSYSTEM_ROOT}}/memory/index.json`, list active projects and their last session date.

Keep it to a compact status block. Never print secret values.
