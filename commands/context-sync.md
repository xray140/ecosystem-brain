---
description: Load a project's context for a fresh session and propose the next action.
argument-hint: <project>
---
Onboard onto project `$1`:

1. Read `memory/projects/$1.md` and the decisions it links.
2. Read `memory/00-MOC/conventions.md`.
3. If recall is fuzzy, run `python ${CLAUDE_PLUGIN_ROOT}/skills/memory/memory-search.py search "$1 status next step" -k 5`.

Output an onboarding summary under 200 words, then propose the single next action.
