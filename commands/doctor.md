---
description: Health + drift check — are the live hooks, commands, and agents in ~/.claude actually in sync with the repo?
---
Run the doctor and report its findings:
```
uv run python /d/claude-projects/ecosystem-brain/scripts/doctor.py
```
It checks three things:
1. **Hooks live** — every hook script path in `~/.claude/settings.json` resolves.
2. **Sync drift** — each repo command/agent matches its `~/.claude` copy (after the
   per-clone path rewrite), so an edit in the repo that was never re-synced shows up.
3. **Prerequisites** — uv/git/node/gh/gitleaks/ruff/ollama on PATH (advisory).

If it reports drift or broken hooks, the fix is almost always:
`uv run python /d/claude-projects/ecosystem-brain/scripts/bootstrap.py`
Summarize the verdict; if anything failed, offer to run bootstrap.
