"""Tests for `memory-index.py --check` as a gate.

The defect: `--check` built a fresh index, printed its counts, and returned 0
whatever it found. It could not fail, so nothing ever noticed the manifest going
stale — and nothing else looked at it either. `memory-search status` counts .md
files against the semantic database and never opens `index.json`, and the weekly
heartbeat refreshed only the semantic index.

So on 2026-08-21 the manifest had been frozen for 18 days: it listed a note that
no longer existed, missed three that did, and five more had changed underneath
it — while every check reported the vault healthy. That matters more than the
other indexes because `SKILL.md` tells the agent to load this file at session
start *instead of* reading the vault.

The property under test: --check goes red when the manifest stops describing
the vault, and stays quiet when it does.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "memory" / "memory-index.py"
spec = importlib.util.spec_from_file_location("memory_index_gate", SKILL)
mi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mi)


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "decisions").mkdir()
    (tmp_path / "decisions" / "one.md").write_text(
        "---\ntype: decision\nstatus: active\n---\n# One\n", encoding="utf-8"
    )
    (tmp_path / "two.md").write_text("---\ntype: note\n---\n# Two\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def manifest(vault):
    """A manifest that faithfully describes the vault."""
    out = vault / "index.json"
    out.write_text(json.dumps(mi.build(vault), indent=2), encoding="utf-8")
    return out


# --- the gate must be able to fail ----------------------------------------
def test_a_faithful_manifest_passes(vault, manifest, capsys):
    assert mi.check(mi.build(vault), manifest) == 0
    assert "matches the vault" in capsys.readouterr().out


def test_a_note_listed_but_deleted_is_a_phantom(vault, manifest, capsys):
    """The 2026-08-21 case: a note written on a branch that was never merged."""
    (vault / "two.md").unlink()
    assert mi.check(mi.build(vault), manifest) == 1
    assert "phantom" in capsys.readouterr().out


def test_a_note_on_disk_but_not_indexed_is_unlisted(vault, manifest, capsys):
    """Every new maintenance report landed here, week after week."""
    (vault / "three.md").write_text("---\ntype: note\n---\n# Three\n", encoding="utf-8")
    assert mi.check(mi.build(vault), manifest) == 1
    assert "unlisted" in capsys.readouterr().out


def test_a_note_whose_frontmatter_changed_is_stale(vault, manifest, capsys):
    """Path-set comparison alone misses this — five notes on 2026-08-21 were
    indexed under a status they no longer had."""
    (vault / "two.md").write_text(
        "---\ntype: note\nstatus: archived\n---\n# Two\n", encoding="utf-8"
    )
    assert mi.check(mi.build(vault), manifest) == 1
    assert "stale" in capsys.readouterr().out


def test_a_changed_link_is_stale(vault, manifest):
    (vault / "two.md").write_text("---\ntype: note\n---\n# Two\nsee [[one]]\n", encoding="utf-8")
    assert mi.compare(mi.build(vault), json.loads(manifest.read_text(encoding="utf-8")))


# --- and must not cry wolf -------------------------------------------------
def test_the_generated_timestamp_is_not_a_disagreement(vault, manifest):
    """It differs on every build by construction. Comparing on it would make the
    gate fire constantly, which is how a gate stops being read."""
    built = mi.build(vault)
    existing = json.loads(manifest.read_text(encoding="utf-8"))
    built["generated"] = "1999-01-01T00:00:00+00:00"
    existing["vault"] = "/somewhere/else"
    assert mi.compare(built, existing) == []


# --- "cannot run" is not "passed" ------------------------------------------
def test_a_missing_manifest_fails_rather_than_passing(vault, capsys):
    """Returning 0 here would report a vault as indexed on the strength of
    there being no index at all."""
    assert mi.check(mi.build(vault), vault / "index.json") == 1
    assert "no manifest" in capsys.readouterr().out


def test_an_unreadable_manifest_fails(vault, capsys):
    out = vault / "index.json"
    out.write_text("{ not json", encoding="utf-8")
    assert mi.check(mi.build(vault), out) == 1
    assert "unreadable" in capsys.readouterr().out


def test_a_manifest_with_junk_entries_does_not_crash(vault, manifest):
    existing = json.loads(manifest.read_text(encoding="utf-8"))
    existing["notes"].append("not a dict")
    existing["notes"].append({"no": "path key"})
    mi.compare(mi.build(vault), existing)  # must not raise


# --- --check inspects, it does not repair ----------------------------------
def test_check_never_writes_the_manifest(vault, manifest):
    """If it silently rewrote, it would always pass and tell you nothing."""
    (vault / "three.md").write_text("---\ntype: note\n---\n# Three\n", encoding="utf-8")
    before = manifest.read_bytes()
    mi.main(["--vault", str(vault), "--out", str(manifest), "--check"])
    assert manifest.read_bytes() == before


def test_main_check_returns_nonzero_on_disagreement(vault, manifest):
    (vault / "three.md").write_text("---\ntype: note\n---\n# Three\n", encoding="utf-8")
    assert mi.main(["--vault", str(vault), "--out", str(manifest), "--check"]) == 1


def test_main_check_returns_zero_when_faithful(vault, manifest):
    assert mi.main(["--vault", str(vault), "--out", str(manifest), "--check"]) == 0


def test_a_build_run_still_writes(vault):
    out = vault / "index.json"
    assert mi.main(["--vault", str(vault), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["counts"]["notes"] == 2


# --- the two questions must stay separate ---------------------------------
# Making --check a gate silently repurposed a flag `selfcheck` already used, and
# `memory/index.json` is gitignored — so on a fresh clone (CI) there is no
# manifest and every build would have gone red. --dry-run answers the question
# selfcheck was actually asking: can the indexer parse every note?
def test_dry_run_does_not_judge_freshness(vault, manifest):
    """A stale manifest is not --dry-run's business."""
    (vault / "three.md").write_text("---\ntype: note\n---\n# Three\n", encoding="utf-8")
    assert mi.main(["--vault", str(vault), "--out", str(manifest), "--dry-run"]) == 0


def test_dry_run_succeeds_with_no_manifest_at_all(vault):
    """The fresh-clone case that would have failed CI."""
    assert mi.main(["--vault", str(vault), "--out", str(vault / "index.json"), "--dry-run"]) == 0
    assert not (vault / "index.json").exists()


def test_dry_run_writes_nothing(vault, manifest):
    before = manifest.read_bytes()
    mi.main(["--vault", str(vault), "--out", str(manifest), "--dry-run"])
    assert manifest.read_bytes() == before


def test_a_vault_that_cannot_be_walked_still_fails(tmp_path):
    """--dry-run must not become unfailable in the process."""
    assert mi.main(["--vault", str(tmp_path / "nope"), "--dry-run"]) == 1
