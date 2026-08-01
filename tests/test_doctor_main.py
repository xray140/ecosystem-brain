"""Tests for doctor.py's main() — the verdict, not the individual checks.

`drift_in` and `hooks_wiring_drift` are covered in test_doctor.py. What is left
is whether main() actually fails on what it detects: a doctor that prints a
problem and still exits 0 is worse than no doctor, because the heartbeat treats
its exit code as the signal.
"""

from __future__ import annotations

import json

import doctor
import pytest


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """A sandbox where repo and live agree, unless a test breaks one of them."""
    repo, live = tmp_path / "repo", tmp_path / "live"
    for sub in ("commands", "agents"):
        (repo / sub).mkdir(parents=True)
    (repo / "skills" / "memory").mkdir(parents=True)
    (live / "commands" / "ecosystem-brain").mkdir(parents=True)
    (live / "agents").mkdir(parents=True)
    (live / "skills" / "memory").mkdir(parents=True)

    hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}
    template = tmp_path / "hooks.json"
    template.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    settings = live / "settings.json"
    settings.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

    monkeypatch.setattr(doctor, "REPO", repo)
    monkeypatch.setattr(doctor, "CLAUDE_DIR", live)
    monkeypatch.setattr(doctor.bs, "REPO_ROOT", repo)
    monkeypatch.setattr(doctor.bs, "CLAUDE_DIR", live)
    monkeypatch.setattr(doctor.bs, "HOOKS_TEMPLATE", template)
    monkeypatch.setattr(doctor.bs, "SETTINGS", settings)
    monkeypatch.setattr(doctor.bs, "check_prereqs", lambda: None)
    return repo, live


def _pair(repo, live, rel_repo, rel_live, text="body\n"):
    (repo / rel_repo).write_text(text, encoding="utf-8")
    (live / rel_live).write_text(text, encoding="utf-8")


def test_healthy_sandbox_exits_zero(wired, capsys):
    repo, live = wired
    _pair(repo, live, "commands/doctor.md", "commands/ecosystem-brain/doctor.md")
    _pair(repo, live, "agents/a.md", "agents/a.md")
    _pair(repo, live, "skills/memory/SKILL.md", "skills/memory/SKILL.md")
    assert doctor.main() == 0
    assert "healthy" in capsys.readouterr().out


def test_drifted_command_fails_the_run(wired, capsys):
    repo, live = wired
    (repo / "commands" / "doctor.md").write_text("new\n", encoding="utf-8")
    (live / "commands" / "ecosystem-brain" / "doctor.md").write_text("old\n", encoding="utf-8")
    assert doctor.main() == 1
    out = capsys.readouterr().out
    assert "[drift]" in out
    assert "doctor found issues" in out
    assert "bootstrap.py" in out, "the fix must be stated, not just the problem"


def test_drifted_skill_fails_the_run(wired, capsys):
    """Skills were invisible to this check until v4.3.5."""
    repo, live = wired
    (repo / "skills" / "memory" / "SKILL.md").write_text("new\n", encoding="utf-8")
    (live / "skills" / "memory" / "SKILL.md").write_text("old\n", encoding="utf-8")
    assert doctor.main() == 1
    assert "skills/memory/SKILL.md" in capsys.readouterr().out


def test_missing_live_agent_fails_the_run(wired, capsys):
    repo, _live = wired
    (repo / "agents" / "never-installed.md").write_text("body\n", encoding="utf-8")
    assert doctor.main() == 1
    assert "missing in ~/.claude" in capsys.readouterr().out


def test_hook_wiring_drift_fails_the_run(wired, capsys):
    _repo, live = wired
    (live / "settings.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"hooks": [{"command": "echo stale"}]}]}}),
        encoding="utf-8",
    )
    assert doctor.main() == 1
    out = capsys.readouterr().out
    assert "hook wiring" in out
    assert "hook-wiring" in out


def test_stale_hook_script_path_fails_the_run(wired, capsys):
    _repo, live = wired
    hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "bash /gone/x.sh"}]}]}
    (live / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    doctor.bs.HOOKS_TEMPLATE.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    assert doctor.main() == 1
    assert "[STALE]" in capsys.readouterr().out


def test_several_problems_are_all_reported(wired, capsys):
    """A doctor that stops at the first fault makes you run it N times."""
    repo, live = wired
    (repo / "commands" / "a.md").write_text("new\n", encoding="utf-8")
    (live / "commands" / "ecosystem-brain" / "a.md").write_text("old\n", encoding="utf-8")
    (live / "settings.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"hooks": [{"command": "echo stale"}]}]}}),
        encoding="utf-8",
    )
    assert doctor.main() == 1
    out = capsys.readouterr().out
    assert "hook-wiring" in out and "drift" in out
