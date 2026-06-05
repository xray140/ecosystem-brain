#!/usr/bin/env python3
"""Health + drift doctor for the ecosystem-brain install.

Answers the question `bootstrap --verify` only half-answered: "is my live Claude
Code config actually in sync with this repo?" Checks:

  1. Hooks live   — every hook script path in settings.json resolves on disk.
  2. Sync drift   — each repo command/agent matches its copy in ~/.claude, after
                    the same path-rewrite bootstrap applies on copy (so a clone at
                    a different path isn't flagged — only real edits are).
  3. Prerequisites — uv/git/node/gh/gitleaks/ruff/ollama on PATH (advisory).

Exit non-zero if hooks are broken or anything has drifted. Fix drift by re-running
bootstrap.

Usage:
    uv run --no-project python scripts/doctor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap as bs  # noqa: E402 — reuse REPO_ROOT, CLAUDE_DIR, rewrite_paths, verify_live

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO = bs.REPO_ROOT
CLAUDE_DIR = bs.CLAUDE_DIR


def drift_in(
    repo_dir: Path, live_dir: Path, bash_root: str, label: str
) -> list[tuple[str, str]]:
    """(file, reason) pairs where the live copy differs from the repo source.

    Compares against the rewritten repo content (the exact bytes bootstrap would
    write), so the intended per-clone path substitution is not mistaken for drift.
    """
    problems: list[tuple[str, str]] = []
    if not repo_dir.is_dir():
        return problems
    for f in sorted(repo_dir.glob("*.md")):
        live = live_dir / f.name
        expected = bs.rewrite_paths(f.read_text(encoding="utf-8"), bash_root)
        if not live.exists():
            problems.append((f"{label}/{f.name}", "missing in ~/.claude"))
        elif live.read_text(encoding="utf-8") != expected:
            problems.append((f"{label}/{f.name}", "drifted — re-run bootstrap"))
    return problems


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

    # 2. sync drift
    print("\n2. Sync (repo -> ~/.claude)")
    pairs = [
        (REPO / "commands", CLAUDE_DIR / "commands" / "ecosystem-brain", "commands"),
        (REPO / "agents", CLAUDE_DIR / "agents", "agents"),
    ]
    drift = [
        p
        for repo_dir, live_dir, label in pairs
        for p in drift_in(repo_dir, live_dir, bash_root, label)
    ]
    if drift:
        for name, why in drift:
            print(f"  [drift] {name} — {why}")
        fails.append("drift")
    else:
        print("  [ok] commands + agents in sync")

    # 3. prerequisites (advisory — never fails the run)
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
