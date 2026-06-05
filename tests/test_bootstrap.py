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
