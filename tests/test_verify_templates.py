"""Tests for the template verifier.

CI smoke-tests the init *engine* with `--plan`, which writes nothing — so the
engine was covered and the templates were not. A dependency could break and
nobody would learn of it until the next person scaffolded a project and found it
red on arrival. This applies the ecosystem's own "verified green baseline" rule
one level up, to the blueprints.

The scaffold and baseline subprocesses are stubbed here; the real end-to-end run
is what CI does.
"""

from __future__ import annotations

import subprocess

import init_project as ip
import pytest
import verify_templates as vt


def _ok(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout, "")


def _fail(stderr="boom"):
    return subprocess.CompletedProcess([], 1, "", stderr)


# --- resolve_exe: the Windows bug this surfaced ---------------------------
def test_resolve_exe_expands_a_bare_tool_name(monkeypatch):
    """On Windows `npm` is `npm.CMD`; subprocess without a shell raises
    FileNotFoundError on the bare name, which crashed init --apply on the
    typescript template instead of reporting a failed check."""
    monkeypatch.setattr(ip.shutil, "which", lambda x: "/resolved/npm")
    assert ip.resolve_exe(["npm", "install"]) == ["/resolved/npm", "install"]


def test_resolve_exe_passes_through_when_the_tool_is_absent(monkeypatch):
    """Leave it to the caller's error path rather than raising here."""
    monkeypatch.setattr(ip.shutil, "which", lambda x: None)
    assert ip.resolve_exe(["nope", "--version"]) == ["nope", "--version"]


def test_verify_baseline_reports_a_missing_tool_instead_of_crashing(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise FileNotFoundError(2, "not found")

    monkeypatch.setattr(ip.subprocess, "run", boom)
    assert ip.verify_baseline(tmp_path, "typescript-project") is False
    assert "cannot run" in capsys.readouterr().out


# --- which templates get verified ----------------------------------------
def test_templates_skips_underscore_directories():
    """`templates/_common` is an overlay, not a project blueprint."""
    assert "_common" not in vt.templates()


def test_templates_finds_the_shipped_blueprints():
    found = vt.templates()
    assert "python-project" in found
    assert "typescript-project" in found


# --- verify() ------------------------------------------------------------
def test_green_template_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(vt, "_run", lambda cmd, cwd: _ok())
    monkeypatch.setattr(vt.shutil, "which", lambda x: "/usr/bin/tool")
    ok, detail = vt.verify("python-project", tmp_path)
    assert ok
    assert "green" in detail


def test_failed_scaffold_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(vt.shutil, "which", lambda x: "/usr/bin/tool")
    monkeypatch.setattr(vt, "_run", lambda cmd, cwd: _fail("template not found"))
    ok, detail = vt.verify("python-project", tmp_path)
    assert not ok
    assert "scaffold failed" in detail


def test_red_baseline_is_reported(tmp_path, monkeypatch):
    """The point of the whole script: a template that scaffolds but whose
    project does not build."""
    calls = {"n": 0}

    def run(cmd, cwd):
        calls["n"] += 1
        return _ok() if calls["n"] == 1 else _fail("2 tests failed")

    monkeypatch.setattr(vt.shutil, "which", lambda x: "/usr/bin/tool")
    monkeypatch.setattr(vt, "_run", run)
    ok, detail = vt.verify("python-project", tmp_path)
    assert not ok
    assert "failed" in detail


def test_absent_runtime_skips_rather_than_fails(tmp_path, monkeypatch):
    """A machine without node should still be able to verify the python
    template; a missing toolchain is not a broken blueprint."""
    monkeypatch.setattr(vt.shutil, "which", lambda x: None)
    ok, detail = vt.verify("typescript-project", tmp_path)
    assert ok
    assert "skipped" in detail


# --- main ----------------------------------------------------------------
def test_main_returns_one_when_a_template_is_red(monkeypatch, capsys):
    monkeypatch.setattr(vt, "templates", lambda: ["python-project"])
    monkeypatch.setattr(vt, "verify", lambda t, w: (False, "baseline red"))
    assert vt.main([]) == 1
    assert "do not produce a green project" in capsys.readouterr().out


def test_main_returns_zero_when_all_green(monkeypatch, capsys):
    monkeypatch.setattr(vt, "templates", lambda: ["python-project"])
    monkeypatch.setattr(vt, "verify", lambda t, w: (True, "green"))
    assert vt.main([]) == 0
    assert "every template still scaffolds" in capsys.readouterr().out


def test_only_flag_narrows_the_run(monkeypatch):
    seen = []
    monkeypatch.setattr(vt, "templates", lambda: ["python-project", "typescript-project"])
    monkeypatch.setattr(vt, "verify", lambda t, w: (seen.append(t), (True, "green"))[1])
    vt.main(["--only", "python-project"])
    assert seen == ["python-project"]


def test_unknown_template_is_an_error(monkeypatch, capsys):
    monkeypatch.setattr(vt, "templates", lambda: ["python-project"])
    assert vt.main(["--only", "nope"]) == 1
    assert "unknown template" in capsys.readouterr().out


def test_nothing_is_written_inside_the_repo(monkeypatch):
    """Scaffolding happens in a temp dir; a stray project in the repo would be
    committed by accident."""
    dests = []
    monkeypatch.setattr(vt, "templates", lambda: ["python-project"])
    monkeypatch.setattr(vt, "verify", lambda t, w: (dests.append(w), (True, "ok"))[1])
    vt.main([])
    assert vt.REPO not in dests[0].parents and dests[0] != vt.REPO


@pytest.mark.parametrize("template", ["python-project", "typescript-project"])
def test_every_shipped_template_declares_a_baseline(template):
    """A template with no verify commands would be silently unverifiable."""
    assert ip.verify_commands(template), f"{template} has no baseline commands"
