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
| `[->]` | on another machine — its whole root is absent here, or the card pins a different `host:` |
| `[!!]` | needs a decision — path gone (its root *does* exist here), or CI red |
| `[--]` | `status: archived`, skipped |

## "Elsewhere" is not "gone"

The vault is shared across machines; project locations are not. A path like
`D:\...` is correct — on the PC that has a `D:` drive. When the whole root is
missing here, the project is not lost, it is simply not on this machine, and
saying "path does not exist" would send the user hunting for nothing.

## It reports; it does not repair

When a path really is wrong, only the user knows whether the project was
deleted, moved, or lives elsewhere — and the right fix differs. Never guess.
Show the findings, then help them apply whichever is true, one line per card:

- **on another machine** → add `host: <machine-name>` to the frontmatter
- **moved** → update the `- Project: ` line in `memory/projects/<name>.md`
- **done** → set `status: archived` in that card's frontmatter

After editing any card, refresh the manifest:

```
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-index.py
```

If several cards point at the same dead root (e.g. an old drive), say so as one
finding rather than repeating it per project — it is one event, not four.
