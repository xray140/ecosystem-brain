#!/usr/bin/env python3
"""SessionStart hook: suggest relevant installed agents for the current project.

Reads the SessionStart JSON on stdin (contains `cwd`), detects the project type
from marker files, then emits `additionalContext` listing installed agents whose
tags match — plus a hint to search for more. Pure stdlib, fast, non-blocking.

Wired in ~/.claude/settings.json under hooks.SessionStart.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Drive-letter <-> Git-Bash-mount translation applies on Windows ONLY. Off
# Windows, `/d/projects/app` is a real posix path, not a mounted drive, and
# rewriting it to `D:/projects/app` points the hook at nothing — so it detects
# no project markers and silently suggests nothing. bootstrap.py has carried
# this guard since 2026-06-06; this copy never got it.
# See memory/decisions/windows-path-translation.md.
WINDOWS = os.name == "nt"

# Resolve the repo root from this script's own location (hooks/scripts/ -> repo).
# Avoids hardcoding /d/ paths, which Python on Windows misreads as D:\d\...
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALLED = REPO_ROOT / "registry" / "installed.json"
REGISTRY = REPO_ROOT / "registry" / "registry.json"
CATALOG = REPO_ROOT / "registry" / "catalog.json"
CATALOG_SEED = REPO_ROOT / "registry" / "catalog.seed.json"


def catalog_path():
    """The live catalog, else the committed seed, else None.

    catalog.json is gitignored (a scheduled task rewrites it weekly). Kept in
    step with catalog.py and init_project.py by a test that asserts all
    three resolve to the same file.
    """
    if CATALOG.exists():
        return CATALOG
    if CATALOG_SEED.exists():
        return CATALOG_SEED
    return None

# First-party squad: name -> when the control tower should delegate to it.
# Shown every session so the soldiers actually get used, not just defined.
FIRST_PARTY: dict[str, str] = {
    "security-auditor": "before any commit/push, or to review a diff",
    "convention-keeper": "before committing changes to rules / agents / scripts",
    "script-smith": "writing or fixing any .sh / .py script",
    "test-writer": "after implementing a feature, or to raise coverage",
    "bug-fixer": "given a stack trace, failing test, or \"X is broken\"",
    "memory-curator": "at session close, or for weekly vault hygiene",
}

# marker file -> project-type tags
MARKERS: dict[str, list[str]] = {
    "pyproject.toml": ["python", "pytest"],
    "setup.py": ["python"],
    "package.json": ["typescript", "javascript", "node"],
    "tsconfig.json": ["typescript"],
    "Cargo.toml": ["rust"],
    "go.mod": ["go"],
    "pom.xml": ["java"],
    "Gemfile": ["ruby"],
}


def to_bash_path(p: Path) -> str:
    """Windows C:/foo -> /c/foo (Git Bash mount form). Posix paths pass through."""
    s = p.as_posix()
    if WINDOWS and len(s) >= 2 and s[1] == ":":
        s = f"/{s[0].lower()}{s[2:]}"
    return s


def normalize_path(raw: str) -> Path:
    """Convert a Git Bash mount path (/d/foo) to Windows form (D:/foo).

    Python on Windows misreads /d/foo as D:\\d\\foo, so translate the leading
    /<drive>/ segment back to <DRIVE>:/ . Leaves normal paths untouched.

    Windows-only: off Windows the same string is a genuine posix path and must
    survive untouched.
    """
    if WINDOWS and len(raw) >= 3 and raw[0] == "/" and raw[2] == "/" and raw[1].isalpha():
        raw = f"{raw[1].upper()}:/{raw[3:]}"
    return Path(raw)


def detect_tags(cwd: Path) -> set[str]:
    tags: set[str] = set()
    for marker, marker_tags in MARKERS.items():
        if (cwd / marker).exists():
            tags.update(marker_tags)
    return tags


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def agent_tags(name: str, registry: dict) -> list[str]:
    for a in registry.get("agents", []):
        if a.get("name") == name:
            return a.get("tags", [])
    return []


def suggest_uninstalled(project_tags: set[str], installed_names: set[str],
                        limit: int = 5) -> list[dict]:
    """Top uninstalled catalog agents whose tags overlap the project's tags."""
    if not project_tags:
        return []
    path = catalog_path()
    catalog = load_json(path) if path else {}
    scored = []
    for a in catalog.get("agents", []):
        if a["name"] in installed_names:
            continue
        overlap = len(set(a.get("tags", [])) & project_tags)
        if overlap:
            scored.append((overlap, a))
    scored.sort(key=lambda t: (-t[0], t[1]["name"]))
    return [a for _, a in scored[:limit]]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    cwd = normalize_path(payload.get("cwd") or ".")

    project_tags = detect_tags(cwd)
    installed = load_json(INSTALLED)
    registry = load_json(REGISTRY)

    all_agents = installed.get("agents", [])
    installed_names = {a["name"] for a in all_agents}

    # Rank installed: agents whose registry tags intersect the project's tags.
    # First-party agents are surfaced separately (with triggers), so skip them here.
    relevant, generic = [], []
    for a in all_agents:
        name = a["name"]
        if name in FIRST_PARTY:
            continue
        tags = set(agent_tags(name, registry))
        (relevant if tags & project_tags else generic).append(name)

    squad = [(n, t) for n, t in FIRST_PARTY.items() if n in installed_names]

    # Suggest UNINSTALLED catalog agents matching the project type (no network —
    # reads the cached catalog.json built by catalog.py).
    suggestions = suggest_uninstalled(project_tags, installed_names, limit=5)

    if not all_agents and not suggestions:
        return 0

    lines = ["Ecosystem-brain agents:"]
    if squad:
        lines.append("  Delegate proactively (first-party squad):")
        for n, t in squad:
            lines.append(f"    - {n}: {t}")
    if relevant:
        lines.append(
            f"  Installed & relevant ({', '.join(sorted(project_tags)) or 'generic'}): "
            + ", ".join(relevant)
        )
    if generic:
        lines.append(f"  Installed (other): {', '.join(generic)}")
    if suggestions:
        lines.append("  Available to install for this project type:")
        for s in suggestions:
            lines.append(f"    - {s['name']}  (install: --repo {s['repo']} --path {s['path']})")
    # Built from this clone's real location — a hardcoded canonical path here
    # would send every session to a script that may not exist on this machine.
    lines.append(
        f"  Search more: `uv run python {to_bash_path(REPO_ROOT)}/"
        'scripts/search_agents.py "<topic>" --files`'
    )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
