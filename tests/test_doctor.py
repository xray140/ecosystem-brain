"""Tests for the drift detection in doctor.py.

drift_in compares a live copy against the rewritten repo source, so it must:
flag missing files, flag genuine edits, and stay quiet when the only difference
is the intended per-clone path substitution.
"""

from __future__ import annotations

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
