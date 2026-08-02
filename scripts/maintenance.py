#!/usr/bin/env python3
"""Weekly ecosystem health heartbeat — run by a scheduled task.

Runs the deterministic checks that catch silent rot:
  1. bootstrap --verify  — live hook paths still resolve (catches a repo move).
  2. selfcheck           — JSON, agent scan, init engine, memory index, pytest.
  3. update --check      — upstream agent updates available / blocked.

Writes a dated report to memory/maintenance/<date>.md and exits non-zero if any
check fails, so a wrapper (or a human reading the report) can tell at a glance.

Usage:
    uv run --no-project python scripts/maintenance.py
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO / "memory" / "maintenance"


def py(script: str, *args: str) -> list[str]:
    return [
        "uv",
        "run",
        "--no-project",
        "python",
        str(REPO / "scripts" / script),
        *args,
    ]


# (label, command, treat-nonzero-as-failure)
CHECKS: list[tuple[str, list[str], bool]] = [
    ("config in sync (doctor)", py("doctor.py"), True),
    ("selfcheck", py("selfcheck.py"), True),
    # Non-gating on purpose, for now: four cards point at a drive that no longer
    # exists on this machine, and until that is triaged a gating check would
    # make the heartbeat permanently red — which is how a report stops being
    # read. Flip to True once the backlog is clear.
    ("registered projects (project_doctor)", py("project_doctor.py"), False),
    # Gating: this one catches the heartbeat's own scheduler failing. It ran
    # here every week from 2026-07-15 without once completing, and nothing
    # noticed — because everything that looked at those tasks looked at their
    # State ("Ready") rather than their last result.
    ("scheduled tasks (task_doctor)", py("task_doctor.py"), True),
    # Advisory: it reports which installed agents never get invoked. Nothing here
    # is broken when the list is long — it is a prompt to prune, not a fault.
    ("agent usage", py("agent_usage.py"), False),
    # --check is informational (updates available is not a failure); network
    # hiccups shouldn't flip the heartbeat red, so don't gate on its exit code.
    ("agent updates (update --check)", py("update-agents.py", "--check"), False),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    # check=False: a failing check is the signal this heartbeat exists to record,
    # not an exception to raise.
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), check=False)


def main() -> int:
    # Local date (the report is filed and read by date), derived from an aware
    # UTC instant rather than a naive date.today().
    today = datetime.now(UTC).astimezone().date().isoformat()
    sections: list[str] = []
    failed: list[str] = []
    warned: list[str] = []

    print(f"ecosystem maintenance — {today}\n")
    for label, cmd, gating in CHECKS:
        r = run(cmd)
        # Three states, not two. A non-gating check that failed is NOT "ok":
        # labelling it so is how the project doctor's four dead paths got filed
        # under a section titled "— ok", where nobody skimming would open it.
        # Advisory means "does not turn the run red", not "did not happen".
        if r.returncode == 0:
            status = "ok"
        elif gating:
            status = "FAIL"
            failed.append(label)
        else:
            status = "warn"
            warned.append(label)
        print(f"  [{status:4s}] {label}")
        body = (r.stdout + r.stderr).strip() or "(no output)"
        sections.append(f"## {label} — {status}\n\n```\n{body}\n```")

    if failed:
        verdict = f"NEEDS ATTENTION: {', '.join(failed)}"
    elif warned:
        verdict = f"all gates green, advisory warnings: {', '.join(warned)}"
    else:
        verdict = "all clear"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / f"{today}.md"
    report.write_text(
        f"---\ntype: maintenance\ndate: {today}\n---\n"
        f"# Ecosystem maintenance — {today}\n\n"
        f"**Verdict:** {verdict}\n\n" + "\n\n".join(sections) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"\nreport : {report}")
    print(f"verdict: {verdict}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
