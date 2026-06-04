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
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode unicode markers.
# Force UTF-8 so output (and accented paths) never crash the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

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


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310
        return r.read().decode()


def is_github_source(source: str) -> bool:
    return source.startswith("http") or source.startswith("github:")


def github_url_from_source(source: str) -> str:
    if source.startswith("http"):
        return source
    # github:user/repo/path/to/file.md
    parts = source.removeprefix("github:").split("/", 2)
    user, repo, path = parts
    return f"https://raw.githubusercontent.com/{user}/{repo}/main/{path}"


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


def update_item(entry: dict, kind: str, check_only: bool) -> str:
    name = entry["name"]
    source = entry.get("source", "local")

    if is_github_source(source):
        try:
            url = github_url_from_source(source)
            new_content = fetch_url(url)
            new_hash = md5(new_content)
            old_hash = entry.get("hash")
            if old_hash == new_hash:
                return "up-to-date"
            if check_only:
                return "update-available"
            # Write updated file
            repo_file = REPO_DIRS[kind] / f"{name}.md"
            global_file = GLOBAL_DIRS[kind] / f"{name}.md"
            repo_file.parent.mkdir(parents=True, exist_ok=True)
            global_file.parent.mkdir(parents=True, exist_ok=True)
            repo_file.write_text(new_content, encoding="utf-8")
            shutil.copy2(repo_file, global_file)
            entry["hash"] = new_hash
            return "updated"
        except Exception as e:
            return f"error: {e}"
    else:
        if check_only:
            return "local"
        status, _ = sync_local(name, kind)
        return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--check", action="store_true", help="Report updates without applying"
    )
    ap.add_argument("--name", help="Update only this item")
    args = ap.parse_args(argv)

    if not INSTALLED_FILE.exists():
        print("[warn] no installed.json found — nothing to update")
        return 0

    data = json.loads(INSTALLED_FILE.read_text())
    changed = False

    for kind in ("agents", "commands", "skills"):
        for entry in data.get(kind, []):
            if args.name and entry["name"] != args.name:
                continue
            status = update_item(entry, kind, args.check)
            symbol = (
                "✓" if "up-to-date" in status else "↑" if "updated" in status else "!"
            )
            print(f"  [{symbol}] {kind[:-1]:10s} {entry['name']:30s}  {status}")
            if "updated" in status:
                changed = True

    if changed and not args.check:
        INSTALLED_FILE.write_text(json.dumps(data, indent=2) + "\n")
        print("\n[ok] installed.json updated")
    elif args.check:
        print("\n[info] run without --check to apply updates")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
