---
description: Browse and batch-install agents from a cached catalog of a big collection repo (VoltAgent by default).
argument-hint: [build | categories | install <category> [--limit N]]
---
Manage the local agent catalog: $ARGUMENTS

The catalog (`registry/catalog.json`) is a cached snapshot of 150+ agents so the
SessionStart suggester can recommend uninstalled agents with no network call.

Run the matching command:
- **build** — refresh the catalog from GitHub:
  `uv run python /d/claude-projects/ecosystem-brain/scripts/catalog.py build`
- **categories** — list categories + counts:
  `uv run python /d/claude-projects/ecosystem-brain/scripts/catalog.py categories`
- **install <category> [--limit N]** — batch-install a category (each agent is
  security-scanned; HIGH-risk ones are blocked):
  `uv run python /d/claude-projects/ecosystem-brain/scripts/catalog.py install <category> --limit N`

After installing, sync to global and report what landed:
`cp /d/claude-projects/ecosystem-brain/agents/*.md ~/.claude/agents/`
