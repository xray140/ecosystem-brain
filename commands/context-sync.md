---
description: Pull latest ecosystem-brain conventions into the current session context.
---
Sync the current session with the ecosystem-brain control tower:

1. Read `{{ECOSYSTEM_ROOT}}/CLAUDE.md` — summarize any rules that differ from current session behavior.
2. Read `{{ECOSYSTEM_ROOT}}/memory/index.json` — list active projects and recent decisions.
3. Run `uv run python {{ECOSYSTEM_ROOT}}/skills/memory/memory-search.py search "recent decisions conventions" -k 5` and surface any relevant notes.

Output a compact briefing: active projects, key conventions, anything that should change in this session.
