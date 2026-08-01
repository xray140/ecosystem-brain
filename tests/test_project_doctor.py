"""Tests for the project doctor — the ecosystem's feedback loop on its own output.

The defect that motivated it: four cards said `status: active` while pointing at
`D:\\claude-projects\\...`, a drive that does not exist on this machine, and
nothing had ever read those cards back.

Two properties carry the design. It must flag a dead path (or it is pointless),
and it must go quiet once the human records a decision (or it becomes noise the
weekly report trains you to skip — the failure the v4.3.11 symbol fix was about).
"""

from __future__ import annotations

import subprocess

import project_doctor as pd
import pytest

CARD = """---
type: project
status: {status}
created: 2026-06-05
stack: [python]
---
# {name}

## Paths
- Project: `{path}`
"""


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "projects"
    v.mkdir()
    monkeypatch.setattr(pd, "VAULT_PROJECTS", v)
    return v


def _card(vault, name, path, status="active"):
    (vault / f"{name}.md").write_text(
        CARD.format(name=name, path=path, status=status), encoding="utf-8"
    )


def _no_ci(monkeypatch):
    monkeypatch.setattr(pd, "ci_status", lambda p: None)


# --- parsing --------------------------------------------------------------
def test_path_comes_from_the_backticks_not_the_card_name():
    """`ipe-pipeline` records the folder `sensor-csv-pipeline` — a rename that
    never completed. Deriving the directory from the card name finds the wrong
    place, or nothing. That mistake is what made the first survey miscount."""
    text = CARD.format(
        name="ipe-pipeline", path=r"C:\Users\me\sensor-csv-pipeline", status="active"
    )
    status, path = pd.parse_card(text)
    assert status == "active"
    assert path == r"C:\Users\me\sensor-csv-pipeline"


def test_trailing_prose_after_the_path_is_not_captured():
    """Real cards annotate the line: '`C:\\x` (pas de D: sur cette machine)'."""
    text = "- Project: `C:/Users/me/thing` (rename pending, see note)\n"
    assert pd.parse_card(text)[1] == "C:/Users/me/thing"


def test_card_without_a_path_is_reported_not_crashed(vault, monkeypatch):
    _no_ci(monkeypatch)
    (vault / "bare.md").write_text("---\nstatus: active\n---\n# bare\n", encoding="utf-8")
    assert pd.main(["--no-ci"]) == 1


# --- the defect it exists to catch ----------------------------------------
def test_missing_path_is_a_problem(vault, monkeypatch, capsys):
    _no_ci(monkeypatch)
    _card(vault, "gone", r"D:\claude-projects\gone")
    assert pd.main(["--no-ci"]) == 1
    out = capsys.readouterr().out
    assert "path does not exist" in out
    assert "need attention" in out


def test_existing_path_is_healthy(vault, tmp_path, monkeypatch, capsys):
    _no_ci(monkeypatch)
    proj = tmp_path / "live-project"
    proj.mkdir()
    (proj / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    _card(vault, "live", str(proj))
    assert pd.main(["--no-ci"]) == 0
    assert "accounted for" in capsys.readouterr().out


# --- the escape hatch: a recorded decision must stop the nagging ----------
def test_archived_card_is_skipped_even_with_a_dead_path(vault, monkeypatch, capsys):
    """Once you decide a project is done, the check must go quiet. A report that
    keeps flagging a settled question is the noise that gets reports ignored."""
    _no_ci(monkeypatch)
    _card(vault, "finished", r"D:\gone\forever", status="archived")
    assert pd.main(["--no-ci"]) == 0
    assert "archived" in capsys.readouterr().out


def test_repairing_the_path_clears_the_problem(vault, tmp_path, monkeypatch):
    """The other escape hatch: point the card at where the project actually is."""
    _no_ci(monkeypatch)
    _card(vault, "moved", r"D:\old\place")
    assert pd.main(["--no-ci"]) == 1
    proj = tmp_path / "new-place"
    proj.mkdir()
    _card(vault, "moved", str(proj))
    assert pd.main(["--no-ci"]) == 0


# --- health notes are advisory, never failures ----------------------------
def test_notes_do_not_fail_the_run(vault, tmp_path, monkeypatch, capsys):
    """A missing AGENTS.md is worth saying; it is not worth turning the weekly
    heartbeat red."""
    _no_ci(monkeypatch)
    proj = tmp_path / "no-rules"
    proj.mkdir()
    _card(vault, "plain", str(proj))
    assert pd.main(["--no-ci"]) == 0
    assert "no AGENTS.md" in capsys.readouterr().out


def test_env_gap_is_reported(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".env.example").write_text("A=\nB=\n# note\nC=\n", encoding="utf-8")
    (proj / ".env").write_text("A=secret\n", encoding="utf-8")
    assert pd.env_gap(proj) == ["B", "C"]


def test_env_gap_empty_without_both_files(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    assert pd.env_gap(proj) == []
    (proj / ".env.example").write_text("A=\n", encoding="utf-8")
    assert pd.env_gap(proj) == [], "no .env yet is init's job, not a drift"


def test_env_gap_ignores_comments_and_blanks(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".env.example").write_text("\n# C=commented\nA=\n", encoding="utf-8")
    (proj / ".env").write_text("A=x\n", encoding="utf-8")
    assert pd.env_gap(proj) == []


# --- CI lookup is advisory ------------------------------------------------
def test_ci_lookup_skipped_without_a_workflows_dir(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    assert pd.ci_status(proj) is None


def test_ci_lookup_skipped_without_a_github_remote(tmp_path, monkeypatch):
    proj = tmp_path / "p"
    (proj / ".github" / "workflows").mkdir(parents=True)
    monkeypatch.setattr(pd.shutil, "which", lambda x: "/usr/bin/gh")
    monkeypatch.setattr(pd, "_git", lambda *a: "git@gitlab.com:me/p.git")
    assert pd.ci_status(proj) is None


def test_failing_ci_is_a_problem(vault, tmp_path, monkeypatch, capsys):
    proj = tmp_path / "p"
    proj.mkdir()
    _card(vault, "redci", str(proj))
    monkeypatch.setattr(pd, "ci_status", lambda p: "failure")
    assert pd.main([]) == 1
    assert "latest CI run: failure" in capsys.readouterr().out


def test_network_failure_never_turns_the_check_red(tmp_path, monkeypatch):
    """The heartbeat must not depend on GitHub being reachable."""
    proj = tmp_path / "p"
    (proj / ".github" / "workflows").mkdir(parents=True)
    monkeypatch.setattr(pd.shutil, "which", lambda x: "/usr/bin/gh")
    monkeypatch.setattr(pd, "_git", lambda *a: "https://github.com/me/p.git")

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("gh", 30)

    monkeypatch.setattr(pd.subprocess, "run", boom)
    assert pd.ci_status(proj) is None


# --- git health -----------------------------------------------------------
def test_non_git_directory_is_noted_not_failed(vault, tmp_path, monkeypatch, capsys):
    _no_ci(monkeypatch)
    proj = tmp_path / "loose"
    proj.mkdir()
    (proj / "AGENTS.md").write_text("x\n", encoding="utf-8")
    _card(vault, "loose", str(proj))
    assert pd.main(["--no-ci"]) == 0
    assert "not a git repository" in capsys.readouterr().out


def test_empty_vault_is_fine(vault, capsys):
    assert pd.main(["--no-ci"]) == 0
    assert "no registered projects" in capsys.readouterr().out
