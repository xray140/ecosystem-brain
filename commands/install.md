---
description: Install an agent, skill, or command from a GitHub URL or local file into the ecosystem.
argument-hint: <github-url | repo/path | local-file>
---
Install an agent/skill/command from: $ARGUMENTS

Run:
```
uv run python /d/claude-projects/ecosystem-brain/scripts/install-agent.py --url <url>
```
Or for a GitHub repo+path:
```
uv run python /d/claude-projects/ecosystem-brain/scripts/install-agent.py --repo <user/repo> --path <path/to/file.md>
```

After installing, sync the command files:
```
cp /d/claude-projects/ecosystem-brain/commands/*.md ~/.claude/commands/ecosystem-brain/
cp /d/claude-projects/ecosystem-brain/agents/*.md ~/.claude/agents/
```

Then show the updated list: `uv run python /d/claude-projects/ecosystem-brain/scripts/install-agent.py --list`
