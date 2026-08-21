"""The registry splits into a tracked half and a machine-local half.

The bug being pinned: `global_path` and `installed_at` describe one computer,
but lived in a git-tracked file. Two machines rewrote every entry, so they
conflicted line-for-line on every pull, and a machine that had not bootstrapped
yet appeared — in the committed file — to have agents it did not have.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import registry_io

LEGACY = {
    "_version": 1,
    "agents": [
        {
            "name": "data-engineer",
            "source": "github:u/r/data-engineer.md",
            "hash": "abc123",
            "installed_at": "2026-06-29",
            "global_path": "C:\\Users\\Someone Else\\.claude\\agents\\data-engineer.md",
            "ref": "main",
            "commit": "947b44c",
        },
        {
            "name": "security-auditor",
            "source": "local",
            "hash": "def456",
            "installed_at": "2026-06-04",
            "global_path": "~/.claude/agents/security-auditor.md",
        },
    ],
    "commands": [],
    "skills": [],
}


@pytest.fixture
def shared(tmp_path):
    p = tmp_path / "installed.json"
    p.write_text(json.dumps(LEGACY, indent=2), encoding="utf-8")
    return p


def _read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_save_keeps_machine_fields_out_of_the_tracked_file(shared):
    registry_io.save(registry_io.load(shared), shared)
    for entry in _read(shared)["agents"]:
        assert "global_path" not in entry
        assert "installed_at" not in entry
    # The durable half is still complete enough to reinstall from.
    first = _read(shared)["agents"][0]
    assert first["source"] == "github:u/r/data-engineer.md"
    assert first["commit"] == "947b44c"
    assert first["hash"] == "abc123"


def test_machine_fields_land_in_the_local_file(shared):
    registry_io.save(registry_io.load(shared), shared)
    local = _read(registry_io.local_path_for(shared))
    assert local["agents"]["data-engineer"]["installed_at"] == "2026-06-29"
    assert "Someone Else" in local["agents"]["data-engineer"]["global_path"]
    assert local["machine"]


def test_the_split_is_lossless(shared):
    """A caller that loads, saves, and loads again must see what it started with."""
    before = registry_io.load(shared)
    registry_io.save(before, shared)
    assert registry_io.load(shared) == before


def test_legacy_file_migrates_and_reports_what_moved(shared):
    assert registry_io.needs_migration(shared) is True
    assert registry_io.migrate(shared) == 2
    assert registry_io.needs_migration(shared) is False


def test_local_half_is_derived_beside_the_shared_one(tmp_path):
    """Not a fixed module path: a caller pointing at a temporary registry must
    not have the local half written into the real repo."""
    assert registry_io.local_path_for(tmp_path / "installed.json") == (
        tmp_path / "installed.local.json"
    )


def test_a_machine_without_the_local_file_still_reads_the_registry(shared):
    """The clone-and-go case: installed.local.json is gitignored, so a fresh
    checkout has only the tracked half and must not crash on the missing one."""
    registry_io.save(registry_io.load(shared), shared)
    registry_io.local_path_for(shared).unlink()
    agents = registry_io.load(shared)["agents"]
    assert [a["name"] for a in agents] == ["data-engineer", "security-auditor"]
    assert all("global_path" not in a for a in agents)


def test_a_corrupt_local_file_does_not_take_the_registry_down(shared):
    """The shared half is recoverable from git; the local half is not worth
    crashing over."""
    registry_io.save(registry_io.load(shared), shared)
    registry_io.local_path_for(shared).write_text("{ not json", encoding="utf-8")
    assert [a["name"] for a in registry_io.load(shared)["agents"]] == [
        "data-engineer",
        "security-auditor",
    ]


def test_two_machines_do_not_conflict_in_the_tracked_half(shared):
    """The whole point: the same install, recorded on two machines, produces
    byte-identical tracked files."""
    registry_io.save(registry_io.load(shared), shared)
    machine_a = shared.read_bytes()

    other = shared.parent / "other" / "installed.json"
    other.parent.mkdir()
    other.write_text(json.dumps(LEGACY, indent=2), encoding="utf-8")
    merged = registry_io.load(other)
    for entry in merged["agents"]:  # a different machine, different paths/dates
        entry["global_path"] = entry["global_path"].replace("Someone Else", "Other User")
        entry["installed_at"] = "2026-08-21"
    registry_io.save(merged, other)

    assert other.read_bytes() == machine_a
