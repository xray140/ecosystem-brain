"""Evidence that survives transcript rotation.

`agent_usage` answers "which installed agents are never invoked", and its answer
decides whether an agent gets removed. But its evidence is Claude Code
transcripts, which rotate: on 2026-08-22 this machine held one day's worth, so
every agent read `0x never invoked` and the report had to disclaim its own
central number. Deleting an agent on that basis would have been deleting on no
evidence at all.

The ledger is the accumulated half. Dates, not counts — the decision is
ever-versus-never, and a count would additionally have to solve double-counting
as transcripts roll.

Tracked in git and keyed by machine, which is the opposite call from
registry_io's split and deliberately so: there the machine-specific field made
the file conflict on every pull; here the machine IS the finding, because
"unused on MSI" and "unused anywhere" are different verdicts and only the second
justifies removing an agent the whole ecosystem shares.
"""

from __future__ import annotations

import json

import agent_usage as au
import pytest

AGENTS = [
    {"name": "python-pro", "source": "github:u/r/a.md", "installed_at": "2026-06-01"},
    {"name": "cli-developer", "source": "github:u/r/b.md", "installed_at": "2026-06-01"},
    {"name": "security-auditor", "source": "local"},
]


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "agent-usage.json"


def _read(p):
    return json.loads(p.read_text(encoding="utf-8"))


# --- recording --------------------------------------------------------------


def test_record_writes_this_machines_evidence(ledger_path):
    au.record({"python-pro": "2026-08-01"}, ledger_path, host="MSI")
    data = _read(ledger_path)
    assert data["machines"]["MSI"]["agents"]["python-pro"] == "2026-08-01"
    assert data["machines"]["MSI"]["since"] == "2026-08-01"


def test_record_is_idempotent(ledger_path):
    """The weekly heartbeat re-runs over the same transcripts; re-recording must
    not change anything or the file churns for no reason."""
    au.record({"python-pro": "2026-08-01"}, ledger_path, host="MSI")
    first = ledger_path.read_text(encoding="utf-8")
    au.record({"python-pro": "2026-08-01"}, ledger_path, host="MSI")
    assert ledger_path.read_text(encoding="utf-8") == first


def test_dates_only_ever_advance(ledger_path):
    au.record({"python-pro": "2026-08-10"}, ledger_path, host="MSI")
    au.record({"python-pro": "2026-08-01"}, ledger_path, host="MSI")
    assert _read(ledger_path)["machines"]["MSI"]["agents"]["python-pro"] == "2026-08-10"


def test_since_keeps_the_earliest_evidence_ever_contributed(ledger_path):
    """Not the oldest surviving transcript, which moves forward as they are
    deleted — that sliding window is the bug being fixed."""
    au.record({"python-pro": "2026-06-05"}, ledger_path, host="MSI")
    au.record({"python-pro": "2026-08-20"}, ledger_path, host="MSI")
    assert _read(ledger_path)["machines"]["MSI"]["since"] == "2026-06-05"


def test_machines_do_not_clobber_each_other(ledger_path):
    """Each machine writes only its own key, so the tracked file does not
    conflict line-for-line the way registry/installed.json used to."""
    au.record({"python-pro": "2026-08-01"}, ledger_path, host="MSI")
    au.record({"cli-developer": "2026-08-02"}, ledger_path, host="Verdun10")
    machines = _read(ledger_path)["machines"]
    assert machines["MSI"]["agents"] == {"python-pro": "2026-08-01"}
    assert machines["Verdun10"]["agents"] == {"cli-developer": "2026-08-02"}


def test_a_corrupt_ledger_does_not_take_the_report_down(ledger_path):
    ledger_path.write_text("{ not json", encoding="utf-8")
    assert au.load_ledger(ledger_path) == {"_version": 1, "machines": {}}


def test_missing_ledger_is_an_empty_one(tmp_path):
    assert au.load_ledger(tmp_path / "nope.json")["machines"] == {}


# --- what the ledger changes about the verdict ------------------------------


def test_an_agent_seen_before_rotation_is_not_a_removal_candidate(ledger_path):
    """The whole point: transcripts are gone, the evidence is not."""
    au.record({"python-pro": "2026-07-01"}, ledger_path, host="MSI")
    remembered = au.ledger_seen(au.load_ledger(ledger_path))
    r = au.report(AGENTS, counts={}, last_seen={}, remembered=remembered)
    names = [row["name"] for row in r["unused"]]
    assert "python-pro" not in names
    assert "cli-developer" in names, "an agent with no evidence anywhere is still a candidate"


def test_use_on_another_machine_counts(ledger_path):
    """'unused here' is not 'unused anywhere', and only the second is a reason to
    remove an agent the shared registry installs everywhere."""
    au.record({"cli-developer": "2026-08-02"}, ledger_path, host="Verdun10")
    remembered = au.ledger_seen(au.load_ledger(ledger_path))
    r = au.report(AGENTS, counts={}, last_seen={}, remembered=remembered)
    assert "cli-developer" not in [row["name"] for row in r["unused"]]
    row = next(x for x in r["used"] if x["name"] == "cli-developer")
    assert row["elsewhere"], "should be marked as ledger evidence, not a live count"


def test_ledger_seen_takes_the_latest_across_machines(ledger_path):
    au.record({"python-pro": "2026-07-01"}, ledger_path, host="MSI")
    au.record({"python-pro": "2026-08-09"}, ledger_path, host="Verdun10")
    assert au.ledger_seen(au.load_ledger(ledger_path))["python-pro"] == "2026-08-09"


def test_window_reaches_back_further_than_the_transcripts(ledger_path):
    au.record({"python-pro": "2026-06-05"}, ledger_path, host="MSI")
    assert au.ledger_since(au.load_ledger(ledger_path)) == "2026-06-05"


def test_first_party_agents_are_never_removal_candidates(ledger_path):
    """Unchanged by the ledger: a zero there means "start delegating", not
    "delete" — the SessionStart hook advertises them on purpose."""
    r = au.report(AGENTS, counts={}, last_seen={}, remembered={})
    assert [row["name"] for row in r["first_party"]] == ["security-auditor"]
