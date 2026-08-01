---
description: Install an agent, skill, or command from a GitHub URL or local file into the ecosystem.
argument-hint: <github-url | repo/path | local-file>
---
Install an agent/skill/command from: $ARGUMENTS

Run:
```
uv run python {{ECOSYSTEM_ROOT}}/scripts/install-agent.py --url <url>
```
Or for a GitHub repo+path (this path **pins to the current commit SHA** so the
content is reproducible and tamper-evident — a moved branch can't swap it):
```
uv run python {{ECOSYSTEM_ROOT}}/scripts/install-agent.py --repo <user/repo> --path <path/to/file.md>
```
Every install is security-scanned; HIGH-risk content is refused and quarantined.

After installing, sync the command files:
```
cp {{ECOSYSTEM_ROOT}}/commands/*.md ~/.claude/commands/ecosystem-brain/
cp {{ECOSYSTEM_ROOT}}/agents/*.md ~/.claude/agents/
```

Then show the updated list: `uv run python {{ECOSYSTEM_ROOT}}/scripts/install-agent.py --list`
