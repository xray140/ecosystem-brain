"""Tests for the agent-usage report.

Every installed agent costs SessionStart context, and nothing measured whether
any were ever used — so the roster only ever grew. The delicate part is not the
counting; it is not overclaiming from it. Transcripts are local and rotatable,
so "never invoked" means "not in what is on this machine", and the tool must
report rather than remove.
"""

from __future__ import annotations

import json

import agent_usage as au
import pytest


def _transcript(root, name, *subagents):
    f = root / f"{name}.jsonl"
    lines = [json.dumps({"type": "user", "text": "hi"})]
    for s in subagents:
        lines.append(json.dumps({"tool": "Agent", "input": {"subagent_type": s}}))
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def _installed(tmp_path, agents):
    p = tmp_path / "installed.json"
    p.write_text(json.dumps({"agents": agents}), encoding="utf-8")
    return p


# --- counting -------------------------------------------------------------
def test_counts_invocations_across_transcripts(tmp_path):
    _transcript(tmp_path, "a", "security-auditor", "security-auditor")
    _transcript(tmp_path, "b", "security-auditor", "bug-fixer")
    counts, _last = au.scan_transcripts(tmp_path)
    assert counts == {"security-auditor": 3, "bug-fixer": 1}


def test_records_the_most_recent_transcript_date(tmp_path):
    _transcript(tmp_path, "a", "test-writer")
    _counts, last = au.scan_transcripts(tmp_path)
    assert last["test-writer"].count("-") == 2, "an ISO date"


def test_nested_project_directories_are_scanned(tmp_path):
    nested = tmp_path / "project-slug"
    nested.mkdir()
    _transcript(nested, "deep", "python-pro")
    counts, _ = au.scan_transcripts(tmp_path)
    assert counts["python-pro"] == 1


def test_missing_transcript_root_is_not_an_error(tmp_path):
    assert au.scan_transcripts(tmp_path / "absent") == ({}, {})


def test_unreadable_transcript_is_skipped_not_fatal(tmp_path):
    _transcript(tmp_path, "good", "python-pro")
    (tmp_path / "bad.jsonl").write_bytes(b"\xff\xfe not text")
    counts, _ = au.scan_transcripts(tmp_path)
    assert counts["python-pro"] == 1, "one bad file must not lose the others"


# --- classification -------------------------------------------------------
AGENTS = [
    {"name": "security-auditor", "source": "local"},
    {"name": "bug-fixer", "source": "local"},
    {"name": "python-pro", "source": "github:u/r/a.md"},
    {"name": "ui-designer", "source": "github:u/r/b.md"},
]


def test_first_party_agents_are_never_removal_candidates():
    """They are the squad the SessionStart hook advertises. A zero there means
    "start delegating to it", not "delete it"."""
    r = au.report(AGENTS, {"python-pro": 2}, {})
    names = [row["name"] for row in r["unused"]]
    assert "bug-fixer" not in names, "unused first-party is not a candidate"
    assert names == ["ui-designer"]


def test_used_third_party_is_not_a_candidate():
    r = au.report(AGENTS, {"python-pro": 2, "ui-designer": 1}, {})
    assert r["unused"] == []


def test_used_list_is_ranked_by_invocations():
    agents = [
        {"name": "a", "source": "github:x"},
        {"name": "b", "source": "github:x"},
    ]
    r = au.report(agents, {"a": 1, "b": 9}, {})
    assert [row["name"] for row in r["used"]] == ["b", "a"]


def test_first_party_kept_even_when_used():
    r = au.report(AGENTS, {"security-auditor": 5}, {})
    assert [row["name"] for row in r["first_party"]] == ["security-auditor", "bug-fixer"]


# --- output contract ------------------------------------------------------
def test_report_states_the_local_only_caveat(tmp_path, monkeypatch, capsys):
    """Overclaiming here invites deleting an agent used on another machine."""
    monkeypatch.setattr(au, "INSTALLED", _installed(tmp_path, AGENTS))
    monkeypatch.setattr(au, "TRANSCRIPTS", tmp_path)
    assert au.main([]) == 0
    out = capsys.readouterr().out
    assert "on this machine" in out
    assert "another PC" in out
    assert "evidence rather than a verdict" in out


def test_report_never_deletes_anything(tmp_path, monkeypatch):
    before = {p.name for p in tmp_path.iterdir()}
    monkeypatch.setattr(au, "INSTALLED", _installed(tmp_path, AGENTS))
    monkeypatch.setattr(au, "TRANSCRIPTS", tmp_path)
    au.main([])
    assert {p.name for p in tmp_path.iterdir()} >= before, "must not remove files"


def test_unused_flag_prints_bare_names(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(au, "INSTALLED", _installed(tmp_path, AGENTS))
    monkeypatch.setattr(au, "TRANSCRIPTS", tmp_path)
    au.main(["--unused"])
    assert capsys.readouterr().out.split() == ["python-pro", "ui-designer"]


def test_no_installed_agents_is_fine(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(au, "INSTALLED", _installed(tmp_path, []))
    assert au.main([]) == 0
    assert "no installed agents" in capsys.readouterr().out


def test_missing_registry_is_fine(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "INSTALLED", tmp_path / "absent.json")
    assert au.load_installed(tmp_path / "absent.json") == []
    assert au.main([]) == 0


@pytest.mark.parametrize(
    "payload",
    ['{"subagent_type":"x"}', '{"subagent_type": "x"}', '{ "subagent_type"  :  "x" }'],
)
def test_field_is_matched_despite_spacing(tmp_path, payload):
    (tmp_path / "t.jsonl").write_text(payload + "\n", encoding="utf-8")
    counts, _ = au.scan_transcripts(tmp_path)
    assert counts == {"x": 1}


# --- the evidence window --------------------------------------------------
# "Never invoked" can only ever mean "not in the transcripts still on disk".
# Here those span 26 days while the oldest agent was installed 60 days ago.
# A report that omits the window overstates itself and invites deleting
# something that is used.


def test_the_oldest_transcript_date_is_reported(tmp_path):
    _transcript(tmp_path, "a", "python-pro")
    _counts, _last, oldest = au.scan_transcripts_windowed(tmp_path)
    assert oldest and oldest.count("-") == 2


def test_no_transcripts_means_no_window(tmp_path):
    assert au.scan_transcripts_windowed(tmp_path / "absent") == ({}, {}, None)


def test_agents_installed_before_the_window_are_flagged(tmp_path, monkeypatch, capsys):
    """The blind spot must be named, with the agents it covers."""
    _transcript(tmp_path, "recent", "python-pro")
    monkeypatch.setattr(
        au,
        "INSTALLED",
        _installed(
            tmp_path,
            [
                {"name": "old-one", "source": "github:u/r/a.md", "installed_at": "2020-01-01"},
                {"name": "python-pro", "source": "github:u/r/b.md", "installed_at": "2099-01-01"},
            ],
        ),
    )
    monkeypatch.setattr(au, "TRANSCRIPTS", tmp_path)
    au.main([])
    out = capsys.readouterr().out
    assert "evidence window" in out
    assert "installed BEFORE the oldest transcript" in out
    warning = out.split("installed BEFORE the oldest transcript", 1)[1].split("\n\n", 1)[0]
    assert "old-one" in warning
    assert "python-pro" not in warning, "installed inside the window, so not a blind spot"


def test_no_blind_spot_is_not_announced(tmp_path, monkeypatch, capsys):
    _transcript(tmp_path, "recent", "python-pro")
    monkeypatch.setattr(
        au,
        "INSTALLED",
        _installed(tmp_path, [{"name": "python-pro", "source": "github:u/r/b.md",
                               "installed_at": "2099-01-01"}]),
    )
    monkeypatch.setattr(au, "TRANSCRIPTS", tmp_path)
    au.main([])
    assert "installed BEFORE" not in capsys.readouterr().out


def test_local_agents_are_not_counted_as_blind_spots(tmp_path, monkeypatch, capsys):
    """First-party agents are versioned in this repo, not fetched — the window
    argument does not apply to them."""
    _transcript(tmp_path, "recent", "x")
    monkeypatch.setattr(
        au,
        "INSTALLED",
        _installed(tmp_path, [{"name": "bug-fixer", "source": "local",
                               "installed_at": "2020-01-01"}]),
    )
    monkeypatch.setattr(au, "TRANSCRIPTS", tmp_path)
    au.main([])
    assert "installed BEFORE" not in capsys.readouterr().out


def test_the_old_two_value_helper_still_works(tmp_path):
    """scan_transcripts is used elsewhere; the windowed variant must not break it."""
    _transcript(tmp_path, "a", "python-pro", "python-pro")
    counts, last = au.scan_transcripts(tmp_path)
    assert counts == {"python-pro": 2}
    assert "python-pro" in last
