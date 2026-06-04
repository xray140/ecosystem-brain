---
description: Pull latest ecosystem-brain conventions into the current session context.
---
Sync the current session with the ecosystem-brain control tower:

1. Read `/d/Claude_projects/ecosystem-brain/CLAUDE.md` — summarize any rules that differ from current session behavior.
2. Read `/d/Claude_projects/ecosystem-brain/memory/index.json` — list active projects and recent decisions.
3. Run `uv run python /d/Claude_projects/ecosystem-brain/skills/memory/memory-search.py search "recent decisions conventions" -k 5` and surface any relevant notes.

Output a compact briefing: active projects, key conventions, anything that should change in this session.
