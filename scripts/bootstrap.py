#!/usr/bin/env python3
"""Install ecosystem-brain into Claude Code on this machine.

Makes the repo portable: run this after `git clone` on any PC and it wires up
~/.claude/ with the correct absolute paths derived from THIS clone's location —
no hardcoded D:\\Claude_projects assumptions.

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
# Overridable for testing (point at a temp dir to avoid touching the real config).
CLAUDE_DIR = Path(os.environ.get("ECOSYSTEM_CLAUDE_DIR") or (Path.home() / ".claude"))
SETTINGS = CLAUDE_DIR / "settings.json"

# The repo path as committed (the "authoring" location). Commands/agents hardcode
# this; bootstrap rewrites it to THIS clone's real path so a clone at any location
# works. On the authoring machine these are no-ops.
CANON_BASH = "/d/Claude_projects/ecosystem-brain"
CANON_WIN_FWD = "D:/Claude_projects/ecosystem-brain"
CANON_WIN_BS = r"D:\Claude_projects\ecosystem-brain"


def to_bash_path(p: Path) -> str:
    """D:\\Claude_projects\\eco  ->  /d/Claude_projects/eco (Git Bash mount form)."""
    s = p.as_posix()  # D:/Claude_projects/eco
    if len(s) >= 2 and s[1] == ":":
        s = f"/{s[0].lower()}{s[2:]}"
    return s


def build_hooks(bash_root: str) -> dict:
    h = f"bash {bash_root}/hooks/scripts"
    return {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "if": "Bash(git commit*)",
                        "command": f"{h}/guard-secrets.sh",
                    },
                    {
                        "type": "command",
                        "if": "Bash(git push*)",
                        "command": f"{h}/guard-secrets.sh",
                    },
                    {
                        "type": "command",
                        "if": "Bash(git push*)",
                        "command": f"{h}/guard-destructive.sh",
                    },
                    {"type": "command", "if": "Bash(rm *)", "command": f"{h}/guard-destructive.sh"},
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Write",
                "hooks": [
                    {"type": "command", "if": "Write(*.py)", "command": f"{h}/fmt-python.sh"}
                ],
            }
        ],
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"uv run --no-project python {bash_root}/hooks/scripts/suggest-agents.py",
                    }
                ]
            }
        ],
        "SessionEnd": [{"hooks": [{"type": "command", "command": f"{h}/log-session.sh"}]}],
    }


PERMISSIONS = {
    "deny": [
        "Read(./.env)",
        "Read(./.env.*)",
        "Read(**/.env)",
        "Read(**/.env.*)",
        "Read(./.identity.local.env)",
    ],
    "ask": ["Bash(rm *)", "Bash(git push*)", "Bash(git reset --hard*)", "Bash(git clean*)"],
}


def merge_settings(dry: bool, bash_root: str) -> None:
    existing: dict = {}
    if SETTINGS.exists():
        existing = json.loads(SETTINGS.read_text(encoding="utf-8"))
    existing["hooks"] = build_hooks(bash_root)
    existing["permissions"] = PERMISSIONS
    if dry:
        print(f"  [dry] would write hooks+permissions to {SETTINGS}")
        return
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"  [ok] merged hooks+permissions -> {SETTINGS} (other keys preserved)")


def rewrite_paths(text: str, bash_root: str) -> str:
    """Rewrite the committed canonical repo path to THIS clone's real path.

    Makes commands/agents portable: a clone at any location works after bootstrap.
    Handles the bash mount form, both Windows forms, and the legacy
    ${CLAUDE_PLUGIN_ROOT} token. No-op on the authoring machine.
    """
    return (text
            .replace(CANON_BASH, bash_root)
            .replace(CANON_WIN_FWD, REPO_ROOT.as_posix())
            .replace(CANON_WIN_BS, str(REPO_ROOT))
            .replace("${CLAUDE_PLUGIN_ROOT}", bash_root))


def copy_tree(src: Path, dst: Path, dry: bool, label: str, bash_root: str,
              rewrite: bool = False) -> None:
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
            (dst / f.name).write_text(content, encoding="utf-8")
        else:
            shutil.copy2(f, dst / f.name)
    suffix = " (paths rewritten to this clone)" if rewrite else ""
    print(f"  [ok] copied {len(files)} {label} -> {dst}{suffix}")


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

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
    copy_tree(REPO_ROOT / "agents", CLAUDE_DIR / "agents", args.dry_run,
              "agents", bash_root, rewrite=True)
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
