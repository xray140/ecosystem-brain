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
  5. Copies skills    -> ~/.claude/skills/<name>/SKILL.md
  6. Removes what it installed on a previous run and no longer ships, then
     records the current set in ~/.claude/.ecosystem-brain-installed.json.
     Nothing outside that manifest is ever touched.
  7. Seeds .env from .env.example if missing.
  8. Reports missing prerequisites (uv, gitleaks, ollama, node, gh).

Usage:
    uv run python scripts/bootstrap.py            # apply
    uv run python scripts/bootstrap.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from datetime import UTC, datetime
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

# Committed files refer to the repo by this token, never by a real path.
# bootstrap expands it to THIS clone's location, so a clone anywhere works.
#
# It used to be a literal path — the machine it was authored on. That worked
# only because this rewrite silently repaired it, and it rotted exactly as you
# would expect: the authoring machine moved, and 58 references across 16 files
# pointed at a directory that existed nowhere. A token cannot rot, because it is
# never a valid path to begin with, and selfcheck fails the build if a literal
# one reappears.
TOKEN = "{{ECOSYSTEM_ROOT}}"  # noqa: S105 — a path placeholder, not a credential

# Legacy forms, still rewritten so a clone carrying pre-4.3.7 files (or an
# already-installed ~/.claude copy) keeps working through the transition.
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


# Deny is enumerated rather than a `.env.*` catch-all, because the catch-all also
# matched `.env.example` — the committed, placeholder-only template that every
# scaffolded project ships and that `project_doctor` diffs `.env` against. Denying
# it made the one file meant to be edited the one file that could not be.
#
# `.gitignore` expresses this as `.env.*` then `!.env.example`. Permission globs
# have no negation and `deny` outranks `allow`, so the exception cannot be written
# that way here — the pattern itself has to stop matching.
#
# The cost is that this is now a list to maintain: a future `.env.<name>` holding
# secrets is readable unless it is added below. Kept aligned with AGENTS.md, which
# states secrets live in `.env` / `.identity.local.env` only — so this enumerates
# the documented policy instead of over-reaching past it. Widen it here, not in
# the live settings, or the next bootstrap run reverts the change.
PERMISSIONS = {
    "deny": [
        "Read(./.env)",
        "Read(**/.env)",
        "Read(./.env.local)",
        "Read(**/.env.local)",
        "Read(./.env.*.local)",
        "Read(**/.env.*.local)",
        "Read(./.identity.local.env)",
        "Read(**/*.local.env)",
    ],
    # These patterns match from the START of the command, so a rule written for
    # `git push` does not cover `git -C <path> push` — the form used to act on a
    # sibling repo. That gap did not make the wider action safer: it fell through
    # to the classifier and hard-failed, where the narrower one merely prompted.
    # Both spellings are listed, and both are `ask` rather than `allow`, so the
    # form that can target any repo on disk is never the unprompted one.
    "ask": [
        "Bash(rm *)",
        "Bash(git push*)",
        "Bash(git -C * push*)",
        "Bash(git reset --hard*)",
        "Bash(git -C * reset --hard*)",
        "Bash(git clean*)",
        "Bash(git -C * clean*)",
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
    """Expand {{ECOSYSTEM_ROOT}} to THIS clone's real path.

    Makes commands/agents/skills/hooks portable: a clone at any location works
    after bootstrap. The legacy literal paths and ${CLAUDE_PLUGIN_ROOT} are
    still handled so an older clone (or an already-installed ~/.claude copy)
    migrates cleanly on the next run.
    """
    return (
        text.replace(TOKEN, bash_root)
        .replace(CANON_BASH, bash_root)
        .replace(CANON_WIN_FWD, REPO_ROOT.as_posix())
        .replace(CANON_WIN_BS, str(REPO_ROOT))
        .replace("${CLAUDE_PLUGIN_ROOT}", bash_root)
    )


# Everything this repo has ever installed under ~/.claude, so a file the repo
# later DELETES can be found and removed. Without it the sync was one-way:
# bootstrap copied repo -> live and never looked the other way, so `doctor`
# reported "healthy — live config in sync" on 2026-08-21 while two agents it
# had just deleted were still loading into every session. A removed agent that
# keeps running is worse than one that never shipped.
INSTALL_MANIFEST = CLAUDE_DIR / ".ecosystem-brain-installed.json"


def _live_rel(path: Path) -> str:
    """A live path as recorded in the manifest: relative to CLAUDE_DIR, posix."""
    try:
        return path.relative_to(CLAUDE_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def read_manifest() -> list[str]:
    """Paths this repo installed on the last run — [] when there is no manifest.

    An empty list is "unknown", not "nothing installed": every install predating
    the manifest reads this way, and the callers must not treat it as proof that
    nothing is orphaned.
    """
    if not INSTALL_MANIFEST.is_file():
        return []
    try:
        data = json.loads(INSTALL_MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    paths = data.get("paths", [])
    return [p for p in paths if isinstance(p, str)]


def prune_orphans(installed: list[str], dry: bool) -> list[str]:
    """Delete live files this repo installed and no longer ships.

    Scoped hard to the previous manifest: a file is removed only when THIS repo
    is on record as having written it and the current run did not. Anything else
    under ~/.claude — the user's own agents, another plugin's commands — is none
    of our business and is never touched.
    """
    stale = [p for p in read_manifest() if p not in set(installed)]
    removed: list[str] = []
    for rel in sorted(stale):
        target = CLAUDE_DIR / rel
        if not target.is_file():
            continue
        removed.append(rel)
        if dry:
            continue
        target.unlink()
        # A skill is a directory; drop it once its SKILL.md is gone.
        parent = target.parent
        if parent != CLAUDE_DIR and not any(parent.iterdir()):
            parent.rmdir()
    if removed:
        verb = "would remove" if dry else "removed"
        print(f"  [ok] {verb} {len(removed)} file(s) the repo no longer ships:")
        for rel in removed:
            print(f"         {rel}")
    return removed


def record_install(installed: list[str], dry: bool) -> None:
    """Write the manifest. Always last, so it records what actually happened."""
    if dry:
        print(f"  [dry] would record {len(installed)} installed path(s)")
        return
    INSTALL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    INSTALL_MANIFEST.write_text(
        json.dumps(
            {
                "generated": datetime.now(UTC).isoformat(),
                "repo": str(REPO_ROOT),
                "paths": sorted(installed),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"  [ok] recorded {len(installed)} installed path(s) -> {INSTALL_MANIFEST.name}")


def copy_tree(
    src: Path, dst: Path, dry: bool, label: str, bash_root: str, rewrite: bool = False
) -> list[str]:
    """Copy, and return the live paths written, relative to CLAUDE_DIR.

    The return value feeds the install manifest — see `record_install`.
    Without it nothing knows which files under ~/.claude this repo put
    there, and a file the repo later deletes stays live for ever.
    """
    if not src.is_dir():
        print(f"  [skip] no {label} dir at {src}")
        return []
    files = sorted(src.glob("*.md"))
    if dry:
        tag = " (paths rewritten)" if rewrite else ""
        print(f"  [dry] would copy {len(files)} {label} -> {dst}{tag}")
        return [_live_rel(dst / f.name) for f in files]
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        if rewrite:
            content = rewrite_paths(f.read_text(encoding="utf-8"), bash_root)
            (dst / f.name).write_text(content, encoding="utf-8", newline="\n")
        else:
            shutil.copy2(f, dst / f.name)
    suffix = " (paths rewritten to this clone)" if rewrite else ""
    print(f"  [ok] copied {len(files)} {label} -> {dst}{suffix}")
    return [_live_rel(dst / f.name) for f in files]


def copy_skills(src: Path, dst: Path, dry: bool, bash_root: str) -> list[str]:
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
        return []
    manifests = sorted(src.glob("*/SKILL.md"))
    written = [_live_rel(dst / mf.parent.name / "SKILL.md") for mf in manifests]
    if dry:
        print(f"  [dry] would copy {len(manifests)} skills -> {dst} (paths rewritten)")
        return written
    for m in manifests:
        target = dst / m.parent.name
        target.mkdir(parents=True, exist_ok=True)
        content = rewrite_paths(m.read_text(encoding="utf-8"), bash_root)
        (target / "SKILL.md").write_text(content, encoding="utf-8", newline="\n")
    print(
        f"  [ok] copied {len(manifests)} skills -> {dst} (paths rewritten to this clone)"
    )
    return written


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


def write_machine_note(dry: bool) -> None:
    """Record which machine this is, as a vault note.

    The vault is shared across machines but nearly everything in it is
    machine-specific — a project card's drive letter, an agent's usage counts,
    the scheduled tasks. Writing this at install time means a fresh clone knows
    where it is from the first session rather than inferring it later.

    Never fatal: a profile is a convenience, and failing to write one must not
    fail an install.
    """
    if dry:
        print("  [dry] would write the machine note")
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import profile_machine

        profile_machine.main([])
    except Exception as e:  # a profile is never worth failing an install over
        print(f"  [skip] machine note: {e}")


#: Absent, something the ecosystem does every day stops working.
REQUIRED_TOOLS = ("uv", "git", "node", "gh", "gitleaks", "ruff")
#: Absent, one capability quietly degrades and everything else is unaffected.
#: `ollama` powers memory-search's embeddings; without it search falls back to
#: the offline hash embedder rather than failing. Listing it as a prerequisite
#: printed `MISS ... install for full functionality` on machines that had made a
#: deliberate choice not to run a local model server.
OPTIONAL_TOOLS = {"ollama": "memory-search embeddings; falls back to offline"}


def check_prereqs() -> None:
    print("\nprerequisites:")
    for tool in REQUIRED_TOOLS:
        found = shutil.which(tool)
        mark = "ok " if found else "MISS"
        print(
            f"  [{mark}] {tool}"
            + (f"  ({found})" if found else "  — install for full functionality")
        )
    for tool, why in OPTIONAL_TOOLS.items():
        found = shutil.which(tool)
        mark = "ok " if found else "--  "
        print(f"  [{mark}] {tool} (optional)" + (f"  ({found})" if found else f"  — {why}"))


def _normalize(raw: str) -> Path:
    """Git Bash mount /d/foo -> D:/foo on Windows. Posix paths pass through.

    The drive translation is Windows-only: on Linux/macOS a path like /d/foo is
    a genuine posix path, not a mounted drive, so it must not be rewritten.
    """
    if WINDOWS and len(raw) >= 3 and raw[0] == "/" and raw[2] == "/" and raw[1].isalpha():
        raw = f"{raw[1].upper()}:/{raw[3:]}"
    return Path(raw)


def _hook_script_paths(hooks: dict):
    """Yield the .sh/.py filesystem paths referenced by hook command strings.

    Split with shlex, not str.split: the paths are double-quoted in hooks.json
    precisely because a clone root on Windows routinely contains a space
    (C:/Users/First Last/...). Splitting on whitespace tears such a path in half
    and reports the fragment as a stale hook.
    """
    for event in hooks.values():
        for group in event:
            for hook in group.get("hooks", []):
                cmd = hook.get("command") or ""
                try:
                    toks = shlex.split(cmd, posix=True)
                except ValueError:
                    toks = cmd.split()  # unbalanced quotes: degrade, don't crash
                for tok in toks:
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
    installed: list[str] = []
    installed += copy_tree(
        REPO_ROOT / "commands",
        CLAUDE_DIR / "commands" / "ecosystem-brain",
        args.dry_run,
        "commands",
        bash_root,
        rewrite=True,
    )
    installed += copy_tree(
        REPO_ROOT / "agents",
        CLAUDE_DIR / "agents",
        args.dry_run,
        "agents",
        bash_root,
        rewrite=True,
    )
    installed += copy_skills(
        REPO_ROOT / "skills", CLAUDE_DIR / "skills", args.dry_run, bash_root
    )
    prune_orphans(installed, args.dry_run)
    record_install(installed, args.dry_run)
    seed_env(args.dry_run)
    write_machine_note(args.dry_run)
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
