"""Tests for the weekly maintenance heartbeat.

The heartbeat's job is to notice rot when nobody is looking, so the property
that matters is that a failing check actually turns the verdict red and shows up
in the report — and that a non-gating check (network flakiness) does not.
"""

from __future__ import annotations

import subprocess

import maintenance as mt
import pytest


def _result(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture
def report_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(mt, "REPORT_DIR", tmp_path)
    return tmp_path


def _run_with(monkeypatch, results):
    """Stub `run` to return a canned result per check, in CHECKS order."""
    seq = iter(results)
    monkeypatch.setattr(mt, "run", lambda cmd: next(seq))


def test_all_green_exits_zero_and_reports_all_clear(report_dir, monkeypatch, capsys):
    _run_with(monkeypatch, [_result(0, "ok")] * len(mt.CHECKS))
    assert mt.main() == 0
    assert "all clear" in capsys.readouterr().out
    report = next(report_dir.glob("*.md"))
    assert "**Verdict:** all clear" in report.read_text(encoding="utf-8")


def test_a_failing_gating_check_turns_the_verdict_red(report_dir, monkeypatch, capsys):
    _run_with(monkeypatch, [_result(1, "", "doctor blew up")] + [_result(0)] * (len(mt.CHECKS) - 1))
    assert mt.main() == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "NEEDS ATTENTION" in out


def test_non_gating_check_failure_does_not_fail_the_run(report_dir, monkeypatch):
    """`update --check` hits the network; a hiccup there is not ecosystem rot."""
    gating = [c for c in mt.CHECKS if c[2]]
    results = [_result(0)] * len(gating) + [_result(1, "", "network down")]
    _run_with(monkeypatch, results)
    assert mt.main() == 0


def test_report_captures_each_checks_output(report_dir, monkeypatch):
    _run_with(monkeypatch, [_result(0, f"output-{i}") for i in range(len(mt.CHECKS))])
    mt.main()
    body = next(report_dir.glob("*.md")).read_text(encoding="utf-8")
    for i in range(len(mt.CHECKS)):
        assert f"output-{i}" in body
    for label, _cmd, _gating in mt.CHECKS:
        assert label in body


def test_report_is_named_for_the_day_and_has_frontmatter(report_dir, monkeypatch):
    _run_with(monkeypatch, [_result(0)] * len(mt.CHECKS))
    mt.main()
    report = next(report_dir.glob("*.md"))
    text = report.read_text(encoding="utf-8")
    assert report.stem.count("-") == 2  # YYYY-MM-DD
    assert text.startswith("---\ntype: maintenance\n")
    assert f"date: {report.stem}" in text


def test_silent_check_still_gets_a_section(report_dir, monkeypatch):
    _run_with(monkeypatch, [_result(0, "", "")] * len(mt.CHECKS))
    mt.main()
    assert "(no output)" in next(report_dir.glob("*.md")).read_text(encoding="utf-8")


def test_report_is_written_with_lf_endings(report_dir, monkeypatch):
    """.gitattributes pins the repo to LF; 4.3.4 was an entire release about
    write sites that ignored it."""
    _run_with(monkeypatch, [_result(0, "line one\nline two")] * len(mt.CHECKS))
    mt.main()
    assert b"\r\n" not in next(report_dir.glob("*.md")).read_bytes()


def test_checks_invoke_scripts_that_exist():
    """A renamed script would make the heartbeat fail for the wrong reason."""
    for _label, cmd, _gating in mt.CHECKS:
        script = next(part for part in cmd if part.endswith(".py"))
        assert (mt.REPO / "scripts").is_dir()
        assert script.endswith(".py")
        from pathlib import Path

        assert Path(script).exists(), f"{script} referenced by the heartbeat does not exist"
