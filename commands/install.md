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
A skill lands at `skills/<name>/SKILL.md` — that nested shape is the only one
Claude Code loads.

The installer writes both the repo copy and the `~/.claude` copy itself, so
nothing further is needed. **Never `cp` the repo's files over `~/.claude`.**
Committed files refer to the repo as `{{ECOSYSTEM_ROOT}}`, and `bootstrap`
expands that token on the way out; a raw copy would overwrite every working
command with one containing the literal token, and would miss skills entirely
(their nested path does not match a flat `*.md` glob).

If `~/.claude` really is out of sync, the one correct fix is:
```
uv run python {{ECOSYSTEM_ROOT}}/scripts/bootstrap.py
```
`scripts/doctor.py` is what tells you whether it is.

Then show the updated list: `uv run python {{ECOSYSTEM_ROOT}}/scripts/install-agent.py --list`
