"""A task cannot be evidence about its own current run.

The heartbeat latched permanently red. `maintenance.py` gates on `task_doctor`,
and one of the tasks `task_doctor` judges is `EcosystemBrain-Maintenance` — the
task running the check. Its recorded result is the PREVIOUS run's, so:

    maintenance exits 1 -> scheduler records 0x1 -> next run's task_doctor sees
    a task that never completes -> that check fails -> maintenance exits 1

Observed on 2026-08-21: ten of eleven checks green, verdict NEEDS ATTENTION,
still carrying a pytest failure that had been fixed the day before. One real
failure was enough to arm it forever.
"""

from __future__ import annotations

import json

import maintenance as mt
import pytest
import task_doctor as td

REPO_SCRIPT = "register-scheduled-tasks.ps1"

FAILING_SELF = {"Name": "EcosystemBrain-Maintenance", "LastResult": 1, "LastRun": ""}
FAILING_OTHER = {"Name": "EcosystemBrain-CatalogRefresh", "LastResult": 1, "LastRun": ""}
HEALTHY_OTHER = {"Name": "EcosystemBrain-OllamaServe", "LastResult": 0, "LastRun": ""}


@pytest.fixture
def tasks(monkeypatch):
    def _set(rows):
        monkeypatch.setattr(td, "query_tasks", lambda: rows)

    return _set


def test_excluded_task_does_not_set_the_exit_code(tasks, capsys):
    tasks([FAILING_SELF, HEALTHY_OTHER])
    assert td.main(["--exclude", "EcosystemBrain-Maintenance"]) == 0
    out = capsys.readouterr().out
    assert "not gated on" in out


def test_the_excluded_task_is_still_reported(tasks, capsys):
    """Excluded from the gate, not from the report — hiding it would trade one
    blind spot for another."""
    tasks([FAILING_SELF, HEALTHY_OTHER])
    td.main(["--exclude", "EcosystemBrain-Maintenance"])
    assert "EcosystemBrain-Maintenance" in capsys.readouterr().out


def test_other_failing_tasks_still_fail(tasks):
    """The exclusion must not become a way to pass with everything broken."""
    tasks([FAILING_SELF, FAILING_OTHER])
    assert td.main(["--exclude", "EcosystemBrain-Maintenance"]) == 1


def test_without_the_flag_behaviour_is_unchanged(tasks):
    """Run by hand, task_doctor still judges every task — the self-reference is
    only invalid when the check runs inside the task it is judging."""
    tasks([FAILING_SELF, HEALTHY_OTHER])
    assert td.main([]) == 1


def test_maintenance_passes_its_own_task_name(tmp_path):
    """The wiring, not just the capability."""
    cmd = next(c for label, c, _ in mt.CHECKS if "task_doctor" in label)
    assert "--exclude" in cmd
    assert cmd[cmd.index("--exclude") + 1] == mt.SELF_TASK


def test_self_task_name_matches_what_gets_registered():
    """If the registration script is renamed and this constant is not, the
    exclusion stops matching and the loop can re-arm — silently, because a name
    that matches nothing looks exactly like a name that matches a healthy task.
    """
    ps1 = (mt.REPO / "scripts" / REPO_SCRIPT).read_text(encoding="utf-8", errors="replace")
    assert mt.SELF_TASK in ps1, f"{mt.SELF_TASK} is not registered by {REPO_SCRIPT}"


def test_exclusion_is_exact_not_substring(tasks):
    """`--exclude EcosystemBrain` must not silence every task by prefix."""
    tasks([FAILING_SELF, FAILING_OTHER])
    assert td.main(["--exclude", "EcosystemBrain"]) == 1
    assert json  # keep the import meaningful for future JSON-shaped fixtures
