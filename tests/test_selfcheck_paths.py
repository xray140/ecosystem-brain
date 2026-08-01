"""Tests for the hardcoded-path check and the {{ECOSYSTEM_ROOT}} substitution.

Together these are what keeps the repo portable. The token is only useful if
bootstrap expands it *and* nothing is allowed to reintroduce a literal path —
the previous scheme had the expansion but not the check, so 58 references
across 16 files rotted into pointing at a directory that existed nowhere,
invisibly, because the expansion kept repairing them on the way out.
"""

from __future__ import annotations

import re

import selfcheck as sc

import bootstrap as bs


# --- the check catches what it must ---------------------------------------
def _flagged(line: str) -> bool:
    return any(not sc._is_illustration(line, m) for m in sc.ABSOLUTE_PATH.finditer(line))


def test_git_bash_mount_path_is_flagged():
    assert _flagged("run `uv run python /d/claude-projects/ecosystem-brain/x.py`")
    assert _flagged("cd /c/Users/me/project")


def test_windows_drive_path_is_flagged():
    assert _flagged(r"- Project: `D:\claude-projects\my-tool`")
    assert _flagged("- Project: `C:/Users/me/thing`")


def test_bare_mount_without_trailing_slash_is_flagged():
    """`--dest-root /d/claude-projects` has no trailing slash; an earlier version
    of the pattern required one and let it through."""
    assert _flagged("scaffold.py --dest-root /d/claude-projects --git")


def test_the_token_itself_is_not_flagged():
    assert not _flagged("run `uv run python {{ECOSYSTEM_ROOT}}/scripts/x.py`")


def test_relative_paths_are_not_flagged():
    assert not _flagged("run `uv run python scripts/selfcheck.py`")
    assert not _flagged("see memory/decisions/agent-pinning.md")


def test_ellipsis_illustrations_are_not_flagged():
    """script-smith has to be able to teach that `/d/...` resolves to `D:\\d\\...`;
    that is the rule it exists to state."""
    assert not _flagged("never hardcode a `/d/...` string (it resolves to `D:\\d\\...`)")


def test_check_passes_on_the_real_repo(capsys):
    """The live assertion: no installable file currently hardcodes a path."""
    sc.fails.clear()
    sc.check_paths()
    assert sc.fails == [], sc.fails


# --- bootstrap expands the token ------------------------------------------
def test_token_expands_to_this_clone():
    out = bs.rewrite_paths("bash {{ECOSYSTEM_ROOT}}/hooks/scripts/x.sh", "/c/clone/eco")
    assert out == "bash /c/clone/eco/hooks/scripts/x.sh"


def test_every_occurrence_is_expanded():
    text = "{{ECOSYSTEM_ROOT}}/a and {{ECOSYSTEM_ROOT}}/b"
    assert bs.rewrite_paths(text, "/root") == "/root/a and /root/b"


def test_legacy_literal_path_still_migrates():
    """An older clone, or an already-installed ~/.claude copy, must keep working
    through the transition rather than breaking on the next bootstrap."""
    out = bs.rewrite_paths(f"bash {bs.CANON_BASH}/hooks/x.sh", "/c/clone/eco")
    assert out == "bash /c/clone/eco/hooks/x.sh"


def test_legacy_plugin_root_token_still_migrates():
    out = bs.rewrite_paths("bash ${CLAUDE_PLUGIN_ROOT}/x.sh", "/c/clone/eco")
    assert out == "bash /c/clone/eco/x.sh"


def test_rewrite_leaves_unrelated_text_alone():
    text = "no paths here, just prose about {{SOMETHING_ELSE}}"
    assert bs.rewrite_paths(text, "/root") == text


# --- the two halves agree -------------------------------------------------
def test_no_installable_file_survives_a_rewrite_unchanged_if_it_uses_the_token():
    """Every installable file that mentions the repo must do so via the token,
    so bootstrap's rewrite is what makes it correct on this machine."""
    token_users = 0
    for pattern in sc.INSTALLABLE:
        for p in sorted(sc.REPO.glob(pattern)):
            text = p.read_text(encoding="utf-8")
            if sc.TOKEN in text:
                token_users += 1
                rewritten = bs.rewrite_paths(text, "/c/clone/eco")
                assert sc.TOKEN not in rewritten, f"{p.name} kept an unexpanded token"
                assert "/c/clone/eco" in rewritten
    assert token_users > 10, "expected the commands and hooks to use the token"


def test_selfcheck_and_bootstrap_use_the_same_token():
    assert sc.TOKEN == bs.TOKEN


def test_pattern_is_anchored_against_inline_code_ticks():
    """The lookbehind must not let a backticked path through unnoticed."""
    assert re.search(sc.ABSOLUTE_PATH, "`/d/claude-projects/eco`")
