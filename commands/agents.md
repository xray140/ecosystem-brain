---
description: List all installed agents, skills, and commands with their sources.
---
List all installed ecosystem components.

Run: `uv run python {{ECOSYSTEM_ROOT}}/scripts/install-agent.py --list`

Also show what's available in the registry:
`cat {{ECOSYSTEM_ROOT}}/registry/registry.json`

Format the output as a clean table grouped by type (agents / commands / skills),
showing name, source, and install date.

If the user is deciding what to keep, add usage:
`uv run python {{ECOSYSTEM_ROOT}}/scripts/agent_usage.py`

Report the **evidence window** it prints alongside any "never invoked" count.
Transcripts are local and rotatable, so the count only speaks for the period
they cover — and several agents here were installed before that window starts.
Never present it as grounds for deletion without the window.
