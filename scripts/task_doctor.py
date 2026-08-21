#!/usr/bin/env python3
r"""Are the scheduled tasks actually running — or just registered?

The weekly heartbeat and the catalog refresh were registered on 2026-07-15 and
reported `State: Ready` ever since. Both had also failed **every single
scheduled run**: `New-ScheduledTaskSettingsSet` defaults both battery guards to
true, so on a laptop the task refused to start on battery and was killed if the
machine switched to it mid-run. The catalog went 40 days without a refresh and
the heartbeat produced no report, while everything looked registered and Ready.

Ready is not the same as working, and nothing was checking the difference. This
does: it reads each task's *last result* and *last run time*, not its state.

Windows-only by nature — Task Scheduler is the mechanism the ecosystem uses.
Everywhere else this reports "not applicable" and passes.

Usage:
    uv run --no-project python scripts/task_doctor.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

WINDOWS = os.name == "nt"
PREFIX = "EcosystemBrain"

# Must be runnable exactly as printed, from anywhere, on a stock Windows box.
# Two ways this line was wrong before:
#   - relative path: from a home directory powershell answers "the argument ...
#     does not exist", which reads like a broken script rather than a wrong cwd.
#   - no -ExecutionPolicy Bypass: the default policy is Restricted, so no .ps1
#     runs at all and it fails UnauthorizedAccess. INSTALL.md had the flag; this
#     line did not, and this is the one the reader meets at the moment of
#     failure. Bypass here is per-process — it changes no machine state.
REGISTER_CMD = (
    "powershell -ExecutionPolicy Bypass -File "
    f'"{Path(__file__).resolve().parent / "register-scheduled-tasks.ps1"}"'
)

# Exit codes that are not failures.
OK_RESULTS = {
    0x0,  # success
    0x41303,  # SCHED_S_TASK_HAS_NOT_RUN — registered, not yet due
    0x41325,  # SCHED_S_TASK_QUEUED
}
RESULT_MEANING = {
    0x41301: "still running",
    0x41303: "has not run yet",
    0x41306: "terminated before finishing (battery guard, or time limit)",
    0xC000013A: "process was terminated",
    0x1: "the task's own command exited 1",
}

# A run in progress is evidence the task STARTED, not that it failed — and this
# doctor is itself one of the checks the weekly heartbeat runs, so it always
# reads the heartbeat's own in-flight run here. Counting that as a failure
# latched the report red for good: task_doctor failed -> maintenance exited 1 ->
# the next run read 0x1 ("the task's own command exited 1") and failed again,
# for ever. The heartbeat could never report itself green.
# Only a run still "running" long past its execution time limit is truly stuck.
RUNNING = 0x41301
RUNNING_GRACE = timedelta(hours=1)

# A weekly task that has not run in this long is not running at all.
STALE_AFTER = timedelta(days=10)

# Windows PowerShell 5.1 has no `ConvertTo-Json -AsArray`, and it emits a bare
# object rather than a 1-element array for a single task — so the results are
# wrapped in an explicit @(...) and the caller normalises either shape. Using
# -AsArray here silently returned "no tasks registered" on this very machine,
# while three were registered and two were failing.
PS = r"""
$rows = Get-ScheduledTask -TaskName '{prefix}*' -ErrorAction SilentlyContinue | ForEach-Object {{
  $i = Get-ScheduledTaskInfo $_.TaskName
  [pscustomobject]@{{
    Name = $_.TaskName
    State = [string]$_.State
    LastRun = if ($i.LastRunTime) {{ $i.LastRunTime.ToString('o') }} else {{ '' }}
    LastResult = $i.LastTaskResult
    NextRun = if ($i.NextRunTime) {{ $i.NextRunTime.ToString('o') }} else {{ '' }}
  }}
}}
ConvertTo-Json -InputObject @($rows) -Compress -Depth 3
"""


def query_tasks(prefix: str = PREFIX) -> list[dict] | None:
    """Registered ecosystem tasks, or None when Task Scheduler is unavailable."""
    if not WINDOWS:
        return None
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return None
    try:
        r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
            [exe, "-NoProfile", "-NonInteractive", "-Command", PS.format(prefix=prefix)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    # 5.1 emits a bare object for a single row even through @(...) in some hosts.
    return data if isinstance(data, list) else [data]


def describe(result: int) -> str:
    return RESULT_MEANING.get(result, f"exit 0x{result:08X}")


def _age(last: str, now: datetime) -> timedelta | None:
    """How long ago `last` was — None when it is absent or unparseable."""
    if not last:
        return None
    try:
        when = datetime.fromisoformat(last)
    except ValueError:
        return None
    return now - (when if when.tzinfo else when.replace(tzinfo=UTC))


def _span(age: timedelta) -> str:
    """Coarse duration. `age.days` alone renders a two-hour hang as "0d"."""
    return f"{age.days}d" if age.days else f"{int(age.total_seconds() // 3600)}h"


def assess(task: dict, now: datetime | None = None) -> tuple[bool, str]:
    """(ok, detail) for one task — judged on its last RESULT, not its state."""
    now = now or datetime.now(UTC)
    result = int(task.get("LastResult", 0))
    last = task.get("LastRun") or ""
    age = _age(last, now)

    # Checked before OK_RESULTS: a run in flight has no verdict yet. See RUNNING.
    if result == RUNNING:
        if age is None or age <= RUNNING_GRACE:
            return True, "run in progress"
        return False, f"still running {_span(age)} after it started — stuck?"

    if result not in OK_RESULTS:
        return False, f"last run {describe(result)}"

    if result == 0x41303 or not last:
        return True, "registered, not yet run"

    if age is None:
        return True, "last run ok"

    if age > STALE_AFTER:
        return False, f"last succeeded {age.days} days ago — is the trigger firing?"
    return True, f"last run ok, {age.days}d ago"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="TASK",
        help=(
            "task to report but not gate on. Pass the task this check is running "
            "inside: its recorded result describes the PREVIOUS run, and the "
            "current one has no verdict yet."
        ),
    )
    args = ap.parse_args(argv)

    print("ecosystem-brain scheduled-task doctor")
    tasks = query_tasks()
    if tasks is None:
        print("  [skip] Task Scheduler not available here (not Windows, or no PowerShell)")
        return 0
    if not tasks:
        print(f"  [skip] no '{PREFIX}-*' tasks registered")
        print(f"     register them: {REGISTER_CMD}")
        return 0

    print(f"  {len(tasks)} registered\n")
    failing = 0
    for t in sorted(tasks, key=lambda x: x["Name"]):
        ok, detail = assess(t)
        # Self-reference is not evidence. When maintenance runs this check, the
        # Maintenance task's last result is its own PREVIOUS run — so one real
        # failure made the heartbeat permanently red: it exited 1, Task Scheduler
        # recorded 0x1, and the next run failed this check on that record and
        # exited 1 again. It stayed red on 2026-08-21 with every other check
        # green, still carrying the pytest failure fixed the day before.
        if t["Name"] in args.exclude:
            print(f"  [--] {t['Name']:34s} {detail} (this run — not gated on)")
            continue
        failing += not ok
        print(f"  [{'ok' if ok else '!!'}] {t['Name']:34s} {detail}")

    print()
    if failing:
        print(f"[!] {failing} scheduled task(s) are registered but not completing.")
        print("    A task can sit at State=Ready forever while every run dies.")
        print("    Re-register — this rewrites each action's path and drops retired tasks:")
        print(f"      {REGISTER_CMD}")
        return 1
    print("[ok] every scheduled task has completed a recent run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
