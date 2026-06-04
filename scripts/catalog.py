#!/usr/bin/env python3
"""Build a local catalog of available agents and batch-install by category.

The catalog is a cached snapshot of a big collection repo (default: VoltAgent),
so the SessionStart suggester can recommend *uninstalled* agents matching the
project type without a live network call. Refresh it periodically.

Subcommands:
    catalog.py build [--repo R]            # fetch tree -> registry/catalog.json
    catalog.py install <category> [--repo R] [--limit N]   # batch-install a category
    catalog.py categories                  # list categories in the catalog

Examples:
    uv run python scripts/catalog.py build
    uv run python scripts/catalog.py categories
    uv run python scripts/catalog.py install 01-core-development --limit 5
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "registry" / "catalog.json"
DEFAULT_REPO = "VoltAgent/awesome-claude-code-subagents"

# keyword -> tag, inferred from the agent's filename/path
TAG_KEYWORDS = {
    "python": ["python"],
    "django": ["python", "django"],
    "fastapi": ["python", "api"],
    "flask": ["python"],
    "pytest": ["python", "testing"],
    "typescript": ["typescript"],
    "javascript": ["javascript"],
    "node": ["node"],
    "react": ["react", "frontend"],
    "vue": ["vue", "frontend"],
    "angular": ["angular", "frontend"],
    "frontend": ["frontend"],
    "backend": ["backend"],
    "fullstack": ["fullstack"],
    "rust": ["rust"],
    "golang": ["go"],
    "go-": ["go"],
    "java": ["java"],
    "csharp": ["csharp"],
    "cpp": ["cpp"],
    "ruby": ["ruby"],
    "php": ["php"],
    "elixir": ["elixir"],
    "kotlin": ["kotlin"],
    "api": ["api"],
    "graphql": ["api", "graphql"],
    "microservice": ["backend", "microservices"],
    "database": ["database"],
    "sql": ["database"],
    "devops": ["devops"],
    "kubernetes": ["devops", "k8s"],
    "docker": ["devops", "docker"],
    "security": ["security"],
    "test": ["testing"],
    "mobile": ["mobile"],
    "ios": ["mobile"],
    "android": ["mobile"],
    "ml": ["ml"],
    "ai": ["ai"],
}


def gh_api(args: list[str]) -> dict | list:
    try:
        out = subprocess.run(
            ["gh", "api", *args],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        sys.exit("[error] gh CLI not found — run `gh auth login`")
    except subprocess.CalledProcessError as e:
        sys.exit(f"[error] gh api failed: {e.stderr.strip()}")
    return json.loads(out.stdout)


def infer_tags(path: str) -> list[str]:
    low = path.lower()
    tags: set[str] = set()
    for kw, kw_tags in TAG_KEYWORDS.items():
        if kw in low:
            tags.update(kw_tags)
    # category folder like categories/02-language-specialists/...
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "categories":
        tags.add(parts[1])
    return sorted(tags)


def cmd_build(args) -> int:
    repo = args.repo
    print(f"fetching tree for {repo} ...")
    tree = gh_api([f"repos/{repo}/git/trees/main?recursive=1"])
    entries = tree.get("tree", []) if isinstance(tree, dict) else []
    agents = []
    for e in entries:
        path = e.get("path", "")
        if (
            path.startswith("categories/")
            and path.endswith(".md")
            and not path.endswith("README.md")
        ):
            name = Path(path).stem
            category = path.split("/")[1] if "/" in path else ""
            agents.append(
                {
                    "name": name,
                    "repo": repo,
                    "path": path,
                    "category": category,
                    "tags": infer_tags(path),
                }
            )
    catalog = {"repo": repo, "count": len(agents), "agents": agents}
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    cats = sorted({a["category"] for a in agents})
    print(
        f"[ok] catalog: {len(agents)} agents across {len(cats)} categories -> {CATALOG}"
    )
    return 0


def load_catalog() -> dict:
    if not CATALOG.exists():
        sys.exit("[error] no catalog — run: catalog.py build")
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def cmd_categories(args) -> int:
    cat = load_catalog()
    counts: dict[str, int] = {}
    for a in cat["agents"]:
        counts[a["category"]] = counts.get(a["category"], 0) + 1
    print(f"\ncategories in {cat['repo']}:\n")
    for c in sorted(counts):
        print(f"  {counts[c]:3d}  {c}")
    return 0


def cmd_install(args) -> int:
    cat = load_catalog()
    picks = [a for a in cat["agents"] if a["category"] == args.category]
    if not picks:
        print(f"no agents in category '{args.category}' — run: catalog.py categories")
        return 1
    if args.limit:
        picks = picks[: args.limit]
    installer = REPO_ROOT / "scripts" / "install-agent.py"
    print(
        f"installing {len(picks)} agents from {args.category} (each security-scanned):\n"
    )
    ok = blocked = 0
    for a in picks:
        r = subprocess.run(
            [
                "uv",
                "run",
                "python",
                str(installer),
                "--repo",
                a["repo"],
                "--path",
                a["path"],
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if r.returncode == 0:
            ok += 1
            print(f"  [ok]      {a['name']}")
        elif r.returncode == 2:
            blocked += 1
            print(f"  [BLOCKED] {a['name']} (security scan)")
        else:
            print(f"  [error]   {a['name']}: {r.stderr.strip()[:60]}")
    print(f"\ninstalled {ok}, blocked {blocked}, of {len(picks)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repo", default=DEFAULT_REPO)
    sub.add_parser("categories")
    i = sub.add_parser("install")
    i.add_argument("category")
    i.add_argument("--repo", default=DEFAULT_REPO)
    i.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    return {"build": cmd_build, "categories": cmd_categories, "install": cmd_install}[
        args.cmd
    ](args)


if __name__ == "__main__":
    raise SystemExit(main())
