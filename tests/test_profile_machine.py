"""Tests for the machine profile note.

The vault is shared across machines but almost everything in it is
machine-specific: a project card's drive letter, an agent's usage counts, which
scheduled tasks exist. Four cards recorded a `D:` path that exists on another PC
and nothing in the vault said which machine it was describing.

The note answers that. So the properties worth pinning are that it records the
facts a reader needs to resolve such a discrepancy, and that it never breaks the
install that writes it.
"""

from __future__ import annotations

import pathlib

import profile_machine as pm
import pytest


def test_the_note_records_which_drives_exist():
    """This is the fact the project cards needed. A card naming a drive absent
    from this list describes another machine, not a lost project."""
    note = pm.compose()
    assert "drives present" in note
    assert "not a lost one" in note, "say what the reader should conclude"


def test_drives_are_real_roots():
    for d in pm.drives():
        assert pathlib.Path(d + "\\" if d.endswith(":") else d).exists()


def test_the_note_names_the_host_in_frontmatter_and_body():
    note = pm.compose()
    assert f"host: {pm.host()}" in note
    assert f"# {pm.host()}" in note


def test_the_note_records_this_clone():
    note = pm.compose()
    assert str(pm.REPO) in note


def test_missing_tools_are_reported_as_an_explanation(monkeypatch):
    """A check reporting 'skipped' on this machine is usually explained by a
    missing tool rather than a fault — the note should say so."""
    monkeypatch.setattr(pm.shutil, "which", lambda t: None if t == "ollama" else "/usr/bin/" + t)
    note = pm.compose()
    assert "**missing**: ollama" in note
    assert "skipped" in note


def test_no_missing_section_when_everything_resolves(monkeypatch):
    monkeypatch.setattr(pm.shutil, "which", lambda t: "/usr/bin/" + t)
    note = pm.compose()
    assert "**missing**: none" in note


def test_the_note_says_it_is_derived():
    """A hand-edit would be overwritten; the note has to warn its reader."""
    assert "Regenerate rather than edit" in pm.compose()


def test_valid_frontmatter():
    note = pm.compose()
    assert note.startswith("---\n")
    assert note.index("\n---\n", 3) > 0
    for key in ("type:", "status:", "host:", "updated:", "tags:"):
        assert key in note.split("\n---\n")[0]


# --- writing --------------------------------------------------------------
def test_writes_one_note_per_host(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "MACHINES", tmp_path / "machines")
    assert pm.main([]) == 0
    written = list((tmp_path / "machines").glob("*.md"))
    assert [p.stem for p in written] == [pm.host()]


def test_rewriting_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "MACHINES", tmp_path / "machines")
    pm.main([])
    first = (tmp_path / "machines" / f"{pm.host()}.md").read_bytes()
    pm.main([])
    assert (tmp_path / "machines" / f"{pm.host()}.md").read_bytes() == first


def test_written_with_lf(tmp_path, monkeypatch):
    """.gitattributes pins the repo to LF."""
    monkeypatch.setattr(pm, "MACHINES", tmp_path / "machines")
    pm.main([])
    assert b"\r\n" not in (tmp_path / "machines" / f"{pm.host()}.md").read_bytes()


def test_print_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pm, "MACHINES", tmp_path / "machines")
    assert pm.main(["--print"]) == 0
    assert not (tmp_path / "machines").exists()
    assert "host:" in capsys.readouterr().out


def test_a_hostless_platform_still_produces_a_name(monkeypatch):
    monkeypatch.setattr(pm.platform, "node", lambda: "")
    assert pm.host() == "unknown-host"


def test_git_failure_does_not_break_the_note(monkeypatch):
    """A clone with no remote, or no git on PATH, still gets a note."""
    monkeypatch.setattr(pm, "_git", lambda *a: "")
    note = pm.compose()
    assert "**remote**: none" in note
    assert "**branch**: unknown" in note


# --- it must never break the install that writes it -----------------------
def test_bootstrap_survives_a_failing_profile(monkeypatch, capsys):
    import bootstrap as bs

    def boom(argv=None):
        raise RuntimeError("disk full")

    monkeypatch.setattr(pm, "main", boom)
    bs.write_machine_note(dry=False)
    assert "[skip] machine note" in capsys.readouterr().out


def test_bootstrap_dry_run_writes_no_note(monkeypatch, capsys):
    import bootstrap as bs

    monkeypatch.setattr(pm, "main", lambda argv=None: pytest.fail("must not write"))
    bs.write_machine_note(dry=True)
    assert "[dry]" in capsys.readouterr().out
