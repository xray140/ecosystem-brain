"""Tests for the destructive-command guard.

Two failure modes matter equally. A guard that misses `rm -r -f /` gives false
assurance; a guard that refuses `rm -rf ~/.claude/skills/one-thing` gets worked
around, and then protects nothing. Both directions are pinned here.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / "hooks" / "scripts"
spec = importlib.util.spec_from_file_location("guard_destructive", HOOKS / "guard_destructive.py")
REPO = HOOKS.parent.parent
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)


# --- must block -----------------------------------------------------------
@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /",
        "rm -fr /",
        "rm  -rf  /",  # collapsed whitespace
        "rm -r -f /",  # split flags
        "rm --recursive --force /",  # long flags
        "rm -rf ~",
        "rm -rf $HOME",
        "rm -rf /etc",
        "rm -rf /usr",
        "rm -rf /home",
        "rm -rf /c/Windows",
        "rm -rf '/'",  # quoted
        'rm -rf "/etc"',
        "rm -rf /etc/",  # trailing slash
        "rm -rf *",
        "echo hi && rm -rf /",  # chained after something innocuous
        "cd /tmp; rm -rf /",
    ],
)
def test_catastrophic_deletes_blocked(cmd):
    assert gd.check(cmd) is not None, f"should block: {cmd}"


@pytest.mark.parametrize(
    "cmd",
    [
        "git push --force origin main",
        "git push -f origin main",
        "git push --force origin master",
        "git push origin +main",  # forced via refspec, no --force flag
        "git push origin +master:master",
    ],
)
def test_force_push_to_protected_branch_blocked(cmd):
    assert gd.check(cmd) is not None, f"should block: {cmd}"


# --- must NOT block -------------------------------------------------------
@pytest.mark.parametrize(
    "cmd",
    [
        # The false positive that sent this rewrite: a specific path under home.
        "rm -rf ~/.claude/skills/pdf-tools",
        "rm -rf /etc/myapp/cache",
        "rm -rf /home/me/project/build",
        "rm -rf ./node_modules",
        "rm -rf build dist",
        "rm -rf /tmp/eco-smoke-abc123",
        "rm -f somefile.txt",  # not recursive
        "rm somefile.txt",
        "rm -rf /c/Users/me/project/.venv",
        "git push origin feature-branch",
        "git push --force origin my-feature",  # force is fine off protected branches
        "git push --force-with-lease origin main",  # the safe form
        "git status",
        "ls -la /",
        "grep -r pattern /etc",
        "",
    ],
)
def test_ordinary_work_allowed(cmd):
    assert gd.check(cmd) is None, f"should allow: {cmd}"


# --- parsing details ------------------------------------------------------
def test_flags_normalize_across_spellings():
    assert gd.rm_targets(["rm", "-rf", "/x"]) == ({"r", "f"}, {"/x"})
    assert gd.rm_targets(["rm", "-r", "-f", "/x"]) == ({"r", "f"}, {"/x"})
    assert gd.rm_targets(["rm", "--recursive", "--force", "/x"]) == ({"r", "f"}, {"/x"})


def test_non_rm_command_yields_no_targets():
    assert gd.rm_targets(["ls", "-la", "/"]) == (set(), set())


def test_statements_splits_on_every_separator():
    assert len(gd.statements("a && b || c ; d | e")) == 5


def test_unbalanced_quotes_do_not_crash():
    """shlex raises on unbalanced quotes; the fallback split must still parse."""
    assert gd.check('rm -rf "/unclosed') is None  # /unclosed is not catastrophic
    assert gd.check('rm -rf "/') is not None  # but the root still is


def test_trailing_slash_normalizes_but_root_survives():
    assert gd._normalize_target("/etc/") == "/etc"
    assert gd._normalize_target("/") == "/"


# --- the entry point, which hooks.json actually invokes --------------------
# Every test above calls check()/rm_targets()/statements() directly. hooks.json
# wires the PROCESS:
#
#   {"if": "Bash(rm *)", "command": "uv run ... hooks/scripts/guard_destructive.py"}
#
# so everything between stdin and the exit code — reading tool_input.command,
# emitting the block decision, returning 2 — was the part Claude Code depends on
# and the one part with no assertions. Measured on 2026-09-04 by planting two
# mutants and running the whole suite:
#
#   [SURVIVED] block becomes allow                        889 passed, 2 skipped
#   [SURVIVED] read a key the payload never has           889 passed, 2 skipped
#
# `rm -rf /` could stop being refused with every gate green.


def _run_main(monkeypatch, payload_text):
    monkeypatch.setattr(gd.sys, "stdin", io.StringIO(payload_text))
    return gd.main()


def test_a_destructive_command_is_blocked_with_exit_2(monkeypatch, capsys):
    """2 is the contract: Claude Code treats it as "deny and tell the model why".
    0 would let the command through."""
    code = _run_main(monkeypatch, json.dumps({"tool_input": {"command": "rm -rf /"}}))
    assert code == 2
    decision = json.loads(capsys.readouterr().out)
    assert decision["decision"] == "block"
    assert decision["reason"], "a block with no reason teaches the model nothing"


def test_an_ordinary_command_is_allowed_silently(monkeypatch, capsys):
    code = _run_main(monkeypatch, json.dumps({"tool_input": {"command": "rm -rf ./build"}}))
    assert code == 0
    assert capsys.readouterr().out == "", "a non-block must not emit a decision"


def test_the_command_is_read_from_tool_input(monkeypatch, capsys):
    """Pinning the exact key. Reading `toolInput` instead — a plausible typo, and
    one of the two mutants that survived — means the guard inspects an empty
    string forever and blocks nothing, while every unit test on check() passes."""
    code = _run_main(monkeypatch, json.dumps({"tool_input": {"command": "rm -rf ~"}}))
    assert code == 2, "the payload key the harness sends is tool_input.command"
    assert "block" in capsys.readouterr().out


def test_unparseable_stdin_does_not_block(monkeypatch, capsys):
    """Deliberate: garbage on stdin is not grounds to refuse the user's command.
    Asserted so the choice stays a choice rather than becoming an accident."""
    assert _run_main(monkeypatch, "not json at all") == 0
    assert capsys.readouterr().out == ""


def test_a_payload_without_a_command_does_not_block(monkeypatch):
    assert _run_main(monkeypatch, json.dumps({"tool_input": {}})) == 0
    assert _run_main(monkeypatch, json.dumps({})) == 0
    assert _run_main(monkeypatch, json.dumps({"tool_input": None})) == 0


def test_the_force_push_form_is_blocked_through_the_entry_point(monkeypatch, capsys):
    """One end-to-end case per guarded family, so the wiring is proved for each
    rather than for `rm` alone."""
    code = _run_main(
        monkeypatch, json.dumps({"tool_input": {"command": "git push --force origin main"}})
    )
    assert code == 2
    assert json.loads(capsys.readouterr().out)["decision"] == "block"


def test_the_hook_config_still_points_at_this_script():
    """These tests prove the function. This asserts the function is still what
    hooks.json runs — a rename would leave the tests green and the guard unwired."""
    wiring = (REPO / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "guard_destructive.py" in wiring
    assert wiring.count("guard_destructive.py") >= 2, "rm and git push must both be wired"
