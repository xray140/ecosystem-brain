#!/usr/bin/env python3
"""Install an agent, skill, or command from a GitHub URL or local path.

Usage:
    # Install from a GitHub raw URL
    uv run python scripts/install-agent.py --url https://raw.githubusercontent.com/user/repo/main/agents/my-agent.md

    # Install from a GitHub repo (sparse-fetches a single file)
    uv run python scripts/install-agent.py --repo user/repo --path agents/my-agent.md

    # Install from a local file (copies + registers)
    uv run python scripts/install-agent.py --file /path/to/my-agent.md --type agent

    # List installed
    uv run python scripts/install-agent.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REGISTRY_DIR = REPO_ROOT / "registry"
INSTALLED_FILE = REGISTRY_DIR / "installed.json"
GLOBAL_AGENTS = Path.home() / ".claude" / "agents"
GLOBAL_COMMANDS = Path.home() / ".claude" / "commands" / "ecosystem-brain"

TYPE_DIRS: dict[str, tuple[Path, Path]] = {
    "agent": (REPO_ROOT / "agents", GLOBAL_AGENTS),
    "command": (REPO_ROOT / "commands", GLOBAL_COMMANDS),
    "skill": (REPO_ROOT / "skills", GLOBAL_COMMANDS),
}


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def load_installed() -> dict:
    if INSTALLED_FILE.exists():
        return json.loads(INSTALLED_FILE.read_text())
    return {"_version": 1, "agents": [], "commands": [], "skills": []}


def save_installed(data: dict) -> None:
    INSTALLED_FILE.write_text(json.dumps(data, indent=2) + "\n")


def detect_type(content: str, filename: str) -> str:
    """Guess type from frontmatter or filename."""
    if "tools:" in content and "---" in content:
        return "agent"
    if filename.endswith(".md"):
        return "command"
    return "skill"


def install_content(content: str, name: str, item_type: str, source: str) -> None:
    repo_dir, global_dir = TYPE_DIRS[item_type]
    repo_dir.mkdir(parents=True, exist_ok=True)
    global_dir.mkdir(parents=True, exist_ok=True)

    fname = f"{name}.md"
    repo_path = repo_dir / fname
    global_path = global_dir / fname

    repo_path.write_text(content, encoding="utf-8")
    shutil.copy2(repo_path, global_path)

    installed = load_installed()
    key = f"{item_type}s"
    entries = installed.setdefault(key, [])
    # Update or append
    for entry in entries:
        if entry["name"] == name:
            entry.update(
                {
                    "source": source,
                    "hash": md5(content),
                    "installed_at": datetime.now(timezone.utc).date().isoformat(),
                }
            )
            break
    else:
        entries.append(
            {
                "name": name,
                "source": source,
                "hash": md5(content),
                "installed_at": datetime.now(timezone.utc).date().isoformat(),
                "global_path": str(global_path),
            }
        )
    save_installed(installed)
    print(f"[ok] installed {item_type} '{name}' -> {global_path}")


def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310
        return r.read().decode()


def github_raw_url(repo: str, path: str, branch: str = "main") -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--url", help="Raw GitHub URL to a markdown file")
    ap.add_argument("--repo", help="GitHub repo (user/repo)")
    ap.add_argument("--path", help="Path within repo (used with --repo)")
    ap.add_argument("--branch", default="main", help="Branch (default: main)")
    ap.add_argument("--file", help="Local file path")
    ap.add_argument(
        "--type", choices=["agent", "command", "skill"], help="Override type detection"
    )
    ap.add_argument("--name", help="Override name (default: filename stem)")
    ap.add_argument("--list", action="store_true", help="List installed items")
    args = ap.parse_args(argv)

    if args.list:
        data = load_installed()
        for kind in ("agents", "commands", "skills"):
            items = data.get(kind, [])
            if items:
                print(f"\n{kind}:")
                for item in items:
                    print(
                        f"  {item['name']:30s}  source={item['source']}  "
                        f"installed={item.get('installed_at', '?')}"
                    )
        return 0

    if args.url:
        content = fetch_url(args.url)
        filename = args.url.rstrip("/").split("/")[-1]
        source = args.url
    elif args.repo and args.path:
        url = github_raw_url(args.repo, args.path, args.branch)
        content = fetch_url(url)
        filename = args.path.split("/")[-1]
        source = f"github:{args.repo}/{args.path}"
    elif args.file:
        content = Path(args.file).read_text(encoding="utf-8")
        filename = Path(args.file).name
        source = "local"
    else:
        ap.error("provide --url, --repo+--path, or --file")
        return 1

    name = args.name or Path(filename).stem
    item_type = args.type or detect_type(content, filename)
    install_content(content, name, item_type, source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
