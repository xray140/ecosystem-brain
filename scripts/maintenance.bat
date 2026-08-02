@echo off
REM Weekly ecosystem health heartbeat. Path-independent: derives the repo root
REM from this script's own location. Writes memory/maintenance/<date>.md.
REM Requires: uv on PATH (gh auth login for the update --check network step).
REM
REM Output is teed to memory/maintenance/last-run.log. A scheduled task that
REM dies leaves nothing behind but an exit code, which is how this one failed
REM every week from 2026-07-15 without anyone being able to see why.
cd /d "%~dp0.."
if not exist "memory\maintenance" mkdir "memory\maintenance"
set "LOG=memory\maintenance\last-run.log"
echo === %DATE% %TIME% === > "%LOG%"
uv run --no-project python scripts/maintenance.py >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo === exit %RC% === >> "%LOG%"
exit /b %RC%
