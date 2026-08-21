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
import shutil
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode unicode markers.
# Force UTF-8 so output (and accented paths) never crash the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry_io

import github_util as gh
import layout
from scan_agent import quarantine, scan, worst

REPO_ROOT = Path(__file__).parent.parent
INSTALLED_FILE = REPO_ROOT / "registry" / "installed.json"

# Paths come from layout.py, shared with install-agent.py. Keeping a second copy
# here is what let update keep writing skills flat after install moved them to
# `skills/<name>/SKILL.md`: the update wrote vetted content to a path nothing
# loads, then advanced the registry pin — reporting "current" while the loaded
# skill stayed stale.


def sync_local(name: str, kind: str) -> tuple[str, bool]:
    """Re-sync a local agent from repo dir → global dir. Returns (status, changed)."""
    repo_file, global_file = layout.target_paths(kind, name)
    if not repo_file.exists():
        return "missing-in-repo", False
    content = repo_file.read_text(encoding="utf-8")
    if global_file.exists() and global_file.read_text(encoding="utf-8") == content:
        return "up-to-date", False
    global_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_file, global_file)
    return "synced", True


def _write_agent(name: str, kind: str, content: str) -> None:
    repo_file, global_file = layout.target_paths(kind, name)
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
    except Exception as e:  # network/parse: report it, don't crash the whole run
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
    # Record where we came from BEFORE advancing. Pinning exists so you control
    # when an agent moves; without the previous SHA there is no way to move back,
    # and an update that degrades an agent leaves only GitHub archaeology.
    if pinned and pinned != latest:
        entry["previous_commit"] = pinned
        entry["previous_hash"] = entry.get("hash")
    entry["hash"] = new_hash
    if latest:
        entry["commit"], entry["ref"] = latest, ref
    return f"updated ({diff})"


def rollback_item(entry: dict, kind: str) -> str:
    """Restore an agent to the SHA it was pinned at before the last update.

    The content is re-scanned on the way back in. It passed the gate once, but
    re-scanning costs nothing and means no path into an active agent file skips
    the scanner — including this one.
    """
    name = entry["name"]
    # Source first: "no previous pin" is technically true of a local agent too,
    # but it is the less useful of the two things to say.
    parsed = gh.parse_source(entry.get("source", "local"))
    if not parsed:
        return "local agent — roll back with git, not this"
    previous = entry.get("previous_commit")
    if not previous:
        return "no previous pin recorded — nothing to roll back to"
    repo, path = parsed
    current = entry.get("commit")
    try:
        content = gh.fetch_url(gh.raw_url(repo, path, previous))
    except Exception as e:  # network/parse: report it, don't crash the run
        return f"error: {e}"

    if worst(scan(content)) == "HIGH":
        q = quarantine(name, content, f"rollback blocked: HIGH risk at {gh.short(previous)}")
        return f"BLOCKED-unsafe (HIGH risk at the old pin; quarantined -> {q.name})"

    _write_agent(name, kind, content)
    entry["hash"] = gh.md5(content)
    entry["commit"] = previous
    # Swap rather than clear, so rolling back is itself undoable.
    entry["previous_commit"] = current
    entry["previous_hash"] = None
    return f"rolled back ({gh.short(current)} -> {gh.short(previous)})"


def status_symbol(status: str) -> str:
    """Display symbol for an update_item/sync_local status.

    `!` means "look at this". It used to be the fallback for everything the
    earlier cascade did not name, which swept in two perfectly ordinary
    outcomes: `local` (a first-party agent with no upstream to query — six of
    them, every run) and `synced` (a local agent re-copied to ~/.claude, i.e.
    success). In a weekly report skimmed for warnings, eight false warnings
    train you to ignore the column.
    """
    if "BLOCKED" in status:
        return "✗"  # refused: HIGH-risk upstream, quarantined
    if status.startswith("error:") or status == "missing-in-repo":
        return "!"  # genuinely needs attention
    if "up-to-date" in status:
        return "✓"  # includes "up-to-date (pinned -> sha)"
    if status.startswith("rolled back"):
        return "↓"  # restored to the previous pin
    if "update" in status:
        return "↑"  # updated, or update-available under --check
    if status == "synced":
        return "→"  # local agent re-copied to ~/.claude
    if status == "local":
        return "·"  # first-party, nothing upstream to check
    return "!"


def _save(data: dict) -> None:
    registry_io.save(data, INSTALLED_FILE)


def _do_rollback(data: dict, name: str) -> int:
    for kind in ("agents", "commands", "skills"):
        for entry in data.get(kind, []):
            if entry["name"] != name:
                continue
            status = rollback_item(entry, kind)
            print(f"  [{status_symbol(status)}] {kind[:-1]:10s} {name:30s}  {status}")
            if status.startswith("rolled back"):
                _save(data)
                print("\n[ok] installed.json updated")
                return 0
            return 1
    print(f"[error] no installed item named '{name}'")
    return 1


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
    ap.add_argument(
        "--rollback",
        metavar="NAME",
        help="restore NAME to the SHA it was pinned at before the last update",
    )
    args = ap.parse_args(argv)

    if not INSTALLED_FILE.exists():
        print("[warn] no installed.json found — nothing to update")
        return 0

    data = registry_io.load(INSTALLED_FILE)

    if args.rollback:
        return _do_rollback(data, args.rollback)
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
            print(f"  [{status_symbol(status)}] {kind[:-1]:10s} {entry['name']:30s}  {status}")
            # "updated (...)" applies new content; "pinned ->" advances provenance —
            # both mutate the entry and must be persisted.
            if "updated" in status or "pinned ->" in status:
                changed = True
            if "BLOCKED" in status:
                blocked += 1

    if changed and not args.check:
        _save(data)
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
