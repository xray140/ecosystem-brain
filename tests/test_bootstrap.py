"""Tests for the portability layer in bootstrap.py.

These lock in the path-rename fix: the canonical repo path must rewrite to any
clone location, and the --verify guard must read hook script paths correctly.
"""

from __future__ import annotations

from pathlib import Path

import bootstrap as b


# --- to_bash_path: Windows -> Git Bash mount form ------------------------
def test_to_bash_path_windows_drive():
    # Drive translation only happens on Windows; on Linux/macOS it passes through.
    result = b.to_bash_path(Path("D:/claude-projects/x"))
    if b.WINDOWS:
        assert result == "/d/claude-projects/x"
    else:
        assert result == "D:/claude-projects/x"


def test_to_bash_path_posix_unchanged_everywhere():
    # A real posix path is already its own bash form on every platform.
    assert b.to_bash_path(Path("/home/user/eco")) == "/home/user/eco"


# --- _normalize: Git Bash mount form -> Windows --------------------------
def test_normalize_mount_path_is_windows_only():
    result = b._normalize("/d/foo/bar")
    if b.WINDOWS:
        assert result == Path("D:/foo/bar")
    else:
        # On Linux/macOS, /d/foo is a genuine posix path — must not be rewritten.
        assert result == Path("/d/foo/bar")


def test_normalize_leaves_multichar_path():
    assert b._normalize("/usr/local/bin") == Path("/usr/local/bin")


# --- rewrite_paths: canonical -> this clone ------------------------------
def test_rewrite_replaces_canonical_bash_form():
    text = f"bash {b.CANON_BASH}/hooks/scripts/x.sh"
    out = b.rewrite_paths(text, "/c/clone/eco")
    assert out == "bash /c/clone/eco/hooks/scripts/x.sh"
    assert "claude-projects" not in out


def test_rewrite_replaces_plugin_root_token():
    out = b.rewrite_paths("${CLAUDE_PLUGIN_ROOT}/scripts/y.py", "/c/clone/eco")
    assert out == "/c/clone/eco/scripts/y.py"


def test_rewrite_is_noop_for_unrelated_text():
    text = "nothing to rewrite here"
    assert b.rewrite_paths(text, "/c/clone/eco") == text


# --- _hook_script_paths: extract .sh/.py from a hooks dict ---------------
def test_hook_script_paths_extraction():
    hooks = {
        "PreToolUse": [
            {
                "hooks": [
                    {"command": "bash /x/a.sh"},
                    {"command": "uv run python /x/b.py"},
                ]
            }
        ],
        "SessionEnd": [{"hooks": [{"command": "bash /x/c.sh"}]}],
    }
    assert set(b._hook_script_paths(hooks)) == {"/x/a.sh", "/x/b.py", "/x/c.sh"}


def test_hook_script_paths_ignores_non_scripts():
    hooks = {"X": [{"hooks": [{"command": "echo hello"}]}]}
    assert list(b._hook_script_paths(hooks)) == []


# --- load_hooks: read hooks.json (source of truth) + rewrite -------------
def test_load_hooks_returns_all_events_rewritten():
    hooks = b.load_hooks("/c/clone/eco")
    assert set(hooks) == {"PreToolUse", "PostToolUse", "SessionStart", "SessionEnd"}
    commands = [
        h["command"] for ev in hooks.values() for group in ev for h in group["hooks"]
    ]
    assert commands, "expected hook commands"
    assert all("claude-projects" not in c for c in commands), (
        "stale canonical path leaked"
    )
    assert all("/c/clone/eco/" in c for c in commands), "clone path not applied"


def test_load_hooks_drops_notes_key():
    # hooks.json carries a `_notes` doc key; load_hooks must not surface it.
    hooks = b.load_hooks("/c/clone/eco")
    assert "_notes" not in hooks


# --- copy_skills: nested SKILL.md, rewritten ----------------------------
def test_copy_skills_copies_nested_manifests_rewritten(tmp_path):
    # Skills live one level deeper than commands/agents; copy_tree's flat
    # *.md glob missed them entirely, so they were never loaded.
    src = tmp_path / "skills"
    (src / "memory").mkdir(parents=True)
    (src / "memory" / "SKILL.md").write_text(
        f"run {b.CANON_BASH}/skills/memory/x.py\n", encoding="utf-8"
    )
    (src / "memory" / "helper.py").write_text("# not copied\n", encoding="utf-8")
    dst = tmp_path / "out"

    b.copy_skills(src, dst, dry=False, bash_root="/c/clone/eco")

    out = dst / "memory" / "SKILL.md"
    assert out.is_file(), "SKILL.md must land under <dst>/<skill-name>/"
    assert out.read_text(encoding="utf-8") == "run /c/clone/eco/skills/memory/x.py\n"
    # Helper scripts stay in the repo — a second copy would drift.
    assert not (dst / "memory" / "helper.py").exists()


def test_copy_skills_writes_lf(tmp_path):
    src = tmp_path / "skills"
    (src / "s").mkdir(parents=True)
    (src / "s" / "SKILL.md").write_text("a\nb\n", encoding="utf-8", newline="\n")
    dst = tmp_path / "out"

    b.copy_skills(src, dst, dry=False, bash_root="/c/clone/eco")

    assert b"\r\n" not in (dst / "s" / "SKILL.md").read_bytes()


def test_copy_skills_dry_run_writes_nothing(tmp_path):
    src = tmp_path / "skills"
    (src / "s").mkdir(parents=True)
    (src / "s" / "SKILL.md").write_text("x\n", encoding="utf-8")
    dst = tmp_path / "out"

    b.copy_skills(src, dst, dry=True, bash_root="/c/clone/eco")

    assert not dst.exists()


def test_copy_skills_missing_dir_is_not_fatal(tmp_path):
    b.copy_skills(tmp_path / "nope", tmp_path / "out", dry=False, bash_root="/c/x")
    assert not (tmp_path / "out").exists()


def test_shipped_skills_carry_no_unrewritten_canonical_path(tmp_path):
    # Guards the actual bug: a SKILL.md whose paths bootstrap cannot rewrite.
    dst = tmp_path / "out"
    b.copy_skills(b.REPO_ROOT / "skills", dst, dry=False, bash_root="/c/clone/eco")
    installed = sorted(dst.glob("*/SKILL.md"))
    assert installed, "expected the repo to ship at least one skill"
    for f in installed:
        assert "claude-projects" not in f.read_text(encoding="utf-8"), (
            f"stale canonical path leaked into {f.name}"
        )
