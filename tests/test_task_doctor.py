"""Tests for the scheduled-task doctor.

The defect it exists for: the weekly heartbeat and the catalog refresh sat at
`State: Ready` from 2026-07-15 onward while **every scheduled run died**. The
catalog went 40 days without a refresh and the heartbeat wrote no report, and
nothing anywhere noticed, because everything that looked at those tasks looked
at their *state*.

So the one property that matters is that this judges on the last **result**, not
the state. A task can be Ready forever and never have completed anything.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
import task_doctor as td


def task(name="EcosystemBrain-X", result=0, days_ago=1, state="Ready"):
    when = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    return {"Name": name, "State": state, "LastRun": when, "LastResult": result, "NextRun": ""}


# --- the property the whole thing exists for ------------------------------
def test_ready_state_does_not_excuse_a_failed_run():
    """This is the bug. `State: Ready` told you nothing; two tasks reported it
    for weeks while every run was being terminated."""
    ok, detail = td.assess(task(result=0xC000013A, state="Ready"))
    assert not ok
    assert "terminated" in detail


@pytest.mark.parametrize(
    ("result", "fragment"),
    [
        (0x41306, "terminated before finishing"),
        (0xC000013A, "process was terminated"),
        (0x1, "exited 1"),
        (0x80070005, "0x80070005"),
    ],
)
def test_failure_codes_are_reported_in_words(result, fragment):
    ok, detail = td.assess(task(result=result))
    assert not ok
    assert fragment in detail


def test_a_successful_recent_run_passes():
    ok, detail = td.assess(task(result=0, days_ago=2))
    assert ok
    assert "ok" in detail


# --- a task that succeeds but stopped firing ------------------------------
def test_a_stale_success_is_still_a_problem():
    """A weekly task whose last success is a month old is not running either —
    the trigger stopped firing, and only the age reveals it."""
    ok, detail = td.assess(task(result=0, days_ago=40))
    assert not ok
    assert "40 days ago" in detail
    assert "trigger" in detail


def test_just_inside_the_staleness_window_passes():
    assert td.assess(task(result=0, days_ago=td.STALE_AFTER.days - 1))[0]


def test_just_outside_the_window_fails():
    assert not td.assess(task(result=0, days_ago=td.STALE_AFTER.days + 1))[0]


# --- benign states --------------------------------------------------------
def test_a_task_that_has_not_run_yet_is_fine():
    ok, detail = td.assess({"Name": "x", "LastResult": 0x41303, "LastRun": ""})
    assert ok
    assert "not yet run" in detail


def test_a_queued_task_is_fine():
    assert td.assess(task(result=0x41325))[0]


def test_an_unparseable_timestamp_does_not_crash():
    ok, _ = td.assess({"Name": "x", "LastResult": 0, "LastRun": "not-a-date"})
    assert ok


# --- the environment gate -------------------------------------------------
def test_non_windows_reports_not_applicable(monkeypatch, capsys):
    monkeypatch.setattr(td, "WINDOWS", False)
    assert td.main([]) == 0
    assert "not available here" in capsys.readouterr().out


def test_no_registered_tasks_is_not_a_failure(monkeypatch, capsys):
    monkeypatch.setattr(td, "query_tasks", lambda: [])
    assert td.main([]) == 0
    out = capsys.readouterr().out
    assert "no 'EcosystemBrain-*' tasks" in out
    assert "register-scheduled-tasks" in out, "say how to fix it"


def test_powershell_absent_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(td, "WINDOWS", True)
    monkeypatch.setattr(td.shutil, "which", lambda x: None)
    assert td.query_tasks() is None


def test_a_powershell_timeout_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(td, "WINDOWS", True)
    monkeypatch.setattr(td.shutil, "which", lambda x: "powershell")

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("powershell", 60)

    monkeypatch.setattr(td.subprocess, "run", boom)
    assert td.query_tasks() is None


# --- PowerShell 5.1 output shapes ----------------------------------------
def _ps(stdout):
    return lambda *a, **k: subprocess.CompletedProcess([], 0, stdout, "")


def test_a_single_task_object_is_normalised_to_a_list(monkeypatch):
    """Windows PowerShell 5.1 emits a bare object rather than a 1-element array.
    Assuming an array made the first version report "no tasks registered" on a
    machine with three registered and two failing."""
    monkeypatch.setattr(td, "WINDOWS", True)
    monkeypatch.setattr(td.shutil, "which", lambda x: "powershell")
    monkeypatch.setattr(td.subprocess, "run", _ps(json.dumps({"Name": "one", "LastResult": 0})))
    got = td.query_tasks()
    assert isinstance(got, list) and len(got) == 1


def test_an_array_is_passed_through(monkeypatch):
    monkeypatch.setattr(td, "WINDOWS", True)
    monkeypatch.setattr(td.shutil, "which", lambda x: "powershell")
    monkeypatch.setattr(td.subprocess, "run", _ps(json.dumps([{"Name": "a"}, {"Name": "b"}])))
    assert len(td.query_tasks()) == 2


def test_unparseable_output_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setattr(td, "WINDOWS", True)
    monkeypatch.setattr(td.shutil, "which", lambda x: "powershell")
    monkeypatch.setattr(td.subprocess, "run", _ps("not json"))
    assert td.query_tasks() is None


# --- exit contract --------------------------------------------------------
def test_main_fails_when_a_task_is_failing(monkeypatch, capsys):
    monkeypatch.setattr(td, "query_tasks", lambda: [task(result=0xC000013A)])
    assert td.main([]) == 1
    out = capsys.readouterr().out
    assert "not completing" in out
    assert "State=Ready forever" in out, "name the trap explicitly"


def test_main_passes_when_all_tasks_are_healthy(monkeypatch, capsys):
    monkeypatch.setattr(td, "query_tasks", lambda: [task(), task(name="EcosystemBrain-Y")])
    assert td.main([]) == 0
    assert "completed a recent run" in capsys.readouterr().out


# --- a run in flight is not a failed run ----------------------------------
# The heartbeat runs task_doctor as one of its own checks, so task_doctor always
# reads the heartbeat's OWN in-progress run. Judging that as a failure latched
# the report red permanently: FAIL -> maintenance exits 1 -> next run reads 0x1
# -> FAIL again. These pin the exit from that loop.
def test_the_heartbeats_own_in_flight_run_is_not_a_failure():
    """0x41301 on the task that is running us right now. Before the fix this
    returned False, and the weekly report could never be green."""
    ok, detail = td.assess(task(name="EcosystemBrain-Maintenance", result=td.RUNNING, days_ago=0))
    assert ok
    assert detail == "run in progress"


def test_a_run_still_running_long_past_its_time_limit_is_stuck():
    """The grace window must not swallow a genuine hang — a task pinned at
    "running" for a day never completed."""
    ok, detail = td.assess(task(result=td.RUNNING, days_ago=2))
    assert not ok
    assert "stuck" in detail


def test_running_grace_is_wider_than_the_tasks_execution_time_limit():
    """register-scheduled-tasks.ps1 caps every run at 15 minutes, so anything
    inside that window is legitimately in flight."""
    assert td.RUNNING_GRACE > timedelta(minutes=15)


def test_a_previous_run_that_exited_1_is_still_a_failure():
    """The grace path is scoped to 0x41301 only. A finished run that exited
    non-zero stays red — that is the signal the doctor exists for."""
    assert not td.assess(task(result=0x1))[0]
