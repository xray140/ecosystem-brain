---
type: project
status: active
created: {{date}}
stack: []
tags: [project]
---
# {{title}}

## Paths
- Project: `D:\claude-projects\{{title}}`

## First-time setup
```bash
cd /d/claude-projects/{{title}}
uv sync
pre-commit install
cp .env.example .env
uv run pytest -q
```
