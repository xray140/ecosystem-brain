@echo off
REM Weekly ecosystem health heartbeat. Path-independent: derives the repo root
REM from this script's own location. Writes memory/maintenance/<date>.md.
REM Requires: uv on PATH (gh auth login for the update --check network step).
cd /d "%~dp0.."
uv run --no-project python scripts/maintenance.py
