---
type: project
status: active
created: 2026-06-04
stack: [python, uv, ruff, pytest]
tags: [project, python]
---

> **Lives on another PC.** The `- Project:` path below is on a `D:` drive that
> is not on Verdun10. That machine is still in use, so the project is live — it
> simply cannot be checked from here. Pin it by adding `host: <machine>` to this
> frontmatter once that machine's `hostname` is known; until then
> `project_doctor` infers "elsewhere" from the absent drive root.
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
