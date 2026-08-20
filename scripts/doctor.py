#!/usr/bin/env python3
"""Health + drift doctor for the ecosystem-brain install.

Answers the question `bootstrap --verify` only half-answered: "is my live Claude
Code config actually in sync with this repo?" Checks:

  1. Hooks live   — every hook script path in settings.json resolves on disk.
  2. Sync drift   — each repo command/agent matches its copy in ~/.claude, after
                    the same path-rewrite bootstrap applies on copy (so a clone at
                    a different path isn't flagged — only real edits are).
  3. Orphans      — the reverse direction: a file this repo installed and has
                    since DELETED, still sitting live. Checked against
                    bootstrap's install manifest, so files the ecosystem never
                    installed are never touched or blamed.
  4. Prerequisites — uv/git/node/gh/gitleaks/ruff/ollama on PATH (advisory).

Exit non-zero if hooks are broken or anything has drifted. Fix drift by re-running
bootstrap.

Usage:
    uv run --no-project python scripts/doctor.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap as bs  # reuse REPO_ROOT, CLAUDE_DIR, rewrite_paths, verify_live

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO = bs.REPO_ROOT
CLAUDE_DIR = bs.CLAUDE_DIR


def drift_in(
    repo_dir: Path, live_dir: Path, bash_root: str, label: str, pattern: str = "*.md"
) -> list[tuple[str, str]]:
    """(file, reason) pairs where the live copy differs from the repo source.

    Compares against the rewritten repo content (the exact bytes bootstrap would
    write), so the intended per-clone path substitution is not mistaken for drift.

    `pattern` mirrors how bootstrap copies each kind: commands and agents are a
    flat `*.md`, skills are `<name>/SKILL.md` one level down. Paths are compared
    relative to repo_dir so both layouts map onto the live tree unchanged.
    """
    problems: list[tuple[str, str]] = []
    if not repo_dir.is_dir():
        return problems
    for f in sorted(repo_dir.glob(pattern)):
        rel = f.relative_to(repo_dir)
        live = live_dir / rel
        expected = bs.rewrite_paths(f.read_text(encoding="utf-8"), bash_root)
        if not live.exists():
            problems.append((f"{label}/{rel.as_posix()}", "missing in ~/.claude"))
        elif live.read_text(encoding="utf-8") != expected:
            problems.append((f"{label}/{rel.as_posix()}", "drifted — re-run bootstrap"))
    return problems


def hooks_wiring_drift(bash_root: str) -> bool:
    """True when the live settings.json hook wiring differs from what
    bootstrap would write from hooks/hooks.json.

    verify_live only checks that referenced scripts exist — it stays green when
    hooks.json gains/changes an entry that was never re-bootstrapped. This check
    closes that gap by comparing the wiring itself.
    """
    if not bs.SETTINGS.exists():
        return False
    expected = bs.load_hooks(bash_root)
    live = json.loads(bs.SETTINGS.read_text(encoding="utf-8")).get("hooks", {})
    return live != expected


def orphans_live() -> tuple[list[str] | None, int]:
    """(orphaned live paths, manifest size) — None when there is no manifest.

    An orphan is a path bootstrap's manifest says THIS repo installed, that the
    repo no longer produces, and that is still on disk. Scoping to the manifest
    is what makes the check safe to gate on: a user's own agent under
    ~/.claude/agents was never in it, so it can never be reported here.

    The distinction the one-way check could not make: `drift_in` walks the repo
    and asks "is each file live?". Nothing walked the other way, so deleting an
    agent from the repo removed it from every future comparison — and it kept
    loading into every session under a green report.
    """
    if not bs.INSTALL_MANIFEST.is_file():
        return None, 0
    recorded = bs.read_manifest()
    expected = {
        bs._live_rel(bs.CLAUDE_DIR / "commands" / "ecosystem-brain" / f.name)
        for f in (REPO / "commands").glob("*.md")
    }
    expected |= {
        bs._live_rel(bs.CLAUDE_DIR / "agents" / f.name) for f in (REPO / "agents").glob("*.md")
    }
    expected |= {
        bs._live_rel(bs.CLAUDE_DIR / "skills" / m.parent.name / "SKILL.md")
        for m in (REPO / "skills").glob("*/SKILL.md")
    }
    stale = [r for r in recorded if r not in expected and (bs.CLAUDE_DIR / r).is_file()]
    return sorted(stale), len(recorded)

def main() -> int:
    bash_root = bs.to_bash_path(REPO)
    print("ecosystem-brain doctor")
    print(f"  repo : {REPO}")
    print(f"  live : {CLAUDE_DIR}\n")
    fails: list[str] = []

    # 1. hooks live (reuse bootstrap's verifier — prints its own lines)
    print("1. Hooks")
    if bs.verify_live() != 0:
        fails.append("hooks")
    if hooks_wiring_drift(bash_root):
        print("  [drift] hook wiring in settings.json != hooks/hooks.json — re-run bootstrap")
        fails.append("hook-wiring")
    else:
        print("  [ok] hook wiring matches hooks/hooks.json")

    # 2. sync drift
    print("\n2. Sync (repo -> ~/.claude)")
    # One entry per thing bootstrap copies. Skills were added to bootstrap in
    # v4.3.5 and must be listed here too, or an edited SKILL.md that was never
    # re-bootstrapped stays invisible to the drift check.
    pairs = [
        (REPO / "commands", CLAUDE_DIR / "commands" / "ecosystem-brain", "commands", "*.md"),
        (REPO / "agents", CLAUDE_DIR / "agents", "agents", "*.md"),
        (REPO / "skills", CLAUDE_DIR / "skills", "skills", "*/SKILL.md"),
    ]
    drift = [
        p
        for repo_dir, live_dir, label, pattern in pairs
        for p in drift_in(repo_dir, live_dir, bash_root, label, pattern)
    ]
    if drift:
        for name, why in drift:
            print(f"  [drift] {name} — {why}")
        fails.append("drift")
    else:
        print("  [ok] commands + agents + skills in sync")

    # 3. orphans (live -> repo, the direction the sync check never looked)
    print("\n3. Orphans (live files the repo no longer ships)")
    stale, recorded = orphans_live()
    if stale is None:
        # Not a pass. Every install predating the manifest lands here, and
        # printing [ok] for a check that could not run is how a green report
        # stops meaning anything.
        print("  [--] no install manifest yet — re-run bootstrap to enable this check")
    elif stale:
        for rel in stale:
            print(f"  [orphan] {rel} — deleted from the repo, still live")
        fails.append("orphans")
    else:
        print(f"  [ok] nothing orphaned ({recorded} installed path(s) tracked)")

    # 4. prerequisites (advisory — never fails the run)
    bs.check_prereqs()

    print()
    if fails:
        print(f"[!] doctor found issues: {', '.join(fails)}")
        print("    fix: uv run --no-project python scripts/bootstrap.py")
        return 1
    print("[ok] healthy — live config in sync with the repo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
