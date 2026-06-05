---
type: project
status: active
created: 2026-06-04
stack: [python, uv, ruff, pytest]
tags: [project, python]
---
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
- [[tools/uv]]
- [[tools/ruff]]
