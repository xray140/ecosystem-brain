---
description: Health check the projects the ecosystem created — do they still exist, and are they healthy?
---
`/ecosystem-brain:doctor` answers "is my install wired up correctly". This one
answers the question nothing used to ask: **are the projects I registered still
there?**

Run:

```
uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/project_doctor.py
```

Add `--no-ci` to skip the GitHub lookup (faster, works offline).

For each card in `memory/projects/`, it reports:

| marker | meaning |
|---|---|
| `[ok]` | path resolves, nothing to say |
| `[??]` | resolves, with advisory notes (stale, dirty tree, no `AGENTS.md`, `.env` missing keys its `.env.example` names) |
| `[!!]` | needs a decision — path gone, or CI red |
| `[--]` | `status: archived`, skipped |

## It reports; it does not repair

When a path is wrong, only the user knows whether the project was deleted,
moved, or lives on a machine that isn't this one — and the right fix differs in
each case. Never guess. Show the findings, then help them apply whichever is
true, one line per card:

- **moved** → update the `- Project: ` line in `memory/projects/<name>.md`
- **done** → set `status: archived` in that card's frontmatter

After editing any card, refresh the manifest:

```
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-index.py
```

If several cards point at the same dead root (e.g. an old drive), say so as one
finding rather than repeating it per project — it is one event, not four.
