---
type: project
status: active
created: {{date}}
stack: []
tags: [project]
---
# {{title}}

## Paths
- Project: `<projects-root>\{{title}}`  <!-- projects root = the ecosystem-brain
  clone's parent, or $ECOSYSTEM_DEST_ROOT if set. Never hardcode a drive here. -->

## First-time setup
```bash
cd <projects-root>/{{title}}
uv sync
pre-commit install
cp .env.example .env
uv run pytest -q
```
