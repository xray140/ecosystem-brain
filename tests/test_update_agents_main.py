"""Tests for update-agents.py's main() — the batch loop and its persistence.

`update_item` decides; `main` iterates, prints, and decides what to persist.
The bug class this guards is a mismatch between the two: a status that means the
registry changed but is never written back leaves the pin behind the content,
which is exactly how a "current" agent ends up stale.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location(
    "update_agents_main_mod", SCRIPTS / "update-agents.py"
)
ua = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ua)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    p = tmp_path / "installed.json"
    monkeypatch.setattr(ua, "INSTALLED_FILE", p)
    return p


def _write(registry, agents=None, commands=None, skills=None):
    registry.write_text(
        json.dumps(
            {
                "_version": 1,
                "agents": agents or [],
                "commands": commands or [],
                "skills": skills or [],
            }
        ),
        encoding="utf-8",
    )


def _statuses(monkeypatch, mapping):
    """Stub update_item to return a canned status per entry name."""
    monkeypatch.setattr(ua, "update_item", lambda entry, kind, check: mapping[entry["name"]])


# --- persistence ----------------------------------------------------------
@pytest.mark.parametrize(
    "status",
    ["updated (abc -> def)", "up-to-date (pinned -> abcdef1)"],
)
def test_statuses_that_mutate_the_entry_are_persisted(registry, monkeypatch, status):
    """Both 'updated' and a bare pin advance mutate the entry in place; if main
    does not write the file, the registry silently falls behind the content."""
    _write(registry, agents=[{"name": "a", "source": "local"}])
    monkeypatch.setattr(
        ua, "update_item", lambda entry, kind, check: (entry.update({"hash": "NEW"}), status)[1]
    )
    assert ua.main([]) == 0
    assert json.loads(registry.read_text(encoding="utf-8"))["agents"][0]["hash"] == "NEW"


def test_unchanged_run_does_not_rewrite_the_registry(registry, monkeypatch):
    _write(registry, agents=[{"name": "a", "source": "local"}])
    before = registry.read_bytes()
    _statuses(monkeypatch, {"a": "up-to-date"})
    ua.main([])
    assert registry.read_bytes() == before


def test_check_mode_never_writes(registry, monkeypatch, capsys):
    _write(registry, agents=[{"name": "a", "source": "local"}])
    before = registry.read_bytes()
    monkeypatch.setattr(
        ua,
        "update_item",
        lambda entry, kind, check: (entry.update({"hash": "NEW"}), "updated (x -> y)")[1],
    )
    ua.main(["--check"])
    assert registry.read_bytes() == before
    assert "run without --check to apply" in capsys.readouterr().out


def test_registry_is_written_with_lf(registry, monkeypatch):
    _write(registry, agents=[{"name": "a", "source": "local"}])
    monkeypatch.setattr(
        ua,
        "update_item",
        lambda entry, kind, check: (entry.update({"hash": "NEW"}), "updated (x -> y)")[1],
    )
    ua.main([])
    assert b"\r\n" not in registry.read_bytes()


# --- scope ----------------------------------------------------------------
def test_name_filter_updates_only_that_item(registry, monkeypatch, capsys):
    _write(registry, agents=[{"name": "a", "source": "local"}, {"name": "b", "source": "local"}])
    seen = []
    monkeypatch.setattr(
        ua, "update_item", lambda entry, kind, check: (seen.append(entry["name"]), "up-to-date")[1]
    )
    ua.main(["--name", "b"])
    assert seen == ["b"]
    assert "'b'" in capsys.readouterr().out


def test_all_three_kinds_are_walked(registry, monkeypatch):
    _write(
        registry,
        agents=[{"name": "a", "source": "local"}],
        commands=[{"name": "c", "source": "local"}],
        skills=[{"name": "s", "source": "local"}],
    )
    seen = []
    monkeypatch.setattr(
        ua,
        "update_item",
        lambda entry, kind, check: (seen.append((entry["name"], kind)), "up-to-date")[1],
    )
    ua.main([])
    assert seen == [("a", "agents"), ("c", "commands"), ("s", "skills")]


def test_missing_registry_is_not_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ua, "INSTALLED_FILE", tmp_path / "absent.json")
    assert ua.main([]) == 0
    assert "nothing to update" in capsys.readouterr().out


# --- reporting ------------------------------------------------------------
def test_blocked_updates_are_surfaced_loudly(registry, monkeypatch, capsys):
    """A quarantined upstream update is the one outcome that must not scroll by
    as just another line."""
    _write(registry, agents=[{"name": "evil", "source": "local"}])
    _statuses(monkeypatch, {"evil": "BLOCKED-unsafe (HIGH risk; quarantined -> evil.md)"})
    ua.main([])
    out = capsys.readouterr().out
    assert "[✗]" in out
    assert "1 update(s) blocked as HIGH-risk" in out
    assert "review quarantine/" in out


# --- status symbols -------------------------------------------------------
@pytest.mark.parametrize(
    ("status", "symbol"),
    [
        # ordinary outcomes — must NOT read as warnings
        ("local", "·"),
        ("up-to-date", "✓"),
        ("up-to-date (pinned -> abcdef1)", "✓"),
        ("synced", "→"),
        ("updated (abc -> def)", "↑"),
        ("update-available (abc -> def)  https://github.com/u/r/compare/a...b", "↑"),
        # things that genuinely need attention
        ("BLOCKED-unsafe (HIGH risk; quarantined -> evil.md, kept current)", "✗"),
        ("error: network down", "!"),
        ("missing-in-repo", "!"),
    ],
)
def test_every_status_maps_to_a_symbol(status, symbol):
    assert ua.status_symbol(status) == symbol


def test_an_unrecognised_status_falls_back_to_attention():
    """A status added later without updating the table should be loud, not
    quietly mislabelled as fine. `!` is the safe default; `✓` would not be."""
    assert ua.status_symbol("some-future-status") == "!"


def test_ordinary_outcomes_never_use_the_attention_marker():
    """`local` fires for all six first-party agents on every run, and `synced` is
    a success. Both used to fall through to `!`, and a column that cries wolf
    eight times a run stops being read at all."""
    for status in ("local", "synced", "up-to-date", "up-to-date (pinned -> abc1234)"):
        assert ua.status_symbol(status) != "!", status


def test_status_symbols_distinguish_the_outcomes(registry, monkeypatch, capsys):
    _write(
        registry,
        agents=[
            {"name": "same", "source": "local"},
            {"name": "moved", "source": "local"},
            {"name": "bad", "source": "local"},
            {"name": "oops", "source": "local"},
        ],
    )
    _statuses(
        monkeypatch,
        {
            "same": "up-to-date",
            "moved": "update-available (abc -> def)",
            "bad": "BLOCKED-unsafe (HIGH risk)",
            "oops": "error: network down",
        },
    )
    ua.main(["--check"])
    # Line shape: "  [<symbol>] <kind> <name>  <status>"
    lines = {
        ln.split()[2]: ln.split()[0] for ln in capsys.readouterr().out.splitlines() if "  [" in ln
    }
    assert lines["same"] == "[✓]"
    assert lines["moved"] == "[↑]"
    assert lines["bad"] == "[✗]"
    assert lines["oops"] == "[!]"


def test_total_counts_only_items_in_scope(registry, monkeypatch, capsys):
    _write(registry, agents=[{"name": f"a{i}", "source": "local"} for i in range(3)])
    _statuses(monkeypatch, {f"a{i}": "up-to-date" for i in range(3)})
    ua.main([])
    assert "all 3 installed items" in capsys.readouterr().out
