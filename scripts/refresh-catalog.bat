@echo off
REM Refresh the cached agent catalog (registry/catalog.json) from GitHub.
REM Path-independent: derives the repo root from this script's own location.
REM Requires: uv on PATH, gh authenticated (gh auth login).
REM
REM Logs and returns the child's exit code explicitly — a batch file that just
REM runs off its end lets Task Scheduler report the console teardown instead of
REM what actually happened, which is how the weekly heartbeat reported
REM STATUS_CONTROL_C_EXIT for weeks while nobody could see why.
cd /d "%~dp0.."
if not exist "memory\maintenance" mkdir "memory\maintenance"
set "LOG=memory\maintenance\last-catalog-refresh.log"
echo === %DATE% %TIME% === > "%LOG%"
uv run --no-project python scripts/catalog.py build >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo === exit %RC% === >> "%LOG%"
exit /b %RC%
