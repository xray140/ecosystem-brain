"""Tests for the mutation harness itself — who restores the restorer.

`mutate_checks.py` writes a defect into a real source file and puts it back. Its
docstring promised the file was "restored either way, including on failure",
which described the `finally` around a failing TEST and said nothing about a
failing RESTORE. On 2026-09-04 the restore write itself raised EINVAL — a
concurrent reader had the file open — the exception escaped the `finally`, and
`elif False:` was left live inside `check_roadmap` in scripts/selfcheck.py.
Nothing reported it. The next `git status` did.

A harness that can silently leave a mutation behind is worse than no harness:
every check that runs afterwards is measuring poisoned source and reporting
confidently on it. So the restore is now verified by reading the file back, and
these tests exist because until this run the harness could not be imported
without executing every mutation — which is why it had never been tested at all.
"""

from __future__ import annotations

import mutate_checks as mc
import pytest


# --- restore --------------------------------------------------------------
def test_restore_puts_the_file_back(tmp_path):
    f = tmp_path / "src.py"
    f.write_text("original\n", encoding="utf-8")
    f.write_text("mutated\n", encoding="utf-8")
    assert mc.restore(f, "original\n") is True
    assert f.read_text(encoding="utf-8") == "original\n"


def test_restore_retries_a_transient_write_failure(tmp_path, monkeypatch):
    """The failure that stranded a mutation was transient — a concurrent reader
    on Windows. One retry would have saved it."""
    f = tmp_path / "src.py"
    f.write_text("mutated\n", encoding="utf-8")
    real_write = type(f).write_text
    calls = {"n": 0}

    def flaky(self, data, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(22, "Invalid argument")
        return real_write(self, data, **kw)

    monkeypatch.setattr(type(f), "write_text", flaky)
    monkeypatch.setattr(mc.time, "sleep", lambda s: None)
    assert mc.restore(f, "original\n") is True
    assert f.read_text(encoding="utf-8") == "original\n"
    assert calls["n"] == 2, "it did not actually retry"


def test_restore_reports_failure_rather_than_claiming_success(tmp_path, monkeypatch):
    """Every attempt fails. The answer must be False — the caller has to be able
    to tell the operator the tree is dirty."""
    f = tmp_path / "src.py"
    f.write_text("mutated\n", encoding="utf-8")
    monkeypatch.setattr(
        type(f), "write_text", lambda self, data, **kw: (_ for _ in ()).throw(OSError(22, "nope"))
    )
    monkeypatch.setattr(mc.time, "sleep", lambda s: None)
    assert mc.restore(f, "original\n") is False


def test_restore_catches_a_write_that_lies(tmp_path, monkeypatch):
    """A write that returns cleanly but leaves different bytes on disk is the
    exact failure mode this harness exists to detect elsewhere. Verifying by
    reading back is the only way to notice it here."""
    f = tmp_path / "src.py"
    f.write_text("mutated\n", encoding="utf-8")
    monkeypatch.setattr(type(f), "write_text", lambda self, data, **kw: None)
    monkeypatch.setattr(mc.time, "sleep", lambda s: None)
    assert mc.restore(f, "original\n") is False


# --- run ------------------------------------------------------------------
def _mutation(tmp_path, find="KEEP", repl="GONE", tests="tests/whatever.py"):
    src = tmp_path / "subject.py"
    src.write_text(f"x = '{find}'\n", encoding="utf-8")
    return src, ("label", str(src), find, repl, tests)


def test_a_caught_mutant_restores_the_source(tmp_path, monkeypatch):
    src, mutation = _mutation(tmp_path)
    original = src.read_text(encoding="utf-8")
    monkeypatch.setattr(
        mc.subprocess, "run", lambda *a, **k: mc.subprocess.CompletedProcess(a, 1, "", "")
    )
    assert mc.run([mutation]) == 0
    assert src.read_text(encoding="utf-8") == original


def test_a_missed_mutant_is_a_failure(tmp_path, monkeypatch, capsys):
    _src, mutation = _mutation(tmp_path)
    monkeypatch.setattr(
        mc.subprocess, "run", lambda *a, **k: mc.subprocess.CompletedProcess(a, 0, "", "")
    )
    assert mc.run([mutation]) == 1
    assert "MISSED" in capsys.readouterr().out


def test_an_unplantable_mutant_is_a_failure_not_a_shrug(tmp_path, monkeypatch, capsys):
    """A skip means the harness proved nothing about that check. It exited 1 on
    a skip for three weeks after the ollama removal, which is what got the two
    dead anchors noticed."""
    src, mutation = _mutation(tmp_path, find="ABSENT")
    src.write_text("nothing to match here\n", encoding="utf-8")
    assert mc.run([mutation]) == 1
    assert "skip" in capsys.readouterr().out


def test_a_stranded_mutation_fails_the_run_and_names_the_file(tmp_path, monkeypatch, capsys):
    """The bug this file was written for: the test verdict was fine and the
    source was left mutated. A green-ish summary with a poisoned tree is the one
    outcome that must be impossible."""
    src, mutation = _mutation(tmp_path)
    monkeypatch.setattr(
        mc.subprocess, "run", lambda *a, **k: mc.subprocess.CompletedProcess(a, 1, "", "")
    )
    monkeypatch.setattr(mc, "restore", lambda path, original, attempts=5: False)
    assert mc.run([mutation]) == 1
    out = capsys.readouterr().out
    assert "IS STILL MUTATED" in out
    assert "git checkout --" in out, "it must print the command that undoes the damage"
    assert str(src.name) in out


def test_the_mutation_table_is_not_empty():
    """A harness with nothing to plant reports 'caught 0, missed 0' and exits 0,
    which reads exactly like success."""
    assert len(mc.MUTATIONS) >= 20


@pytest.mark.parametrize("entry", mc.MUTATIONS, ids=lambda e: e[0][:40])
def test_every_mutation_names_a_file_and_a_test_that_exist(entry):
    """A retargeted anchor is caught by the skip counter at runtime, but a typo
    in a path is worth catching without a full harness run."""
    _label, src, _find, _repl, tests = entry
    assert (mc.pathlib.Path(src)).exists(), f"{src} does not exist"
    assert (mc.pathlib.Path(tests)).exists(), f"{tests} does not exist"
