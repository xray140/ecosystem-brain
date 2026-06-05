---
description: List all installed agents, skills, and commands with their sources.
---
List all installed ecosystem components.

Run: `uv run python /d/claude-projects/ecosystem-brain/scripts/install-agent.py --list`

Also show what's available in the registry:
`cat /d/claude-projects/ecosystem-brain/registry/registry.json`

Format the output as a clean table grouped by type (agents / commands / skills),
showing name, source, and install date.
