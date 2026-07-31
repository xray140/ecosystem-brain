#!/usr/bin/env python3
"""Where an installed item lives, and what it may be called.

Single source of truth for the install layout, imported by both `install-agent`
and `update-agents`. They used to answer this question separately, and drifted:
install started writing skills to `skills/<name>/SKILL.md` while update kept
writing them flat to `~/.claude/commands/`, so updating a skill wrote vetted
content to a path nothing loads and then advanced the registry pin anyway —
reporting "current" while the loaded copy stayed stale.

Two rules live here:

  * `target_paths` — agents and commands are flat `<dir>/<name>.md`; skills are
    `<dir>/<name>/SKILL.md`, because that is the only shape Claude Code loads
    and the only shape bootstrap's `*/SKILL.md` glob copies.
  * `safe_name` — the name is a filesystem path component that arrives from
    untrusted sources (a URL, a repo path, the registry), so it is validated
    before it can steer a write.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR = Path.home() / ".claude"

GLOBAL_AGENTS = CLAUDE_DIR / "agents"
GLOBAL_COMMANDS = CLAUDE_DIR / "commands" / "ecosystem-brain"
GLOBAL_SKILLS = CLAUDE_DIR / "skills"

# kind -> (repo dir, global dir). Keyed singular; `normalize_kind` accepts the
# plural form the registry uses.
TYPE_DIRS: dict[str, tuple[Path, Path]] = {
    "agent": (REPO_ROOT / "agents", GLOBAL_AGENTS),
    "command": (REPO_ROOT / "commands", GLOBAL_COMMANDS),
    "skill": (REPO_ROOT / "skills", GLOBAL_SKILLS),
}

_PLURAL = {"agents": "agent", "commands": "command", "skills": "skill"}

# Anchored with \Z, not $: `$` also matches before a trailing newline, so
# "evil\n" would have passed an otherwise-correct slug check.
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")

# Windows resolves these to devices regardless of extension or directory. As a
# flat file they behave, but a skill's `mkdir("nul")` succeeds silently and the
# SKILL.md write inside it then fails with an unhandled traceback. The name can
# come from upstream (`skills/nul/SKILL.md`), so it is not merely a typo guard.
RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def normalize_kind(kind: str) -> str:
    """Accept either 'skill' or the registry's plural 'skills'."""
    k = _PLURAL.get(kind, kind)
    if k not in TYPE_DIRS:
        raise ValueError(f"unknown kind {kind!r} — expected one of {sorted(TYPE_DIRS)}")
    return k


def safe_name(raw: str) -> str:
    """Validate and normalize a name used as a path component.

    Lowercased rather than rejected on case: these names become paths on a
    case-insensitive filesystem, where `Data-Engineer` and `data-engineer` are
    the same file, and upstream repos are inconsistent about it.

    Raises ValueError on anything that could steer the write elsewhere.
    """
    name = raw.strip().lower()
    if not SAFE_NAME.fullmatch(name) or ".." in name:
        raise ValueError(
            f"unsafe name {raw!r} — expected letters, digits, '.', '-', '_' "
            "(1-64 chars, starting alphanumeric, no path separators)"
        )
    if name.split(".")[0] in RESERVED:
        raise ValueError(f"unsafe name {raw!r} — reserved Windows device name")
    return name


def target_paths(kind: str, name: str) -> tuple[Path, Path]:
    """(repo_path, global_path) for an item of this kind. Validates `name`."""
    repo_dir, global_dir = TYPE_DIRS[normalize_kind(kind)]
    name = safe_name(name)
    if normalize_kind(kind) == "skill":
        return repo_dir / name / "SKILL.md", global_dir / name / "SKILL.md"
    return repo_dir / f"{name}.md", global_dir / f"{name}.md"
