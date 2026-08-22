#!/usr/bin/env python3
"""Health check for the PROJECTS the ecosystem created, not the ecosystem itself.

`doctor.py` answers "is my install wired up correctly". Nothing answered "are the
projects I registered still there, and still healthy" — the vault's project cards
were written once at init and never read back by anything. They drifted silently:
four cards still say `status: active` while pointing at `D:\\claude-projects\\...`,
a drive path that no longer exists on this machine.

This reports; it does not repair. When a path is wrong only you know whether the
project was deleted, moved, or lives on a machine that isn't this one — and the
right fix differs in each case. Two escape hatches, both a one-line edit to the
card:

  * the project moved  -> update its `- Project: ` line
  * the project is done -> set `status: archived` in the frontmatter

Archived cards are reported but never fail the run, so a deliberate decision
stops nagging you while an unexamined one keeps showing up.

Usage:
    uv run --no-project python scripts/project_doctor.py
    uv run --no-project python scripts/project_doctor.py --no-ci   # skip gh calls
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_spec

REPO = Path(__file__).resolve().parent.parent
VAULT_PROJECTS = REPO / "memory" / "projects"

# The card records its path on a `- Project: ` line, in backticks, sometimes
# followed by prose in parentheses. Capture only what's inside the backticks —
# `ipe-pipeline` records a folder whose name differs from the card's, so
# guessing the directory from the card name finds the wrong answer (or none).
PATH_RE = re.compile(r"^- Project:\s*`([^`]+)`", re.M)
STATUS_RE = re.compile(r"^status:\s*(\S+)", re.M)
# Optional. The vault is shared across machines but project locations are not:
# `D:\claude-projects\x` is a correct path — on the PC that has a D: drive.
HOST_RE = re.compile(r"^host:\s*(\S+)", re.M)

# `.env.example` directive parsing lives in env_spec, which secrets-doctor.sh
# also calls — one implementation, two callers. Re-exported here because callers
# and tests referenced these names before the extraction.
ONE_OF_RE = env_spec.ONE_OF_RE
OPTIONAL_RE = env_spec.OPTIONAL_RE

# A project untouched for this long is worth a glance — not a failure.
STALE_DAYS = 90

HOST = platform.node()


def parse_card(text: str) -> dict:
    """{status, path, host} from a project card. Missing keys are None."""
    return {
        "status": m.group(1) if (m := STATUS_RE.search(text)) else "unknown",
        "path": m.group(1) if (m := PATH_RE.search(text)) else None,
        "host": m.group(1) if (m := HOST_RE.search(text)) else None,
    }


def root_is_absent(path: Path) -> bool:
    """True when the path's whole root is missing — a different machine, or an
    unmounted drive.

    This is the distinction between "gone" and "not here". `D:\\claude-projects\\x`
    with no `D:\\` at all is not a deleted project; it is a project on the PC that
    has that drive. Reporting it as a missing path reads as data loss and sends
    you looking for something that was never lost.

    On posix the anchor is `/`, which always exists, so this correctly returns
    False and the ordinary "path does not exist" verdict applies.
    """
    anchor = path.anchor
    return bool(anchor) and not Path(anchor).exists()


def load_cards(vault: Path | None = None) -> list[dict]:
    """Read every project card in the vault.

    `vault=None` resolves VAULT_PROJECTS at CALL time, not at import time. A
    default of `vault: Path = VAULT_PROJECTS` binds the constant when the module
    loads, which silently ignores any later override — so tests pointed at a
    temp vault would quietly audit the real one. (init_project.append_to_moc
    still has that shape; it takes an explicit `moc=` argument instead.)
    """
    vault = vault or VAULT_PROJECTS
    cards = []
    for f in sorted(vault.glob("*.md")):
        cards.append(
            {"name": f.stem, "card": f, **parse_card(f.read_text(encoding="utf-8"))}
        )
    return cards


def _git(repo: Path, *args: str) -> str | None:
    """git output in `repo`, or None if it isn't a repo / git is unavailable."""
    try:
        r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, ValueError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def env_gap(project: Path) -> list[str]:
    """Key names present in .env.example but absent from .env.

    The ecosystem seeds .env from the example at init; keys added to the example
    afterwards never reach the .env, and the failure shows up as a confusing
    runtime error rather than a missing-config message.

    Parsing lives in env_spec, shared with secrets-doctor.sh. Two independent
    parsers of one format is how the bash side came to exclude `optional` keys
    but not `one-of` members, reporting the unchosen alternative as missing.
    """
    example, env = project / ".env.example", project / ".env"
    if not example.is_file() or not env.is_file():
        return []
    return env_spec.gaps(example, env)


def ci_status(project: Path) -> str | None:
    """Conclusion of the newest CI run, or None when there's nothing to ask.

    Advisory only: no network, no gh, no remote, or a rate limit must never turn
    this check red — that would make the heartbeat depend on GitHub being up.
    """
    if not shutil.which("gh") or not (project / ".github" / "workflows").is_dir():
        return None
    remote = _git(project, "remote", "get-url", "origin") or ""
    if "github.com" not in remote:
        return None
    try:
        r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
            [
                "gh",
                "run",
                "list",
                "--limit",
                "1",
                "--json",
                "conclusion",
                "--jq",
                ".[0].conclusion",
            ],
            cwd=str(project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and out and out != "null" else None


def inspect(card: dict, *, want_ci: bool) -> dict:
    """Everything worth knowing about one registered project."""
    result = dict(card, problems=[], notes=[])
    if not card["path"]:
        result["problems"].append("card records no `- Project: ` path")
        return result

    project = Path(os.path.expandvars(card["path"])).expanduser()
    result["resolved"] = project

    # A card pinned to another machine is not this machine's business.
    if card.get("host") and card["host"] != HOST:
        result["elsewhere"] = card["host"]
        return result

    if not project.is_dir():
        # "Not here" and "gone" are different findings, and only one of them is
        # alarming. A whole missing root means the drive isn't on this machine.
        if root_is_absent(project):
            result["elsewhere"] = f"root {project.anchor} not on {HOST}"
            result["notes"].append(
                "cannot be checked from here — add `host:` to the card to pin it"
            )
            return result
        result["problems"].append(f"path does not exist: {project}")
        return result

    if (head := _git(project, "log", "-1", "--format=%cI")) is None:
        result["notes"].append("not a git repository")
    else:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(head)).days
            result["age_days"] = age
            if age > STALE_DAYS:
                result["notes"].append(f"no commit in {age} days")
        except ValueError:
            pass
        if _git(project, "status", "--porcelain"):
            result["notes"].append("uncommitted changes")

    if not (project / "AGENTS.md").is_file():
        result["notes"].append("no AGENTS.md (the cross-tool rules file)")
    if missing := env_gap(project):
        result["notes"].append(f".env is missing {len(missing)} key(s): {', '.join(missing[:4])}")
    if want_ci and (ci := ci_status(project)) and ci != "success":
        result["problems"].append(f"latest CI run: {ci}")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--no-ci", action="store_true", help="skip the GitHub CI lookup")
    args = ap.parse_args(argv)

    cards = load_cards()
    print(f"ecosystem-brain project doctor\n  vault : {VAULT_PROJECTS}")
    print(f"  host  : {HOST}")
    print(f"  cards : {len(cards)}\n")
    if not cards:
        print("[ok] no registered projects")
        return 0

    failing = elsewhere = 0
    for card in cards:
        if card["status"] == "archived":
            print(f"  [--] {card['name']:36s} archived")
            continue
        r = inspect(card, want_ci=not args.no_ci)
        if r["problems"]:
            failing += 1
            print(f"  [!!] {card['name']:36s} {r['problems'][0]}")
            for extra in r["problems"][1:]:
                print(f"       {'':36s} {extra}")
        elif r.get("elsewhere"):
            elsewhere += 1
            print(f"  [->] {card['name']:36s} elsewhere: {r['elsewhere']}")
        else:
            summary = "; ".join(r["notes"]) if r["notes"] else "healthy"
            mark = "ok" if not r["notes"] else "??"
            print(f"  [{mark}] {card['name']:36s} {summary}")

    if elsewhere:
        # No "add `host:`" advice here: a card only reaches this branch BECAUSE it
        # already has one. Telling you to do the thing you just did leaves a
        # nag with no way to satisfy it, which trains you to ignore the footer.
        print(
            f"\n  {elsewhere} project(s) are pinned to another machine — not"
            f" checkable from {HOST}, and not counted as failures."
        )

    print()
    if failing:
        print(f"[!] {failing} of {len(cards)} registered project(s) need attention.")
        print("    Fix the card, whichever is true:")
        print("      moved  -> update its `- Project: ` line")
        print("      done   -> set `status: archived` in the frontmatter")
        return 1
    print(f"[ok] all {len(cards)} registered projects accounted for")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
