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

import re
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


# --- the run records what it ran on ---------------------------------------
# Added 2026-09-03: this step went red on ubuntu and green on windows for the
# same commit, and neither run named its toolchain. The npm version had to be
# inferred from the workflow file, which is exactly the kind of inference a
# report exists to make unnecessary.
def test_runtime_versions_names_both_node_and_npm():
    """npm is the version that matters and node is the version that decides it,
    so the npm runtime reports both."""
    line = vt.runtime_versions("npm")
    assert "node" in line, line
    assert "npm" in line, line
    # A version, not a word: "node v22.23.2, npm 10.9.8"
    assert re.search(r"node v?\d+\.\d+\.\d+", line), line
    assert re.search(r"npm v?\d+\.\d+\.\d+", line), line


def test_runtime_versions_drops_build_metadata():
    """`uv --version` answers "uv 0.11.23 (3cdf50e0 2026-06-19 x86_64-...)".
    The build hash is noise in a line meant to be compared between two runs."""
    line = vt.runtime_versions("uv")
    assert line.startswith("uv "), line
    assert "(" not in line, line
    assert line.count("uv") == 1, f"the tool name is printed twice: {line}"


def test_an_unprobed_runtime_says_so_rather_than_returning_nothing():
    """An empty string in a diagnostic line reads as "nothing to report", which
    is the failure this whole addition is about."""
    assert vt.runtime_versions("cargo") == "no version probe for this runtime"


def test_every_runtime_a_template_needs_has_a_version_probe():
    """A template whose runtime has no probe would report its baseline result
    without saying what produced it."""
    missing = [tool for tool in set(vt.RUNTIME.values()) if tool not in vt.VERSION_PROBES]
    assert not missing, f"runtimes with no version probe: {missing}"


def test_the_versions_are_printed_on_a_green_run_too(capsys, monkeypatch):
    """Recording the toolchain only on failure means there is never a green run
    to compare a red one against — and the comparison is the diagnosis."""
    monkeypatch.setattr(vt, "templates", lambda: ["typescript-project"])
    monkeypatch.setattr(vt, "verify", lambda template, workdir: (True, "green"))
    monkeypatch.setattr(vt, "runtime_versions", lambda tool: f"<{tool} versions>")
    assert vt.main([]) == 0
    out = capsys.readouterr().out
    assert "runtime: <npm versions>" in out
    assert "green" in out


# --- following npm's debug log --------------------------------------------
# npm reports an arborist crash as one line plus a path. On a CI runner that
# file is gone by the time anyone reads the report, so three runs across two
# platforms produced the same seven-word error and nothing that named a package.
# The log is right there while the step is still running.

# The real thing, copied from run 33807018438 (ubuntu-latest, npm 10.9.8).
NPM_CRASH_OUTPUT = """npm error Cannot read properties of null (reading 'edgesOut')
npm error A complete log of this run can be found in: {path}
"""


def test_the_log_path_is_followed_and_its_tail_returned(tmp_path):
    log = tmp_path / "2026-09-03T21_16_38_362Z-debug-0.log"
    log.write_text("\n".join(f"line {i}" for i in range(1, 51)), encoding="utf-8")
    out = vt.follow_debug_log(NPM_CRASH_OUTPUT.format(path=log), lines=5)
    assert log.name in out
    assert "line 50" in out, "the tail is the interesting end"
    assert "line 46" in out, "the whole tail, not just the last line"
    assert "line 45" not in out, "asked for 5 lines, got more"


def test_output_with_no_log_path_yields_nothing_rather_than_noise():
    """A command that failed for an ordinary reason must not gain a puzzling
    empty section in the report."""
    assert vt.follow_debug_log("npm error code E404\nnpm error 404 Not Found") == ""


def test_an_unreadable_log_says_so_instead_of_going_quiet(tmp_path):
    """Silence here would read as "npm had nothing more to say", which is the
    opposite of the truth and the exact habit this whole change is against."""
    missing = tmp_path / "gone-debug-0.log"
    out = vt.follow_debug_log(NPM_CRASH_OUTPUT.format(path=missing))
    assert "could not read" in out
    assert missing.name in out


def test_a_windows_log_path_survives_the_regex(tmp_path):
    """The path npm prints on windows is drive-lettered and separated by
    backslashes, and the regex must not mangle or truncate it — the crash of
    2026-09-03 reported one of each across the two runners.
    """
    log = tmp_path / "win-debug-0.log"
    log.write_text("arborist stack", encoding="utf-8")
    windows_style = str(log).replace("/", chr(92))
    out = vt.follow_debug_log(NPM_CRASH_OUTPUT.format(path=windows_style))
    assert "arborist stack" in out, f"the windows path was not followed: {out!r}"


def test_the_failure_detail_carries_the_log_when_there_is_one(tmp_path, monkeypatch):
    """End to end: the report a human reads must contain the deeper output, not
    just the line that points at it."""
    log = tmp_path / "deep-debug-0.log"
    log.write_text("verbose stack naming the package", encoding="utf-8")

    def fake_run(cmd, cwd):
        if "scaffold.py" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(
            cmd, 1, NPM_CRASH_OUTPUT.format(path=log), ""
        )

    monkeypatch.setattr(vt, "_run", fake_run)
    monkeypatch.setattr(vt.ip, "verify_commands", lambda t: [["npm", "install"]])
    monkeypatch.setattr(vt.shutil, "which", lambda tool: "/usr/bin/npm")
    ok, detail = vt.verify("typescript-project", tmp_path)
    assert not ok
    assert "edgesOut" in detail
    assert "verbose stack naming the package" in detail
