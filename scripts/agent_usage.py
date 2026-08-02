#!/usr/bin/env python3
"""Which installed agents actually get invoked — and which never have.

Every installed agent costs context on every SessionStart, because the suggester
lists it. Nothing measured whether any of them were ever used, so the roster only
ever grew.

Claude Code records each delegation in its session transcripts as a
`"subagent_type"` field, which makes the question answerable from data already
on disk. No network, no instrumentation to add.

**What "never" means here.** It means "not in the transcripts present on this
machine". Transcripts are local, and they can be rotated or deleted — an agent
you use daily on another PC reads as unused here. That is why this reports and
ranks, and never removes: the number is evidence, not a verdict.

First-party agents are listed separately and never proposed for removal. They
are the squad the SessionStart hook advertises on purpose; a zero there means
"start delegating to it", not "delete it".

Usage:
    uv run --no-project python scripts/agent_usage.py
    uv run --no-project python scripts/agent_usage.py --unused   # just the candidates
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO = Path(__file__).resolve().parent.parent
INSTALLED = REPO / "registry" / "installed.json"
TRANSCRIPTS = Path.home() / ".claude" / "projects"

# Matched textually rather than by parsing each JSONL record: the field sits
# inside a tool-call payload whose surrounding schema is Claude Code's, not ours,
# and a regex keeps working when that shape changes around it.
SUBAGENT_RE = re.compile(r'"subagent_type"\s*:\s*"([^"]+)"')


def scan_transcripts(root: Path | None = None) -> tuple[dict[str, int], dict[str, str]]:
    """(invocations per agent, last-seen date per agent) across all transcripts."""
    root = root or TRANSCRIPTS
    counts: collections.Counter[str] = collections.Counter()
    last_seen: dict[str, str] = {}
    if not root.is_dir():
        return {}, {}
    for f in root.rglob("*.jsonl"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            when = datetime.fromtimestamp(f.stat().st_mtime, UTC).date().isoformat()
        except OSError:
            continue
        for m in SUBAGENT_RE.finditer(text):
            name = m.group(1)
            counts[name] += 1
            if when > last_seen.get(name, ""):
                last_seen[name] = when
    return dict(counts), last_seen


def load_installed(path: Path | None = None) -> list[dict]:
    path = path or INSTALLED
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("agents", [])


def report(agents: list[dict], counts: dict[str, int], last_seen: dict[str, str]) -> dict:
    """Split the roster into first-party, used, and removal candidates."""
    first_party, used, unused = [], [], []
    for a in agents:
        row = {
            "name": a["name"],
            "local": a.get("source") == "local",
            "count": counts.get(a["name"], 0),
            "last": last_seen.get(a["name"], "—"),
        }
        if row["local"]:
            first_party.append(row)
        elif row["count"]:
            used.append(row)
        else:
            unused.append(row)
    used.sort(key=lambda r: -r["count"])
    return {"first_party": first_party, "used": used, "unused": unused}


def _print_rows(rows: list[dict]) -> None:
    for r in rows:
        seen = f"last {r['last']}" if r["count"] else "never invoked here"
        print(f"    {r['name']:24s} {r['count']:3d}x   {seen}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--unused", action="store_true", help="print only the removal candidates")
    args = ap.parse_args(argv)

    agents = load_installed()
    if not agents:
        print("[ok] no installed agents")
        return 0
    counts, last_seen = scan_transcripts()
    n_files = sum(1 for _ in TRANSCRIPTS.rglob("*.jsonl")) if TRANSCRIPTS.is_dir() else 0
    r = report(agents, counts, last_seen)

    if args.unused:
        for row in r["unused"]:
            print(row["name"])
        return 0

    print(f"agent usage — {len(agents)} installed, {n_files} local transcript(s) scanned\n")
    if r["first_party"]:
        print("  first-party squad (kept regardless — the hook advertises these):")
        _print_rows(r["first_party"])
    if r["used"]:
        print("\n  third-party, used:")
        _print_rows(r["used"])
    if r["unused"]:
        print("\n  third-party, never invoked on this machine:")
        _print_rows(r["unused"])
        print(
            f"\n  {len(r['unused'])} candidate(s) for removal. Transcripts are local and"
            "\n  can be rotated, so this is evidence rather than a verdict — an agent you"
            "\n  use on another PC reads as unused here. Remove one with:"
            "\n      rm agents/<name>.md ~/.claude/agents/<name>.md"
            "\n  then drop its entry from registry/installed.json."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
