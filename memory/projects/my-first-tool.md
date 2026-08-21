---
type: project
status: archived
created: 2026-06-04
stack: [python, uv, ruff, pytest]
tags: [project, python]
---

> **Archived — the project directory is gone.** `D:\claude-projects\my-first-tool`
> no longer exists on MSI, the machine that held it. Deleted; confirmed by the
> owner on 2026-08-21 rather than inferred from the absent path, which is the
> mistake 90b52db reverted. The card is kept because decisions and links still
> point at it.
# my-first-tool

Scaffolded from `python-project` template on 2026-06-04.

## Paths
- Project: `D:\claude-projects\my-first-tool`
- Package: `my_first_tool`
- Entry point: `src/my_first_tool/cli.py`

## First-time setup
```bash
cd /d/claude-projects/my-first-tool
uv sync
pre-commit install
cp .env.example .env
uv run pytest -q
```

## Links
- [[projects-moc]]
- [[windows-python-invocation]] — uv / `uv run python` invocation rule
- [[powershell-utf8-bom]] — ruff-formatted files must stay BOM-free
