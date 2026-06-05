@echo off
REM Refresh the cached agent catalog (registry/catalog.json) from GitHub.
REM Path-independent: derives the repo root from this script's own location.
REM Requires: uv on PATH, gh authenticated (gh auth login).
cd /d "%~dp0.."
uv run python scripts/catalog.py build
