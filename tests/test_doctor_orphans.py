"""Tests for the reverse direction of the sync check.

The defect: `doctor` walked the repo and asked "is each file live?" — and
nothing ever walked the other way. So on 2026-08-21, minutes after a merge
deleted `agents/cli-developer.md` and `agents/python-pro.md`, doctor printed
`[ok] healthy — live config in sync with the repo` while both were still in
~/.claude, loading into every session.

A removed agent that keeps running is worse than one that never shipped, so the
property under test is: a file this repo installed and has since deleted must be
found — and a file the ecosystem never installed must never be touched or
blamed, because that is what makes the check safe to gate on.
"""

from __future__ import annotations

import json

import doctor as dr
import pytest

import bootstrap as bs


@pytest.fixture
def live(tmp_path, monkeypatch):
    """An isolated ~/.claude, wired into both modules."""
    claude = tmp_path / "claude"
    claude.mkdir()
    monkeypatch.setattr(bs, "CLAUDE_DIR", claude)
    monkeypatch.setattr(bs, "INSTALL_MANIFEST", claude / ".ecosystem-brain-installed.json")
    monkeypatch.setattr(dr, "CLAUDE_DIR", claude)
    return claude


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo with one agent, one command and one skill."""
    root = tmp_path / "repo"
    (root / "agents").mkdir(parents=True)
    (root / "commands").mkdir()
    (root / "skills" / "memory").mkdir(parents=True)
    (root / "agents" / "keeper.md").write_text("keeper", encoding="utf-8")
    (root / "commands" / "doit.md").write_text("doit", encoding="utf-8")
    (root / "skills" / "memory" / "SKILL.md").write_text("skill", encoding="utf-8")
    monkeypatch.setattr(dr, "REPO", root)
    monkeypatch.setattr(bs, "REPO_ROOT", root)
    return root


def install(live, paths):
    """Put `paths` live and record them as ours, the way bootstrap would."""
    for rel in paths:
        f = live / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    (live / ".ecosystem-brain-installed.json").write_text(
        json.dumps({"generated": "t", "repo": "r", "paths": sorted(paths)}), encoding="utf-8"
    )


CURRENT = ["agents/keeper.md", "commands/ecosystem-brain/doit.md", "skills/memory/SKILL.md"]


# --- the bug ---------------------------------------------------------------
def test_an_agent_deleted_from_the_repo_is_found_still_live(live, repo):
    """This is the case that printed "healthy" on 2026-08-21."""
    install(live, [*CURRENT, "agents/python-pro.md"])
    stale, _ = dr.orphans_live()
    assert stale == ["agents/python-pro.md"]


def test_a_clean_install_reports_no_orphans(live, repo):
    install(live, CURRENT)
    stale, recorded = dr.orphans_live()
    assert stale == []
    assert recorded == 3


@pytest.mark.parametrize(
    ("orphan", "kind"),
    [
        ("agents/gone.md", "agent"),
        ("commands/ecosystem-brain/gone.md", "command"),
        ("skills/gone/SKILL.md", "skill"),
    ],
)
def test_every_installed_kind_is_checked(live, repo, orphan, kind):
    """Commands and skills rot the same way agents do — skills were already
    shipped-but-never-loaded once for exactly this kind of gap."""
    install(live, [*CURRENT, orphan])
    stale, _ = dr.orphans_live()
    assert stale == [orphan], kind


# --- the safety property that lets it gate ---------------------------------
def test_a_file_the_ecosystem_never_installed_is_never_reported(live, repo):
    """The user's own agent, or another plugin's command. Not in the manifest,
    so not our business — reporting it would make the check unusable."""
    install(live, CURRENT)
    (live / "agents" / "my-own.md").write_text("mine", encoding="utf-8")
    (live / "commands" / "other-plugin").mkdir(parents=True)
    (live / "commands" / "other-plugin" / "x.md").write_text("theirs", encoding="utf-8")
    stale, _ = dr.orphans_live()
    assert stale == []


def test_a_recorded_path_already_gone_from_disk_is_not_an_orphan(live, repo):
    """Someone removed it by hand. Nothing to report and nothing to do."""
    install(live, CURRENT)
    manifest = json.loads((live / ".ecosystem-brain-installed.json").read_text(encoding="utf-8"))
    manifest["paths"].append("agents/deleted-by-hand.md")
    (live / ".ecosystem-brain-installed.json").write_text(json.dumps(manifest), encoding="utf-8")
    stale, _ = dr.orphans_live()
    assert stale == []


# --- "cannot run" must not read as "passed" --------------------------------
def test_no_manifest_reports_unknown_rather_than_clean(live, repo):
    """Every install predating the manifest lands here. Returning [] would
    claim the vault is clean on the strength of having looked at nothing."""
    stale, _ = dr.orphans_live()
    assert stale is None


def test_a_corrupt_manifest_does_not_crash_the_doctor(live, repo):
    (live / ".ecosystem-brain-installed.json").write_text("{ not json", encoding="utf-8")
    stale, recorded = dr.orphans_live()
    assert stale == []
    assert recorded == 0


# --- bootstrap must actually deliver the fix doctor advertises -------------
def test_bootstrap_prunes_what_the_repo_no_longer_ships(live, repo, capsys):
    """doctor's advice is "re-run bootstrap". If bootstrap did not prune, that
    advice would be stale the moment it was printed."""
    install(live, [*CURRENT, "agents/python-pro.md"])
    removed = bs.prune_orphans(CURRENT, dry=False)
    assert removed == ["agents/python-pro.md"]
    assert not (live / "agents" / "python-pro.md").exists()
    assert (live / "agents" / "keeper.md").exists()


def test_a_dry_run_deletes_nothing(live, repo):
    install(live, [*CURRENT, "agents/python-pro.md"])
    removed = bs.prune_orphans(CURRENT, dry=True)
    assert removed == ["agents/python-pro.md"]
    assert (live / "agents" / "python-pro.md").exists()


def test_pruning_never_touches_a_file_it_did_not_install(live, repo):
    install(live, CURRENT)
    mine = live / "agents" / "my-own.md"
    mine.write_text("mine", encoding="utf-8")
    bs.prune_orphans(CURRENT, dry=False)
    assert mine.exists()


def test_an_emptied_skill_directory_is_removed_with_its_manifest(live, repo):
    install(live, [*CURRENT, "skills/dead/SKILL.md"])
    bs.prune_orphans(CURRENT, dry=False)
    assert not (live / "skills" / "dead").exists()
    assert (live / "skills" / "memory" / "SKILL.md").exists()
