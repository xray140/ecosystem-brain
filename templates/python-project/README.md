# pkgname

A project scaffolded from the claude-unified-ecosystem `python-project` template.

## Setup
```bash
uv sync                 # create venv + install deps (incl. dev group)
pre-commit install      # enable gitleaks + ruff git hook
cp .env.example .env     # then fill values
```

## Use
```bash
uv run pkgname "Hello World"   # -> hello-world
uv run pytest                  # tests
uv run ruff check              # lint
```
