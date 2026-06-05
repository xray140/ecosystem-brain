---
type: decision
status: confirmed
date: 2026-06-05
tags: [windows, git-bash, python, paths]
---
# Windows /d/ Path Translation in Hooks & Scripts

## Problem
Git Bash mount paths like `/d/claude-projects/foo` behave inconsistently:

| Context | `/d/foo` becomes | Works? |
|---------|------------------|--------|
| bash builtin (cd, ls) | `D:\foo` | ✅ |
| Command-line ARG to native exe (python.exe) | `D:\foo` (MSYS auto-translates) | ✅ |
| Hardcoded STRING inside Python code | `D:\d\foo` | ❌ |

The MSYS layer only translates `/d/` when it's a command-line argument crossing
into a native Windows process. A `/d/` string written inside a `.py` file is
never translated — Python reads it literally and resolves to `D:\d\foo`.

## Rules
- **In hook commands / shell:** `uv run python /d/claude-projects/.../x.py` works
  (the path arg is auto-translated).
- **Inside Python code:** never hardcode `/d/...`. Either:
  - resolve relative to `__file__`: `Path(__file__).resolve().parent.parent`
  - or use Windows form: `Path("D:/claude-projects/...")`
  - or convert at runtime: translate leading `/<drive>/` → `<DRIVE>:/`

## Where this bit us
`suggest-agents.py` SessionStart hook returned nothing because its hardcoded
`/d/.../installed.json` resolved to `D:\d\...` (missing). Fixed with
`__file__`-relative `REPO_ROOT` and a `normalize_path()` for the incoming `cwd`.

See [[hook-format]] for the hook structure itself.
