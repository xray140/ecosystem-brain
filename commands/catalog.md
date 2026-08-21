---
description: Browse and batch-install agents from a cached catalog of a big collection repo (VoltAgent by default).
argument-hint: [build | categories | install <category> [--limit N]]
---
Manage the local agent catalog: $ARGUMENTS

The catalog (`registry/catalog.json`) is a cached snapshot of 150+ agents so the
SessionStart suggester can recommend uninstalled agents with no network call.

`catalog.json` is **gitignored** — a scheduled task rewrites it every Sunday, and
as a tracked file that meant a weekly uncommitted diff nobody landed. The
committed floor is `registry/catalog.seed.json`, which a fresh clone reads until
its first `catalog.py build`; reading it prints a note saying so. Refresh the
seed deliberately with `catalog.py build --seed` when it has drifted far from
upstream.

Run the matching command:
- **build** — refresh the catalog from GitHub:
  `uv run python {{ECOSYSTEM_ROOT}}/scripts/catalog.py build`
- **categories** — list categories + counts:
  `uv run python {{ECOSYSTEM_ROOT}}/scripts/catalog.py categories`
- **install <category> [--limit N]** — batch-install a category (each agent is
  security-scanned; HIGH-risk ones are blocked):
  `uv run python {{ECOSYSTEM_ROOT}}/scripts/catalog.py install <category> --limit N`

After installing, sync to global and report what landed:
`uv run python {{ECOSYSTEM_ROOT}}/scripts/bootstrap.py`  (not `cp` — see below)
