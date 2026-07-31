#!/usr/bin/env python3
"""Install ecosystem-brain into Claude Code on this machine.

Makes the repo portable: run this after `git clone` on any PC and it wires up
~/.claude/ with the correct absolute paths derived from THIS clone's location —
no hardcoded D:\\claude-projects assumptions.

What it does:
  1. Detects the repo root (this script's location) and its bash-form path.
  2. Merges hooks + permissions into ~/.claude/settings.json (keeps your MCPs).
  3. Copies commands  -> ~/.claude/commands/ecosystem-brain/
  4. Copies agents    -> ~/.claude/agents/
  5. Seeds .env from .env.example if missing.
  6. Reports missing prerequisites (uv, gitleaks, ollama, node, gh).

Usage:
    uv run python scripts/bootstrap.py            # apply
    uv run python scripts/bootstrap.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).resolve().parent.parent
# Drive-letter <-> Git-Bash-mount translation only applies on Windows. On
# Linux/macOS paths are already posix, so the translations below are no-ops.
WINDOWS = os.name == "nt"
# Overridable for testing (point at a temp dir to avoid touching the real config).
CLAUDE_DIR = Path(os.environ.get("ECOSYSTEM_CLAUDE_DIR") or (Path.home() / ".claude"))
SETTINGS = CLAUDE_DIR / "settings.json"
# Single source of truth for hook wiring. bootstrap reads it and rewrites the
# canonical path to this clone's real path — no second copy to drift out of sync.
HOOKS_TEMPLATE = REPO_ROOT / "hooks" / "hooks.json"

# The repo path as committed (the "authoring" location). Commands/agents hardcode
# this; bootstrap rewrites it to THIS clone's real path so a clone at any location
# works. On the authoring machine these are no-ops.
CANON_BASH = "/d/claude-projects/ecosystem-brain"
CANON_WIN_FWD = "D:/claude-projects/ecosystem-brain"
CANON_WIN_BS = r"D:\claude-projects\ecosystem-brain"


def to_bash_path(p: Path) -> str:
    """Windows D:\\claude-projects\\eco -> /d/claude-projects/eco (Git Bash mount).

    On Linux/macOS a path is already its own bash form, so it passes through.
    """
    s = p.as_posix()  # D:/claude-projects/eco
    if WINDOWS and len(s) >= 2 and s[1] == ":":
        s = f"/{s[0].lower()}{s[2:]}"
    return s


def load_hooks(bash_root: str) -> dict:
    """Read hooks/hooks.json (the single source of truth) and rewrite the
    canonical repo path to this clone's real path. Drops the `_notes` doc key.

    Editing the hook wiring means editing one JSON file — no second hardcoded
    copy here to keep in sync.
    """
    raw = rewrite_paths(HOOKS_TEMPLATE.read_text(encoding="utf-8"), bash_root)
    return json.loads(raw).get("hooks", {})


PERMISSIONS = {
    "deny": [
        "Read(./.env)",
        "Read(./.env.*)",
        "Read(**/.env)",
        "Read(**/.env.*)",
        "Read(./.identity.local.env)",
    ],
    "ask": [
        "Bash(rm *)",
        "Bash(git push*)",
        "Bash(git reset --hard*)",
        "Bash(git clean*)",
    ],
}


def merge_settings(dry: bool, bash_root: str) -> None:
    existing: dict = {}
    if SETTINGS.exists():
        existing = json.loads(SETTINGS.read_text(encoding="utf-8"))
    existing["hooks"] = load_hooks(bash_root)
    existing["permissions"] = PERMISSIONS
    if dry:
        print(f"  [dry] would write hooks+permissions to {SETTINGS}")
        return
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(
        json.dumps(existing, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"  [ok] merged hooks+permissions -> {SETTINGS} (other keys preserved)")


def rewrite_paths(text: str, bash_root: str) -> str:
    """Rewrite the committed canonical repo path to THIS clone's real path.

    Makes commands/agents portable: a clone at any location works after bootstrap.
    Handles the bash mount form, both Windows forms, and the legacy
    ${CLAUDE_PLUGIN_ROOT} token. No-op on the authoring machine.
    """
    return (
        text.replace(CANON_BASH, bash_root)
        .replace(CANON_WIN_FWD, REPO_ROOT.as_posix())
        .replace(CANON_WIN_BS, str(REPO_ROOT))
        .replace("${CLAUDE_PLUGIN_ROOT}", bash_root)
    )


def copy_tree(
    src: Path, dst: Path, dry: bool, label: str, bash_root: str, rewrite: bool = False
) -> None:
    if not src.is_dir():
        print(f"  [skip] no {label} dir at {src}")
        return
    files = sorted(src.glob("*.md"))
    if dry:
        tag = " (paths rewritten)" if rewrite else ""
        print(f"  [dry] would copy {len(files)} {label} -> {dst}{tag}")
        return
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        if rewrite:
            content = rewrite_paths(f.read_text(encoding="utf-8"), bash_root)
            (dst / f.name).write_text(content, encoding="utf-8", newline="\n")
        else:
            shutil.copy2(f, dst / f.name)
    suffix = " (paths rewritten to this clone)" if rewrite else ""
    print(f"  [ok] copied {len(files)} {label} -> {dst}{suffix}")


def copy_skills(src: Path, dst: Path, dry: bool, bash_root: str) -> None:
    """Copy skills/<name>/SKILL.md -> <claude-dir>/skills/<name>/SKILL.md.

    Skills sit one level deeper than commands/agents, so copy_tree's flat
    `*.md` glob never matched them — which is why the bundled memory and
    secrets skills were shipped but never loaded by Claude Code.

    Only SKILL.md is copied. It invokes its helper scripts by absolute path
    (rewritten here to this clone), so the scripts stay in the repo as the
    single copy and cannot drift from a duplicate under ~/.claude.
    """
    if not src.is_dir():
        print(f"  [skip] no skills dir at {src}")
        return
    manifests = sorted(src.glob("*/SKILL.md"))
    if dry:
        print(f"  [dry] would copy {len(manifests)} skills -> {dst} (paths rewritten)")
        return
    for m in manifests:
        target = dst / m.parent.name
        target.mkdir(parents=True, exist_ok=True)
        content = rewrite_paths(m.read_text(encoding="utf-8"), bash_root)
        (target / "SKILL.md").write_text(content, encoding="utf-8", newline="\n")
    print(
        f"  [ok] copied {len(manifests)} skills -> {dst} (paths rewritten to this clone)"
    )


def seed_env(dry: bool) -> None:
    env, example = REPO_ROOT / ".env", REPO_ROOT / ".env.example"
    if env.exists():
        print("  [ok] .env already present")
        return
    if not example.exists():
        print("  [skip] no .env.example to seed from")
        return
    if dry:
        print("  [dry] would seed .env from .env.example")
        return
    shutil.copy2(example, env)
    print("  [ok] seeded .env from .env.example (fill in real values)")


def check_prereqs() -> None:
    print("\nprerequisites:")
    for tool in ("uv", "git", "node", "gh", "gitleaks", "ruff", "ollama"):
        found = shutil.which(tool)
        mark = "ok " if found else "MISS"
        print(
            f"  [{mark}] {tool}"
            + (f"  ({found})" if found else "  — install for full functionality")
        )


def _normalize(raw: str) -> Path:
    """Git Bash mount /d/foo -> D:/foo on Windows. Posix paths pass through.

    The drive translation is Windows-only: on Linux/macOS a path like /d/foo is
    a genuine posix path, not a mounted drive, so it must not be rewritten.
    """
    if WINDOWS and len(raw) >= 3 and raw[0] == "/" and raw[2] == "/" and raw[1].isalpha():
        raw = f"{raw[1].upper()}:/{raw[3:]}"
    return Path(raw)


def _hook_script_paths(hooks: dict):
    """Yield the .sh/.py filesystem paths referenced by hook command strings."""
    for event in hooks.values():
        for group in event:
            for hook in group.get("hooks", []):
                for tok in (hook.get("command") or "").split():
                    if tok.endswith((".sh", ".py")):
                        yield tok


def verify_live() -> int:
    """Check that the live settings.json hook scripts actually exist on disk.

    Catches the classic breakage: the repo was renamed or moved but bootstrap
    was never re-run, so every hook silently points at a dead path.
    """
    print("verify: live hook paths resolve")
    if not SETTINGS.exists():
        print(f"  [skip] no live settings at {SETTINGS} — run bootstrap first")
        return 0
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8")).get("hooks", {})
    stale = sorted({t for t in _hook_script_paths(hooks) if not _normalize(t).exists()})
    if stale:
        print(f"  [STALE] {len(stale)} hook script(s) point at non-existent paths:")
        for t in stale:
            print(f"    - {t}")
        print("  fix: re-run  uv run --no-project python scripts/bootstrap.py")
        return 1
    print("  [ok] all live hook scripts resolve")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--verify",
        action="store_true",
        help="check the live config's hook paths resolve, then exit",
    )
    args = ap.parse_args(argv)

    if args.verify:
        return verify_live()

    bash_root = to_bash_path(REPO_ROOT)
    print("ecosystem-brain bootstrap")
    print(f"  repo root : {REPO_ROOT}")
    print(f"  bash form : {bash_root}")
    print(f"  claude dir: {CLAUDE_DIR}\n")

    merge_settings(args.dry_run, bash_root)
    copy_tree(
        REPO_ROOT / "commands",
        CLAUDE_DIR / "commands" / "ecosystem-brain",
        args.dry_run,
        "commands",
        bash_root,
        rewrite=True,
    )
    copy_tree(
        REPO_ROOT / "agents",
        CLAUDE_DIR / "agents",
        args.dry_run,
        "agents",
        bash_root,
        rewrite=True,
    )
    copy_skills(REPO_ROOT / "skills", CLAUDE_DIR / "skills", args.dry_run, bash_root)
    seed_env(args.dry_run)
    check_prereqs()

    print(
        "\ndone."
        + (
            "  (dry run — nothing written)"
            if args.dry_run
            else "  Restart Claude Code to load hooks/commands."
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
