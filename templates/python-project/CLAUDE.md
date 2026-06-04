# pkgname — operating rules

Part of the claude-unified-ecosystem. Inherits ecosystem-brain conventions.

## Stack
- **Runtime:** Python 3.12+ via `uv`
- **Lint/format:** `ruff` (auto-applied on Write by the ecosystem hook)
- **Tests:** `pytest` — run with `uv run pytest -q`
- **Secrets:** `.env` only (gitignored); never committed, never echoed

## Workflow
- Propose → get approval → execute for any multi-file change
- Use plan mode (`/plan`) for structural changes
- Commit messages: `type(scope): description` (feat, fix, chore, docs, test)

## Commands available (via ecosystem-brain plugin)
- `/ecosystem-brain:health-check` — secrets hygiene + tool versions
- `/ecosystem-brain:memory-gc` — prune stale memory notes
- `/ecosystem-brain:context-sync` — pull latest ecosystem conventions

## Key files
| File | Purpose |
|------|---------|
| `src/pkgname/core.py` | Business logic — keep pure, no I/O |
| `src/pkgname/cli.py` | Entry point — thin wrapper over core |
| `tests/test_core.py` | Unit tests |
| `.env.example` | Required env vars (copy to `.env` and fill) |
| `pyproject.toml` | Deps, tool config, entry points |

## After scaffold — first-time setup
```bash
uv sync                 # install deps + dev group
pre-commit install      # wire gitleaks + ruff git hook
cp .env.example .env    # fill in real values
uv run pytest -q        # confirm green baseline
```

## Conventions
- `core.py` stays pure (no subprocess, no network, no file I/O)
- New features go in `core.py` first, exposed via `cli.py`
- Every public function gets a docstring + at least one test
- Never `print()` in core — use the return value or raise
