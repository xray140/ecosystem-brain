---
description: Ecosystem health report — secrets hygiene, tool versions, MCP status, active projects.
---
Produce a health report:

1. Secrets: run `bash /d/Claude_projects/ecosystem-brain/skills/secrets/secrets-doctor.sh` and summarize.
2. Tools: report versions of git, node, uv, ruff, gitleaks, ollama (note any missing).
3. MCP: list connected servers and their status.
4. Projects: from `/d/Claude_projects/ecosystem-brain/memory/index.json`, list active projects and their last session date.

Keep it to a compact status block. Never print secret values.
