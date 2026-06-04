---
type: decision
status: confirmed
date: 2026-06-04
tags: [windows, python, uv]
---
# Python Invocation on Windows

## Problem
`python` and `python3` in Git Bash and PowerShell hit the Windows Store
App Execution Alias stub — prints a store redirect error instead of running.

## Solution
Always use `uv run python` (or `uv run --no-project python` in hook scripts
to avoid searching for a pyproject.toml).

```bash
# In hook scripts
uv run --no-project python -c 'import json,sys; ...'

# In skill/command instructions
uv run python /d/Claude_projects/ecosystem-brain/skills/memory/memory-index.py
```

## Real Python location
`C:\Users\Martin Cayré\AppData\Local\Programs\Python\Python313\python.exe` — 3.13.5
But never hardcode this; use `uv run python` so it works regardless of install state.
