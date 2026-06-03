---
description: Ecosystem health report — secrets hygiene, tool versions, MCP status, active projects.
---
Produce a health report:

1. Secrets: run `bash ${CLAUDE_PLUGIN_ROOT}/skills/secrets/secrets-doctor.sh` and summarize.
2. Tools: report versions of git, python, node, uv, ruff, gitleaks, mise, ollama (note any missing).
3. MCP: list connected servers and their status.
4. Projects: from `memory/index.json`, list active projects and their last session date.

Keep it to a compact status block. Never print secret values.
