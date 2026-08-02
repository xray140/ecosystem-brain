---
type: project
status: archived
created: 2026-06-04
stack: [python, uv, ruff, pytest]
tags: [project, python]
---

> **Archived 2026-08-03.** The project lives on another PC's `D:` drive, or was
> deleted from it — unknowable from this machine. The `- Project:` path below is
> left as recorded so the card still knows where to look if that drive returns.
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
