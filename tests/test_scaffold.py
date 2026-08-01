"""Tests for scaffold.py — chiefly the destination guard.

`--force` deletes the destination with `shutil.rmtree`, and the destination is
built from an unvalidated `--name`. These pin the cases where that delete could
have been aimed above the intended project directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import scaffold


# --- resolve_dest: the guard in front of rmtree ---------------------------
def test_ordinary_name_resolves_under_root(tmp_path):
    dest = scaffold.resolve_dest(tmp_path, "my-tool")
    assert dest == (tmp_path / "my-tool").resolve()
    assert tmp_path.resolve() in dest.parents


@pytest.mark.parametrize("name", ["..", ".", "../..", "../sibling", "a/b", "a\\b", ""])
def test_names_that_escape_or_target_the_root_are_refused(tmp_path, name):
    with pytest.raises(ValueError):
        scaffold.resolve_dest(tmp_path, name)


def test_absolute_name_is_refused(tmp_path):
    with pytest.raises(ValueError):
        scaffold.resolve_dest(tmp_path, str(tmp_path.parent / "elsewhere"))


def test_dot_dot_inside_a_longer_name_is_refused(tmp_path):
    with pytest.raises(ValueError):
        scaffold.resolve_dest(tmp_path, "a..b")


def test_overlong_name_refused(tmp_path):
    with pytest.raises(ValueError):
        scaffold.resolve_dest(tmp_path, "x" * 65)


# --- the destructive path itself ------------------------------------------
def test_force_cannot_delete_the_dest_root(tmp_path):
    """The failure this prevents: `--name .` making rmtree(dest) wipe the root
    that holds every scaffolded project."""
    root = tmp_path / "projects"
    (root / "existing-project").mkdir(parents=True)
    rc = scaffold.main(
        ["--type", "python-project", "--name", ".", "--dest-root", str(root), "--force"]
    )
    assert rc == 1
    assert root.is_dir()
    assert (root / "existing-project").is_dir()


def test_force_replaces_only_its_own_directory(tmp_path):
    root = tmp_path / "projects"
    victim = root / "sibling"
    victim.mkdir(parents=True)
    (victim / "keep.txt").write_text("keep me", encoding="utf-8")
    target = root / "my-tool"
    target.mkdir()
    (target / "stale.txt").write_text("replace me", encoding="utf-8")

    templates = Path(__file__).resolve().parent.parent / "templates"
    rc = scaffold.main(
        [
            "--type",
            "python-project",
            "--name",
            "my-tool",
            "--dest-root",
            str(root),
            "--templates-root",
            str(templates),
            "--force",
        ]
    )
    assert rc == 0
    assert not (target / "stale.txt").exists()  # replaced
    assert (victim / "keep.txt").read_text(encoding="utf-8") == "keep me"  # untouched


# --- package-name derivation (unchanged behaviour, pinned) ----------------
def test_to_package_normalizes():
    assert scaffold.to_package("my-tool") == "my_tool"
    assert scaffold.to_package("My Tool 2") == "my_tool_2"
    assert scaffold.to_package("2fast") == "pkg_2fast"
