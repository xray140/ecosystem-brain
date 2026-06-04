#!/usr/bin/env python3
"""SessionStart hook: suggest relevant installed agents for the current project.

Reads the SessionStart JSON on stdin (contains `cwd`), detects the project type
from marker files, then emits `additionalContext` listing installed agents whose
tags match — plus a hint to search for more. Pure stdlib, fast, non-blocking.

Wired in ~/.claude/settings.json under hooks.SessionStart.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Resolve the repo root from this script's own location (hooks/scripts/ -> repo).
# Avoids hardcoding /d/ paths, which Python on Windows misreads as D:\d\...
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALLED = REPO_ROOT / "registry" / "installed.json"
REGISTRY = REPO_ROOT / "registry" / "registry.json"

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


def normalize_path(raw: str) -> Path:
    """Convert a Git Bash mount path (/d/foo) to Windows form (D:/foo).

    Python on Windows misreads /d/foo as D:\\d\\foo, so translate the leading
    /<drive>/ segment back to <DRIVE>:/ . Leaves normal paths untouched.
    """
    if len(raw) >= 3 and raw[0] == "/" and raw[2] == "/" and raw[1].isalpha():
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
    if not all_agents:
        return 0  # nothing installed, say nothing

    # Rank: agents whose registry tags intersect the project's type tags first.
    relevant, generic = [], []
    for a in all_agents:
        tags = set(agent_tags(a["name"], registry))
        (relevant if tags & project_tags else generic).append(a["name"])

    lines = ["Ecosystem-brain installed agents available via the Agent tool:"]
    if relevant:
        lines.append(
            f"  Relevant to this project ({', '.join(sorted(project_tags)) or 'generic'}): "
            + ", ".join(relevant)
        )
    if generic:
        lines.append(f"  Also available: {', '.join(generic)}")
    lines.append(
        "  Find more: `uv run python /d/Claude_projects/ecosystem-brain/"
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
