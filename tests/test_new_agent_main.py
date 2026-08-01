"""Tests for new_agent.py's main() — the recruiter's CLI contract.

The property worth pinning: a composed agent is previewed by default and only
installed on an explicit --register, and it passes through the same scan gate as
any third-party agent. A recruiter that could install unscanned content would be
a hole straight through the supply chain it belongs to.
"""

from __future__ import annotations

import subprocess

import new_agent as na
import pytest

BASE = [
    "--name",
    "doc-linter",
    "--description",
    "Lints docs. Use proactively before a docs PR.",
    "--tools",
    "Read,Grep",
]


# --- convention gate ------------------------------------------------------
def test_bad_name_is_rejected_before_composing(capsys):
    assert na.main(["--name", "Bad Name", "--description", "Use it.", "--tools", "Read"]) == 1
    out = capsys.readouterr().out
    assert "kebab-case" in out
    assert "composed" not in out, "nothing should be composed after a convention failure"


def test_unknown_tool_is_rejected(capsys):
    argv = ["--name", "ok", "--description", "Use it.", "--tools", "Read,Nuke"]
    assert na.main(argv) == 1
    assert "unknown tool" in capsys.readouterr().out


def test_empty_tools_is_rejected(capsys):
    assert na.main(["--name", "ok", "--description", "Use it.", "--tools", ""]) == 1
    assert "at least one tool" in capsys.readouterr().out


def test_description_without_a_trigger_warns_but_proceeds(capsys):
    argv = ["--name", "ok", "--description", "Lints docs.", "--tools", "Read"]
    assert na.main(argv) == 0
    out = capsys.readouterr().out
    assert "[warn]" in out
    assert "when to delegate" in out
    assert "composed" in out, "a warning must not abort the compose"


# --- preview is the default ----------------------------------------------
def test_preview_is_the_default_and_installs_nothing(monkeypatch, capsys):
    def explode(*a, **k):
        raise AssertionError("register() must not run without --register")

    monkeypatch.setattr(na, "register", explode)
    assert na.main(BASE) == 0
    out = capsys.readouterr().out
    assert "preview only" in out
    assert "--register" in out


def test_preview_shows_the_composed_definition(capsys):
    na.main(BASE)
    out = capsys.readouterr().out
    assert "name: doc-linter" in out
    assert "model: inherit" in out
    assert "  - Read" in out


def test_model_choice_is_carried_into_the_definition(capsys):
    na.main([*BASE, "--model", "haiku"])
    assert "model: haiku" in capsys.readouterr().out


def test_steps_and_returns_reach_the_definition(capsys):
    na.main([*BASE, "--step", "Find docs", "--step", "Check links", "--returns", "a report"])
    out = capsys.readouterr().out
    assert "1. Find docs" in out
    assert "2. Check links" in out
    assert "Return: a report." in out


# --- the scan gate applies to home-grown agents too -----------------------
def test_high_risk_composition_is_blocked(monkeypatch, capsys):
    """A skeleton should never scan HIGH — but if it does, it must not install."""
    monkeypatch.setattr(
        na, "scan", lambda c: [{"severity": "HIGH", "label": "x", "why": "y", "snippet": "z"}]
    )
    monkeypatch.setattr(na, "register", lambda *a: pytest.fail("must not register"))
    assert na.main([*BASE, "--register"]) == 2
    assert "BLOCKED" in capsys.readouterr().out


# --- register hands off to the scanning installer -------------------------
def test_register_invokes_install_agent(monkeypatch):
    seen: list[list[str]] = []

    def fake_run(cmd, **k):
        seen.append(cmd)
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(na.subprocess, "run", fake_run)
    assert na.register("---\nname: x\n---\nbody\n", "x") == 0
    cmd = seen[0]
    assert any("install-agent.py" in part for part in cmd)
    assert "--type" in cmd and "agent" in cmd
    assert "--name" in cmd and "x" in cmd


def test_register_cleans_up_its_temp_file(monkeypatch):
    captured = {}

    def fake_run(cmd, **k):
        captured["path"] = cmd[cmd.index("--file") + 1]
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(na.subprocess, "run", fake_run)
    na.register("body", "leftover-probe")
    from pathlib import Path

    assert not Path(captured["path"]).exists(), "temp definition must not be left behind"


def test_register_propagates_the_installers_exit_code(monkeypatch):
    monkeypatch.setattr(na.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess([], 2))
    assert na.register("body", "x") == 2


def test_main_returns_the_registration_exit_code(monkeypatch):
    monkeypatch.setattr(na, "register", lambda content, name: 2)
    assert na.main([*BASE, "--register"]) == 2
