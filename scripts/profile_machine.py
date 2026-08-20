#!/usr/bin/env python3
"""Write a vault note describing THIS machine, so a session knows where it is.

Proposed 2026-07-15 and parked. What made it worth building is what this session
kept running into: the vault is shared across machines, but almost everything in
it is machine-specific. Four project cards recorded a `D:` path that exists on
another PC; "never invoked" for an agent means "not in the transcripts on *this*
box"; the scheduled tasks are per-machine. Every one of those readings needed to
know which machine was asking, and nothing recorded it.

So this records the answer once, as an ordinary vault note:

    memory/machines/<hostname>.md

It is deliberately a **note, not a config**. It is read by a human or an agent
reasoning about a discrepancy ("this card says D: — is that this machine?"), not
consumed by code. Nothing branches on it.

Only facts that stay true for weeks: hostname, OS, drives, where the ecosystem
is cloned, which prerequisites resolve. No secrets, no environment dump, no
per-session state — a note that churns is a note nobody reads.

Usage:
    uv run --no-project python scripts/profile_machine.py            # write it
    uv run --no-project python scripts/profile_machine.py --print    # stdout only
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import string
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
MACHINES = REPO / "memory" / "machines"

# The tools the ecosystem's own checks depend on. Absence is worth recording:
# it explains why a check on this machine reports "skipped" rather than green.
PREREQS = ("git", "uv", "ruff", "node", "gh", "gitleaks", "ollama", "powershell")


def host() -> str:
    return platform.node() or "unknown-host"


def drives() -> list[str]:
    """Drive roots that exist here. This is the fact the project cards needed."""
    if os.name != "nt":
        return ["/"]
    return [f"{d}:" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]


def tools() -> dict[str, str | None]:
    return {t: shutil.which(t) for t in PREREQS}


def _git(*args: str) -> str:
    try:
        r = subprocess.run(  # noqa: PLW1510 — returncode inspected below
            ["git", "-C", str(REPO), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def compose() -> str:
    """The note. Local date, since a human reads it in their own timezone."""
    today = datetime.now(UTC).astimezone().date().isoformat()
    found = tools()
    missing = [t for t, path in found.items() if not path]
    present = [t for t, path in found.items() if path]

    lines = [
        "---",
        "type: machine",
        "status: active",
        f"host: {host()}",
        f"updated: {today}",
        "tags: [machine, environment]",
        "---",
        f"# {host()}",
        "",
        "Written by `scripts/profile_machine.py`. Regenerate rather than edit —",
        "it is derived, and a hand-edit will be silently overwritten.",
        "",
        "`updated` is the date these facts last *changed*. Re-running on a machine",
        "that has not changed leaves the file alone, so the note never appears in",
        "a diff for having been regenerated.",
        "",
        "## Identity",
        f"- **host**: `{host()}`",
        f"- **os**: {platform.system()} {platform.release()} ({platform.machine()})",
        f"- **drives present**: {', '.join(drives())}",
        "",
        "A vault card naming a drive that is not in that list describes a project",
        "on a different machine — not a lost one.",
        "",
        "## This clone",
        f"- **path**: `{REPO}`",
        # No branch line. It changes on every checkout, so the note rewrote
        # itself constantly and showed up dirty in unrelated commits — twice it
        # was nearly committed recording a feature branch as this machine's
        # durable state. The docstring's own rule: no per-session state.
        f"- **remote**: {_git('remote', 'get-url', 'origin') or 'none'}",
        "",
        "## Tooling",
        f"- **present**: {', '.join(present) if present else 'none'}",
        f"- **missing**: {', '.join(missing) if missing else 'none'}",
        "",
    ]
    if missing:
        lines += [
            "A check that reports *skipped* on this machine is usually explained by",
            "that missing list, not by a fault.",
            "",
        ]
    lines += ["## Links", "- [[roadmap]]", ""]
    return "\n".join(lines)


def facts(note: str) -> str:
    """The note minus its `updated:` line — what actually describes the machine.

    Comparing on this is what makes a re-run a no-op: regenerating on an
    unchanged machine differs only in that date, and rewriting for it produced a
    tracked file that went dirty on every run of the weekly heartbeat.
    """
    return "\n".join(ln for ln in note.split("\n") if not ln.startswith("updated:"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--print", action="store_true", help="write to stdout, not the vault")
    args = ap.parse_args(argv)

    note = compose()
    if args.print:
        print(note)
        return 0

    MACHINES.mkdir(parents=True, exist_ok=True)
    dest = MACHINES / f"{host()}.md"
    existed = dest.exists()
    unchanged = existed and facts(dest.read_text(encoding="utf-8")) == facts(note)
    if not unchanged:
        dest.write_text(note, encoding="utf-8", newline="\n")
    # relative_to raises when the destination is not under the repo — which it
    # is not when MACHINES is redirected. Report the path either way rather than
    # crashing on the success message.
    try:
        shown = dest.relative_to(REPO).as_posix()
    except ValueError:
        shown = str(dest)
    if unchanged:
        verb = "unchanged"
    else:
        verb = "updated" if existed else "wrote"
    print(f"[ok] {verb} {shown}")
    print(f"     host={host()}  drives={', '.join(drives())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
