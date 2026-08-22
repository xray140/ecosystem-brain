---
description: Health + drift check — are the live hooks, commands, and agents in ~/.claude actually in sync with the repo?
---
Run the doctor and report its findings:
```
uv run python {{ECOSYSTEM_ROOT}}/scripts/doctor.py
```
It checks three things:
1. **Hooks live** — every hook script path in `~/.claude/settings.json` resolves.
2. **Sync drift** — each repo command/agent matches its `~/.claude` copy (after the
   per-clone path rewrite), so an edit in the repo that was never re-synced shows up.
3. **Prerequisites** — uv/git/node/gh/gitleaks/ruff on PATH (advisory).

It checks the **install**, and only the install. Sync drift also covers `skills/`
(`<name>/SKILL.md`), which it was blind to before v4.3.5.

If it reports drift or broken hooks, the fix is almost always:
`uv run python {{ECOSYSTEM_ROOT}}/scripts/bootstrap.py`
Summarize the verdict; if anything failed, offer to run bootstrap.

## Its siblings

A green `doctor` says the wiring is right. It says nothing about whether the
things the ecosystem *produced* are still healthy — that is deliberately split:

- `project_doctor.py` — do the registered projects still exist?
- `task_doctor.py` — have the scheduled tasks actually completed a run?
- `memory-search.py status` — is the search index real and complete?
- `agent_usage.py` — which installed agents ever get invoked?

`/ecosystem-brain:health-check` runs all of them together. Reach for that when
the question is "is everything alright", and this one when it is "is my install
wired up correctly".
