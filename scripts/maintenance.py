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

    print(f"ecosystem maintenance — {today}\n")
    for label, cmd, gating in CHECKS:
        r = run(cmd)
        bad = gating and r.returncode != 0
        status = "FAIL" if bad else "ok"
        if bad:
            failed.append(label)
        print(f"  [{status:4s}] {label}")
        body = (r.stdout + r.stderr).strip() or "(no output)"
        sections.append(f"## {label} — {status}\n\n```\n{body}\n```")

    verdict = "all clear" if not failed else f"NEEDS ATTENTION: {', '.join(failed)}"
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
