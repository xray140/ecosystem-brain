#!/usr/bin/env python3
"""Search GitHub live for Claude Code agents/skills, ranked by popularity.

Uses the authenticated `gh` CLI (gh auth token) so code search works.
Two modes:
  * repo search  — find collections/repos (ranked by stars)
  * file search  — find individual agent .md files inside repos

Usage:
    uv run python scripts/search_agents.py "react testing"
    uv run python scripts/search_agents.py "security" --files
    uv run python scripts/search_agents.py "python" --files --limit 15

Output is a numbered table. Copy a repo+path into install-agent.py to install.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).parent.parent
REGISTRY = REPO_ROOT / "registry" / "registry.json"


def gh_api(args: list[str]) -> dict | list:
    """Call gh api and parse JSON. Raises with a readable message on failure."""
    try:
        out = subprocess.run(
            ["gh", "api", *args],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        sys.exit(
            "[error] gh CLI not found — install GitHub CLI and run `gh auth login`"
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"[error] gh api failed: {e.stderr.strip()}")
    return json.loads(out.stdout)


def search_repos(query: str, limit: int) -> list[dict]:
    # Restrict to name/description (not readme) so generic "awesome" lists that
    # merely mention everything don't crowd out genuine claude-code repos.
    q = f"{query} claude code agents in:name,description"
    data = gh_api(
        [
            "-X",
            "GET",
            "search/repositories",
            "-f",
            f"q={q}",
            "-f",
            "sort=stars",
            "-f",
            f"per_page={limit}",
        ]
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    return [
        {
            "stars": it["stargazers_count"],
            "repo": it["full_name"],
            "desc": (it.get("description") or "")[:80],
        }
        for it in items
    ]


def search_files(query: str, limit: int) -> list[dict]:
    # Code search: .md files living under an agents/ or .claude/agents/ path.
    q = f"{query} path:agents extension:md"
    data = gh_api(
        [
            "-X",
            "GET",
            "search/code",
            "-f",
            f"q={q}",
            "-f",
            f"per_page={limit}",
        ]
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    return [
        {
            "repo": it["repository"]["full_name"],
            "path": it["path"],
            "name": Path(it["path"]).stem,
        }
        for it in items
    ]


def known_sources() -> list[str]:
    if not REGISTRY.exists():
        return []
    reg = json.loads(REGISTRY.read_text())
    return [s["repo"] for s in reg.get("sources", [])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("query", help="search terms (e.g. 'react testing')")
    ap.add_argument(
        "--files",
        action="store_true",
        help="search individual agent files instead of repos",
    )
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args(argv)

    known = set(known_sources())

    if args.files:
        results = search_files(args.query, args.limit)
        if not results:
            print("no agent files found — try broader terms or --files off")
            return 0
        print(f"\nagent files matching '{args.query}':\n")
        for i, r in enumerate(results, 1):
            star = " ★known" if r["repo"] in known else ""
            print(f"  {i:2d}. {r['name']:28s}  {r['repo']}{star}")
            print(f"      install: --repo {r['repo']} --path {r['path']}")
    else:
        results = search_repos(args.query, args.limit)
        if not results:
            print("no repos found — try broader terms")
            return 0
        print(f"\nrepos matching '{args.query}' (by stars):\n")
        for i, r in enumerate(results, 1):
            star = " ★known" if r["repo"] in known else ""
            print(f"  {i:2d}. {r['stars']:>7,d}★  {r['repo']}{star}")
            print(f"           {r['desc']}")
        print("\ntip: add --files to find individual installable agent files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
