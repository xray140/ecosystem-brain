"""Tests for the SessionStart agent suggester.

This runs on every single session start, so a crash or a wrong path here is felt
immediately and everywhere — yet it was the least-tested code in the repo. The
path translation is the sharp edge: Claude Code hands it a Git Bash `cwd` like
/c/Users/x, and Python on Windows reads that as C:\\c\\Users\\x if left alone.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / "hooks" / "scripts"
spec = importlib.util.spec_from_file_location("suggest_agents", HOOKS / "suggest-agents.py")
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)

WINDOWS = os.name == "nt"


# --- path translation -----------------------------------------------------
@pytest.mark.skipif(not WINDOWS, reason="drive-letter translation is Windows-only")
def test_bash_mount_path_becomes_windows_path():
    """The bug this prevents: Path('/c/Users/x') resolves to C:\\c\\Users\\x."""
    assert sa.normalize_path("/c/Users/me/proj") == Path("C:/Users/me/proj")
    assert sa.normalize_path("/d/projects/x") == Path("D:/projects/x")


def test_ordinary_paths_pass_through():
    assert sa.normalize_path("relative/path") == Path("relative/path")
    assert sa.normalize_path(".") == Path(".")


@pytest.mark.skipif(not WINDOWS, reason="drive-letter translation is Windows-only")
def test_to_bash_path_is_the_inverse_on_windows():
    assert sa.to_bash_path(Path("C:/Users/me")) == "/c/Users/me"
    assert sa.to_bash_path(Path("/home/me")) == "/home/me"


@pytest.mark.skipif(WINDOWS, reason="describes the non-Windows branch")
def test_posix_mount_lookalikes_survive_off_windows():
    """`/d/projects/app` is a real posix path on Linux and macOS. Rewriting it
    to `D:/projects/app` points the hook at nothing, so it detects no project
    markers and silently suggests nothing — the failure is invisible."""
    assert sa.normalize_path("/d/projects/app") == Path("/d/projects/app")
    assert sa.normalize_path("/c/src/thing") == Path("/c/src/thing")
    assert sa.to_bash_path(Path("/d/projects/app")) == "/d/projects/app"


MOUNT_LOOKALIKES = ["/d/projects/app", "/c/src/thing", "/home/me/app", "relative/path", "."]


def test_non_windows_branch_leaves_mount_lookalikes_alone(monkeypatch):
    """Forces the non-Windows branch so this runs everywhere, including here.

    Simply comparing the two copies would not have caught the bug: on Windows
    both translate, so they agreed. The divergence only appeared off Windows,
    which is the platform CI runs on and this machine is not.
    """
    monkeypatch.setattr(sa, "WINDOWS", False)
    for raw in MOUNT_LOOKALIKES:
        assert sa.normalize_path(raw) == Path(raw), raw
    assert sa.to_bash_path(Path("/d/projects/app")) == "/d/projects/app"


def test_path_helpers_agree_with_bootstraps_copy(monkeypatch):
    """These two functions exist in bootstrap.py and here. bootstrap gained the
    Windows guard on 2026-06-06; this copy did not, for two months. Checked on
    BOTH branches, since agreement on one proves nothing about the other."""
    import bootstrap as bs

    assert sa.WINDOWS == bs.WINDOWS, "the two copies must agree on what platform this is"
    for windows in (True, False):
        monkeypatch.setattr(sa, "WINDOWS", windows)
        monkeypatch.setattr(bs, "WINDOWS", windows)
        for raw in MOUNT_LOOKALIKES:
            assert sa.normalize_path(raw) == bs._normalize(raw), (windows, raw)
        for p in (Path("C:/Users/me"), Path("/home/me"), Path("/d/projects/app")):
            assert sa.to_bash_path(p) == bs.to_bash_path(p), (windows, p)


# --- project-type detection ----------------------------------------------
def test_detect_tags_from_markers(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert sa.detect_tags(tmp_path) == {"python", "pytest"}


def test_detect_tags_unions_multiple_markers(tmp_path):
    (tmp_path / "package.json").write_text("", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("", encoding="utf-8")
    assert sa.detect_tags(tmp_path) == {"typescript", "javascript", "node"}


def test_detect_tags_empty_for_bare_directory(tmp_path):
    assert sa.detect_tags(tmp_path) == set()


# --- resilience: this must never break a session start --------------------
def test_load_json_survives_missing_file(tmp_path):
    assert sa.load_json(tmp_path / "nope.json") == {}


def test_load_json_survives_corrupt_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert sa.load_json(bad) == {}


def test_main_survives_empty_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert sa.main() == 0


def test_main_survives_garbage_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert sa.main() == 0


# --- catalog suggestions --------------------------------------------------
def _catalog(tmp_path, monkeypatch, agents):
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps({"agents": agents}), encoding="utf-8")
    monkeypatch.setattr(sa, "CATALOG", p)


def test_suggests_uninstalled_agents_matching_project_tags(tmp_path, monkeypatch):
    _catalog(
        tmp_path,
        monkeypatch,
        [
            {"name": "python-pro", "tags": ["python"], "repo": "u/r", "path": "a.md"},
            {"name": "rust-pro", "tags": ["rust"], "repo": "u/r", "path": "b.md"},
        ],
    )
    out = sa.suggest_uninstalled({"python"}, set())
    assert [a["name"] for a in out] == ["python-pro"]


def test_already_installed_agents_are_not_suggested(tmp_path, monkeypatch):
    _catalog(
        tmp_path,
        monkeypatch,
        [
            {"name": "python-pro", "tags": ["python"], "repo": "u/r", "path": "a.md"},
        ],
    )
    assert sa.suggest_uninstalled({"python"}, {"python-pro"}) == []


def test_suggestions_rank_by_tag_overlap(tmp_path, monkeypatch):
    _catalog(
        tmp_path,
        monkeypatch,
        [
            {"name": "one-tag", "tags": ["python"], "repo": "u/r", "path": "a.md"},
            {"name": "two-tags", "tags": ["python", "pytest"], "repo": "u/r", "path": "b.md"},
        ],
    )
    out = sa.suggest_uninstalled({"python", "pytest"}, set())
    assert [a["name"] for a in out] == ["two-tags", "one-tag"]


def test_no_project_tags_means_no_suggestions():
    assert sa.suggest_uninstalled(set(), set()) == []


def test_suggestions_respect_the_limit(tmp_path, monkeypatch):
    _catalog(
        tmp_path,
        monkeypatch,
        [
            {"name": f"agent-{i}", "tags": ["python"], "repo": "u/r", "path": f"{i}.md"}
            for i in range(10)
        ],
    )
    assert len(sa.suggest_uninstalled({"python"}, set(), limit=3)) == 3


# --- output contract ------------------------------------------------------
def _wire(tmp_path, monkeypatch, installed, registry=None, catalog=None):
    for attr, data in (
        ("INSTALLED", installed),
        ("REGISTRY", registry or {}),
        ("CATALOG", catalog or {}),
    ):
        p = tmp_path / f"{attr.lower()}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(sa, attr, p)


def test_emits_sessionstart_context_json(tmp_path, monkeypatch, capsys):
    _wire(tmp_path, monkeypatch, {"agents": [{"name": "security-auditor"}]})
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    assert sa.main() == 0
    payload = json.loads(capsys.readouterr().out)
    block = payload["hookSpecificOutput"]
    assert block["hookEventName"] == "SessionStart"
    assert "security-auditor" in block["additionalContext"]


def test_search_hint_uses_this_clones_real_path(tmp_path, monkeypatch, capsys):
    """A hardcoded canonical path here sends every session to a script that may
    not exist on this machine — the defect 4.3.2 fixed, pinned so it stays fixed.

    Banning the literal "/d/claude-projects" was the wrong way to pin it: that
    string is also what a correctly-derived hint contains on any machine that
    really does clone under /d/claude-projects, so the check failed the fix it
    was guarding. Move REPO_ROOT somewhere arbitrary and assert the hint follows
    it — that is the property, and it holds wherever the clone actually lives.
    """
    _wire(tmp_path, monkeypatch, {"agents": [{"name": "security-auditor"}]})
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    sa.main()
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    hint = next(ln for ln in context.splitlines() if "Search more" in ln)
    assert sa.to_bash_path(sa.REPO_ROOT) in hint

    elsewhere = tmp_path / "cloned" / "somewhere-else"
    monkeypatch.setattr(sa, "REPO_ROOT", elsewhere)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    sa.main()
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    moved = next(ln for ln in context.splitlines() if "Search more" in ln)
    assert sa.to_bash_path(elsewhere) in moved
    assert moved != hint


def test_silent_when_nothing_installed(tmp_path, monkeypatch, capsys):
    _wire(tmp_path, monkeypatch, {"agents": []})
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    assert sa.main() == 0
    assert capsys.readouterr().out == ""


def test_first_party_squad_listed_with_triggers(tmp_path, monkeypatch, capsys):
    _wire(tmp_path, monkeypatch, {"agents": [{"name": "bug-fixer"}]})
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    sa.main()
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "bug-fixer" in context
    assert sa.FIRST_PARTY["bug-fixer"] in context  # the trigger moment, not just the name
