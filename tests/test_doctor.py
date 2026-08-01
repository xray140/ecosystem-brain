"""Tests for the drift detection in doctor.py.

drift_in compares a live copy against the rewritten repo source, so it must:
flag missing files, flag genuine edits, and stay quiet when the only difference
is the intended per-clone path substitution.
"""

from __future__ import annotations

import json

import doctor


def _write(p, text):
    p.write_text(text, encoding="utf-8")


def test_in_sync_reports_no_drift(tmp_path):
    repo, live = tmp_path / "repo", tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    _write(repo / "a.md", "hello world\n")
    _write(live / "a.md", "hello world\n")
    assert doctor.drift_in(repo, live, "/d/clone/eco", "commands") == []


def test_missing_live_file_is_flagged(tmp_path):
    repo, live = tmp_path / "repo", tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    _write(repo / "a.md", "hello\n")
    problems = doctor.drift_in(repo, live, "/d/clone/eco", "agents")
    assert problems == [("agents/a.md", "missing in ~/.claude")]


def test_edited_repo_file_is_flagged(tmp_path):
    repo, live = tmp_path / "repo", tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    _write(repo / "a.md", "new content\n")
    _write(live / "a.md", "old content\n")
    problems = doctor.drift_in(repo, live, "/d/clone/eco", "commands")
    assert len(problems) == 1
    assert "drifted" in problems[0][1]


def test_path_rewrite_is_not_drift(tmp_path):
    # Repo holds the canonical path; the live copy holds the rewritten clone path.
    # That is the intended substitution, not drift.
    repo, live = tmp_path / "repo", tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    _write(repo / "a.md", f"run {doctor.bs.CANON_BASH}/scripts/x.py\n")
    _write(live / "a.md", "run /c/clone/eco/scripts/x.py\n")
    assert doctor.drift_in(repo, live, "/c/clone/eco", "commands") == []


def test_missing_repo_dir_is_empty(tmp_path):
    assert doctor.drift_in(tmp_path / "nope", tmp_path, "/x", "commands") == []


# --- skills: nested <name>/SKILL.md, not a flat *.md -----------------------


def _skill(root, name, text):
    d = root / name
    d.mkdir(parents=True)
    _write(d / "SKILL.md", text)


def test_skill_in_sync_reports_no_drift(tmp_path):
    repo, live = tmp_path / "repo", tmp_path / "live"
    _skill(repo, "memory", "body\n")
    _skill(live, "memory", "body\n")
    assert doctor.drift_in(repo, live, "/c/clone/eco", "skills", "*/SKILL.md") == []


def test_edited_skill_is_flagged(tmp_path):
    """The gap this closes: bootstrap started copying skills, but the drift check
    still globbed a flat *.md, so an edited SKILL.md was invisible to doctor."""
    repo, live = tmp_path / "repo", tmp_path / "live"
    _skill(repo, "memory", "new body\n")
    _skill(live, "memory", "old body\n")
    problems = doctor.drift_in(repo, live, "/c/clone/eco", "skills", "*/SKILL.md")
    assert len(problems) == 1
    assert problems[0][0] == "skills/memory/SKILL.md"
    assert "drifted" in problems[0][1]


def test_never_bootstrapped_skill_is_flagged_missing(tmp_path):
    repo, live = tmp_path / "repo", tmp_path / "live"
    _skill(repo, "secrets", "body\n")
    live.mkdir()
    problems = doctor.drift_in(repo, live, "/c/clone/eco", "skills", "*/SKILL.md")
    assert problems == [("skills/secrets/SKILL.md", "missing in ~/.claude")]


def test_flat_md_in_skills_dir_is_ignored(tmp_path):
    """A README beside the skill dirs is not a skill and must not be compared."""
    repo, live = tmp_path / "repo", tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    _write(repo / "README.md", "not a skill\n")
    assert doctor.drift_in(repo, live, "/c/clone/eco", "skills", "*/SKILL.md") == []


# --- hooks_wiring_drift: live settings hooks vs hooks/hooks.json ------------


def _wire(tmp_path, monkeypatch, template_hooks, live_hooks):
    template = tmp_path / "hooks.json"
    _write(template, json.dumps({"hooks": template_hooks}))
    settings = tmp_path / "settings.json"
    if live_hooks is not None:
        _write(settings, json.dumps({"hooks": live_hooks}))
    monkeypatch.setattr(doctor.bs, "HOOKS_TEMPLATE", template)
    monkeypatch.setattr(doctor.bs, "SETTINGS", settings)


def test_wiring_in_sync_is_not_drift(tmp_path, monkeypatch):
    hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}
    _wire(tmp_path, monkeypatch, hooks, hooks)
    assert doctor.hooks_wiring_drift("/c/clone/eco") is False


def test_wiring_edit_is_drift(tmp_path, monkeypatch):
    repo_hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "echo new"}]}]}
    live_hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "echo old"}]}]}
    _wire(tmp_path, monkeypatch, repo_hooks, live_hooks)
    assert doctor.hooks_wiring_drift("/c/clone/eco") is True


def test_wiring_missing_settings_is_not_drift(tmp_path, monkeypatch):
    hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}
    _wire(tmp_path, monkeypatch, hooks, None)
    assert doctor.hooks_wiring_drift("/c/clone/eco") is False


def test_wiring_path_rewrite_is_not_drift(tmp_path, monkeypatch):
    # hooks.json holds the canonical authoring path; live holds this clone's
    # rewritten path — that is bootstrap's intended substitution, not drift.
    repo_hooks = {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": f"bash {doctor.bs.CANON_BASH}/x.sh"}]}
        ]
    }
    live_hooks = {
        "SessionStart": [{"hooks": [{"type": "command", "command": "bash /c/clone/eco/x.sh"}]}]
    }
    _wire(tmp_path, monkeypatch, repo_hooks, live_hooks)
    assert doctor.hooks_wiring_drift("/c/clone/eco") is False
