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
import platform
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry_io

REPO = Path(__file__).resolve().parent.parent
INSTALLED = REPO / "registry" / "installed.json"
TRANSCRIPTS = Path.home() / ".claude" / "projects"

# Matched textually rather than by parsing each JSONL record: the field sits
# inside a tool-call payload whose surrounding schema is Claude Code's, not ours,
# and a regex keeps working when that shape changes around it.
SUBAGENT_RE = re.compile(r'"subagent_type"\s*:\s*"([^"]+)"')


def scan_transcripts(root: Path | None = None) -> tuple[dict[str, int], dict[str, str]]:
    """(invocations per agent, last-seen date per agent) across all transcripts."""
    return scan_transcripts_windowed(root)[:2]


def scan_transcripts_windowed(
    root: Path | None = None,
) -> tuple[dict[str, int], dict[str, str], str | None]:
    """As above, plus the DATE OF THE OLDEST transcript.

    Without that date, "never invoked" reads as "never since it was installed",
    when it can only ever mean "never in the transcripts still on disk". Here
    those span 26 days while the oldest agent was installed 60 days ago — a
    34-day blind spot the report has to admit to, or it overstates its evidence
    and invites deleting something that is used.
    """
    root = root or TRANSCRIPTS
    counts: collections.Counter[str] = collections.Counter()
    last_seen: dict[str, str] = {}
    oldest: str | None = None
    if not root.is_dir():
        return {}, {}, None
    for f in root.rglob("*.jsonl"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            when = datetime.fromtimestamp(f.stat().st_mtime, UTC).date().isoformat()
        except OSError:
            continue
        if oldest is None or when < oldest:
            oldest = when
        for m in SUBAGENT_RE.finditer(text):
            name = m.group(1)
            counts[name] += 1
            if when > last_seen.get(name, ""):
                last_seen[name] = when
    return dict(counts), last_seen, oldest


LEDGER = REPO / "registry" / "agent-usage.json"


def load_ledger(path: Path | None = None) -> dict:
    """Durable record of which agents have ever been invoked, and where.

    Transcripts are the evidence and they rotate: this machine holds one day's
    worth, so every agent reads "never invoked" and the report has to disclaim
    its own central number. The ledger is the accumulated part — once an agent
    has been seen, that fact survives the transcript being deleted.

    Dates, not counts. The decision this feeds is "remove this agent or keep it",
    for which ever-versus-never is the whole question; a count would also have to
    solve double-counting as transcripts roll, and would be wrong more often than
    it was useful.

    Tracked in git and keyed by machine — the opposite call from registry_io,
    deliberately. There the machine-specific field made the file conflict on
    every pull; here the machine IS the finding, because "unused on MSI" and
    "unused anywhere" are different verdicts and only the second justifies
    removing a shared agent. Each machine writes only its own key, so two
    machines never edit the same lines.
    """
    path = path or LEDGER
    if not path.is_file():
        return {"_version": 1, "machines": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_version": 1, "machines": {}}


def record(last_seen: dict[str, str], path: Path | None = None, host: str | None = None) -> dict:
    """Fold this machine's current evidence into the ledger and write it.

    Idempotent: re-running on the same transcripts changes nothing, because each
    date only ever advances. `since` is the earliest evidence this machine has
    ever contributed, which is what widens the window past what is still on disk.
    """
    path = path or LEDGER
    host = host or platform.node() or "unknown"
    ledger = load_ledger(path)
    today = datetime.now(UTC).date().isoformat()
    entry = ledger.setdefault("machines", {}).setdefault(host, {})
    agents = entry.setdefault("agents", {})
    for name, when in last_seen.items():
        if when > agents.get(name, ""):
            agents[name] = when
    # Earliest evidence ever contributed by this machine — not today's oldest
    # transcript, which moves forward as old ones are deleted.
    candidates = [d for d in [entry.get("since"), *last_seen.values()] if d]
    entry["since"] = min(candidates) if candidates else today
    entry["updated"] = today
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return ledger


def ledger_seen(ledger: dict) -> dict[str, str]:
    """agent -> most recent date seen on ANY machine."""
    out: dict[str, str] = {}
    for entry in ledger.get("machines", {}).values():
        for name, when in (entry.get("agents") or {}).items():
            if when > out.get(name, ""):
                out[name] = when
    return out


def ledger_since(ledger: dict) -> str | None:
    """Earliest date any machine has evidence for — the real evidence window."""
    dates = [e["since"] for e in ledger.get("machines", {}).values() if e.get("since")]
    return min(dates) if dates else None


def load_installed(path: Path | None = None) -> list[dict]:
    """Agents with this machine's `installed_at` merged back in — the blind-window
    warning below compares it against local transcripts, so it must be local."""
    path = path or INSTALLED
    if not path.is_file():
        return []
    return registry_io.load(path).get("agents", [])


def report(
    agents: list[dict],
    counts: dict[str, int],
    last_seen: dict[str, str],
    remembered: dict[str, str] | None = None,
) -> dict:
    """Split the roster into first-party, used, and removal candidates.

    `remembered` is the ledger's agent -> last-seen across all machines. An agent
    is a removal candidate only when neither the surviving transcripts nor the
    ledger has ever seen it — otherwise "unused" means "unused since the last
    transcript rotation", which is not a reason to delete anything.
    """
    remembered = remembered or {}
    first_party, used, unused = [], [], []
    for a in agents:
        name = a["name"]
        ever = remembered.get(name)
        row = {
            "name": name,
            "local": a.get("source") == "local",
            "count": counts.get(name, 0),
            "last": last_seen.get(name) or ever or "—",
            "elsewhere": bool(ever) and not counts.get(name),
        }
        if row["local"]:
            first_party.append(row)
        elif row["count"] or ever:
            used.append(row)
        else:
            unused.append(row)
    used.sort(key=lambda r: (-r["count"], r["name"]))
    return {"first_party": first_party, "used": used, "unused": unused}


def _print_rows(rows: list[dict]) -> None:
    for r in rows:
        if r["count"]:
            seen = f"last {r['last']}"
        elif r["elsewhere"]:
            # Recorded before the current transcripts existed, or on another
            # machine. Either way it is evidence of use, not of absence.
            seen = f"last {r['last']} (from the ledger)"
        else:
            seen = "never invoked here"
        print(f"    {r['name']:24s} {r['count']:3d}x   {seen}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--unused", action="store_true", help="print only the removal candidates")
    ap.add_argument(
        "--record",
        action="store_true",
        help="fold today's evidence into registry/agent-usage.json before reporting",
    )
    args = ap.parse_args(argv)

    agents = load_installed()
    if not agents:
        print("[ok] no installed agents")
        return 0
    counts, last_seen, oldest = scan_transcripts_windowed()
    n_files = sum(1 for _ in TRANSCRIPTS.rglob("*.jsonl")) if TRANSCRIPTS.is_dir() else 0
    ledger = record(last_seen) if args.record else load_ledger()
    remembered = ledger_seen(ledger)
    since = ledger_since(ledger)
    r = report(agents, counts, last_seen, remembered)

    if args.unused:
        for row in r["unused"]:
            print(row["name"])
        return 0

    print(f"agent usage — {len(agents)} installed, {n_files} local transcript(s) scanned")
    # The ledger's reach, when it has any, is the real window: transcripts rotate
    # but the record of having seen an agent does not.
    window = min([d for d in (since, oldest) if d], default=None)
    if window:
        source = "ledger + transcripts" if since else "transcripts only"
        print(f"  evidence window: {window} -> today ({source})")
        blind = [
            a["name"]
            for a in agents
            if a.get("source") != "local"
            and (a.get("installed_at") or "9999") < window
            and a["name"] not in remembered
        ]
        if blind:
            print(
                f"  [!] {len(blind)} agent(s) were installed BEFORE the evidence window,"
                f"\n      so 'never invoked' cannot speak for their first weeks: "
                + ", ".join(blind)
            )
    print()
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
