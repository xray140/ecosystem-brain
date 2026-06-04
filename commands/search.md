---
description: Search GitHub live for Claude Code agents/skills, ranked by stars. Then optionally install one.
argument-hint: <topic> [--files]
---
Search GitHub for agents/skills matching: $ARGUMENTS

Run:
```
uv run python /d/Claude_projects/ecosystem-brain/scripts/search_agents.py $ARGUMENTS
```

- Without `--files`: returns repos ranked by stars.
- With `--files`: returns individual installable agent files (shows the exact `--repo ... --path ...` to install).

After showing results, if the user picks one, install it (the security scan runs automatically):
```
uv run python /d/Claude_projects/ecosystem-brain/scripts/install-agent.py --repo <repo> --path <path>
```
Then sync: `cp /d/Claude_projects/ecosystem-brain/agents/*.md ~/.claude/agents/`
