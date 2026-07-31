#!/usr/bin/env python3
"""Check for and apply updates to all installed agents/skills/commands.

For GitHub-sourced items: re-fetches and compares hash.
For local items: re-syncs repo copy → global directory.

Usage:
    uv run python scripts/update-agents.py           # update all
    uv run python scripts/update-agents.py --check   # report only, no writes
    uv run python scripts/update-agents.py --name security-auditor
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode unicode markers.
# Force UTF-8 so output (and accented paths) never crash the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_util as gh  # noqa: E402
from scan_agent import quarantine, scan, worst  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
INSTALLED_FILE = REPO_ROOT / "registry" / "installed.json"
GLOBAL_AGENTS = Path.home() / ".claude" / "agents"
GLOBAL_COMMANDS = Path.home() / ".claude" / "commands" / "ecosystem-brain"

GLOBAL_DIRS: dict[str, Path] = {
    "agents": GLOBAL_AGENTS,
    "commands": GLOBAL_COMMANDS,
    "skills": GLOBAL_COMMANDS,
}
REPO_DIRS: dict[str, Path] = {
    "agents": REPO_ROOT / "agents",
    "commands": REPO_ROOT / "commands",
    "skills": REPO_ROOT / "skills",
}


def sync_local(name: str, kind: str) -> tuple[str, bool]:
    """Re-sync a local agent from repo dir → global dir. Returns (status, changed)."""
    repo_file = REPO_DIRS[kind] / f"{name}.md"
    global_file = GLOBAL_DIRS[kind] / f"{name}.md"
    if not repo_file.exists():
        return "missing-in-repo", False
    content = repo_file.read_text(encoding="utf-8")
    if global_file.exists() and global_file.read_text(encoding="utf-8") == content:
        return "up-to-date", False
    global_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_file, global_file)
    return "synced", True


def _write_agent(name: str, kind: str, content: str) -> None:
    repo_file = REPO_DIRS[kind] / f"{name}.md"
    global_file = GLOBAL_DIRS[kind] / f"{name}.md"
    repo_file.parent.mkdir(parents=True, exist_ok=True)
    global_file.parent.mkdir(parents=True, exist_ok=True)
    # .gitattributes pins *.md to eol=lf. Two distinct sources of CRLF to kill:
    # text mode translating \n on Windows (newline="\n"), and upstream content
    # already shipping \r\n (the .replace). Either one dirties git status.
    repo_file.write_text(content.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    shutil.copy2(repo_file, global_file)


def update_item(entry: dict, kind: str, check_only: bool) -> str:
    name = entry["name"]
    source = entry.get("source", "local")
    parsed = gh.parse_source(source) if gh.is_github_source(source) else None

    if not parsed:
        if check_only:
            return "local"
        return sync_local(name, kind)[0]

    repo, path = parsed
    ref = entry.get("ref", "main")
    pinned = entry.get("commit")
    try:
        latest = gh.resolve_commit(repo, ref)  # branch tip via gh (None if no gh)
        new_content = gh.fetch_url(gh.raw_url(repo, path, latest or ref))
    except Exception as e:  # noqa: BLE001 — network/parse: report, don't crash the run
        return f"error: {e}"
    new_hash = gh.md5(new_content)

    if new_hash == entry.get("hash"):
        # Content identical. Advance the pin if the tip moved — this also migrates
        # legacy unpinned entries to a SHA on the first update run.
        if not check_only and latest and pinned != latest:
            entry["commit"], entry["ref"] = latest, ref
            return f"up-to-date (pinned -> {gh.short(latest)})"
        return "up-to-date"

    diff = f"{gh.short(pinned)} -> {gh.short(latest)}"
    if check_only:
        cmp = gh.compare_url(repo, pinned, latest) if pinned and latest else ""
        return f"update-available ({diff})  {cmp}".rstrip()

    # Re-scan the new upstream content — it could be poisoned between installs.
    # Refuse a HIGH-risk update; stash it in quarantine/ and keep the current pin.
    if worst(scan(new_content)) == "HIGH":
        q = quarantine(
            name, new_content, f"update blocked: HIGH risk upstream ({repo}@{gh.short(latest)})"
        )
        return f"BLOCKED-unsafe (HIGH risk; quarantined -> {q.name}, kept current)"

    _write_agent(name, kind, new_content)
    entry["hash"] = new_hash
    if latest:
        entry["commit"], entry["ref"] = latest, ref
    return f"updated ({diff})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--check", action="store_true", help="Report updates without applying"
    )
    ap.add_argument("--name", help="Update only this item")
    ap.add_argument(
        "--all", action="store_true",
        help="Update every installed item (the default; explicit for clarity)",
    )
    args = ap.parse_args(argv)

    if not INSTALLED_FILE.exists():
        print("[warn] no installed.json found — nothing to update")
        return 0

    data = json.loads(INSTALLED_FILE.read_text(encoding="utf-8"))
    changed = False
    blocked = 0
    total = sum(
        1
        for kind in ("agents", "commands", "skills")
        for e in data.get(kind, [])
        if not args.name or e["name"] == args.name
    )
    scope = f"'{args.name}'" if args.name else f"all {total} installed items"
    print(f"updating {scope}{' (check only)' if args.check else ''}\n")

    for kind in ("agents", "commands", "skills"):
        for entry in data.get(kind, []):
            if args.name and entry["name"] != args.name:
                continue
            status = update_item(entry, kind, args.check)
            symbol = (
                "✓" if "up-to-date" in status
                else "✗" if "BLOCKED" in status
                else "↑" if "update" in status  # updated or update-available
                else "!"
            )
            print(f"  [{symbol}] {kind[:-1]:10s} {entry['name']:30s}  {status}")
            # "updated (...)" applies new content; "pinned ->" advances provenance —
            # both mutate the entry and must be persisted.
            if "updated" in status or "pinned ->" in status:
                changed = True
            if "BLOCKED" in status:
                blocked += 1

    if changed and not args.check:
        INSTALLED_FILE.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print("\n[ok] installed.json updated")
    elif args.check:
        print("\n[info] run without --check to apply updates")

    if blocked:
        print(
            f"[!] {blocked} update(s) blocked as HIGH-risk and quarantined — "
            "review quarantine/ before trusting."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
