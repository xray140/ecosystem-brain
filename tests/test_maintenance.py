"""Tests for the weekly maintenance heartbeat.

The heartbeat's job is to notice rot when nobody is looking, so the property
that matters is that a failing check actually turns the verdict red and shows up
in the report — and that a non-gating check (network flakiness) does not.
"""

from __future__ import annotations

import subprocess
import sys

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
    """A network hiccup, or a project backlog still being triaged, is not
    ecosystem rot — only gating checks may turn the heartbeat red.

    Keyed on each check's own gating flag rather than on position: an earlier
    version assumed the non-gating checks came last, and broke the moment a
    second one was added in the middle.
    """
    monkeypatch.setattr(
        mt, "run", lambda cmd: _result(0 if _gating_for(cmd) else 1, "", "boom")
    )
    assert mt.main() == 0


def _gating_for(cmd):
    return next(gating for _label, c, gating in mt.CHECKS if c == cmd)


def test_every_non_gating_check_failing_at_once_is_still_green(report_dir, monkeypatch):
    non_gating = [label for label, _c, gating in mt.CHECKS if not gating]
    assert non_gating, "expected at least one advisory check"
    monkeypatch.setattr(
        mt, "run", lambda cmd: _result(0 if _gating_for(cmd) else 1, "", "boom")
    )
    assert mt.main() == 0


def test_a_failed_advisory_check_is_labelled_warn_not_ok(report_dir, monkeypatch, capsys):
    """Advisory means "does not turn the run red", not "did not happen".

    Filing a failed check under a section titled "— ok" is how the project
    doctor's four dead paths landed somewhere nobody skimming would open.
    """
    monkeypatch.setattr(
        mt, "run", lambda cmd: _result(0 if _gating_for(cmd) else 1, "problems found", "")
    )
    assert mt.main() == 0
    assert "[warn]" in capsys.readouterr().out
    body = next(report_dir.glob("*.md")).read_text(encoding="utf-8")
    assert "— warn" in body
    assert "advisory warnings" in body


def test_all_green_says_all_clear_not_warn(report_dir, monkeypatch, capsys):
    _run_with(monkeypatch, [_result(0)] * len(mt.CHECKS))
    mt.main()
    out = capsys.readouterr().out
    assert "all clear" in out
    assert "warn" not in out


def test_a_gating_failure_outranks_an_advisory_one(report_dir, monkeypatch, capsys):
    _run_with(monkeypatch, [_result(1, "", "boom")] * len(mt.CHECKS))
    assert mt.main() == 1
    assert "NEEDS ATTENTION" in capsys.readouterr().out


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


# --- the report is the artefact, and it is the thing that was broken ----------
# For eight weeks every check in this file passed while the reports on disk were
# corrupted, because each one stubs `run`. These two exercise the real one.
EM_DASH_CHILD = (
    "import sys; sys.stdout.reconfigure(encoding='utf-8'); print('healthy — in sync')"
)


def test_run_decodes_child_output_as_utf8_not_the_locale_encoding():
    """`text=True` alone decodes with the locale encoding — cp1252 on Windows —
    so a child's UTF-8 em dash arrived as three characters and the heartbeat
    wrote them down without a word of complaint."""
    r = mt.run([sys.executable, "-c", EM_DASH_CHILD])
    assert r.returncode == 0
    assert "healthy — in sync" in r.stdout
    assert "â€”" not in r.stdout, "child output was decoded with the locale encoding"
    assert "�" not in r.stdout


def test_the_written_report_carries_the_character_the_child_printed(report_dir, monkeypatch):
    """End to end: what a check prints is what the report says it printed."""
    monkeypatch.setattr(
        mt, "CHECKS", [("probe", [sys.executable, "-c", EM_DASH_CHILD], True)]
    )
    assert mt.main() == 0
    text = next(report_dir.glob("*.md")).read_text(encoding="utf-8")
    assert "healthy — in sync" in text
    assert "â€”" not in text
    assert "�" not in text
