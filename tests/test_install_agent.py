"""Tests for install-agent.py's naming and target-path logic.

These cover the two ways a supply-chain install can go wrong before any content
is even written: landing a skill somewhere nothing loads it, and letting a
hostile `--name` steer the write outside its directory.

The script name has a hyphen, so it's loaded via importlib.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(modname: str, filename: str):
    spec = importlib.util.spec_from_file_location(modname, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ia = _load("install_agent_mod", "install-agent.py")


# --- target_paths: a skill is a directory, not a flat file -----------------
def test_skill_installs_as_directory_with_skill_md():
    """Claude Code only loads skills/<name>/SKILL.md, and bootstrap's copier
    globs `*/SKILL.md`. A flat skills/<name>.md is registered but never loaded."""
    repo_path, global_path = ia.target_paths("skill", "pdf-tools")
    assert repo_path.parent.name == "pdf-tools"
    assert repo_path.name == "SKILL.md"
    assert global_path.parent.name == "pdf-tools"
    assert global_path.name == "SKILL.md"
    # and it lands under ~/.claude/skills, not ~/.claude/commands
    assert global_path.parent.parent.name == "skills"


@pytest.mark.parametrize("kind", ["agent", "command"])
def test_agents_and_commands_stay_flat(kind):
    repo_path, _ = ia.target_paths(kind, "my-thing")
    assert repo_path.name == "my-thing.md"


# --- install and update must agree on where things go ----------------------
ua = _load("update_agents_layout_mod", "update-agents.py")


@pytest.mark.parametrize("kind", ["agent", "command", "skill"])
def test_install_and_update_resolve_identical_paths(kind):
    """The defect this locks out: install moved skills to `<name>/SKILL.md`
    while update kept writing them flat, so an update wrote vetted content to a
    path nothing loads and then advanced the registry pin — reporting the skill
    current while the loaded copy stayed stale."""
    assert ia.target_paths(kind, "thing") == ua.layout.target_paths(kind, "thing")


def test_update_accepts_the_registrys_plural_kinds():
    """update-agents iterates 'agents'/'commands'/'skills'; install uses the
    singular. Both must land on the same layout."""
    assert ua.layout.target_paths("skills", "thing") == ia.target_paths("skill", "thing")
    assert ua.layout.target_paths("agents", "thing") == ia.target_paths("agent", "thing")


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError):
        ua.layout.target_paths("widgets", "thing")


# --- safe_name: the value reaches both the install and quarantine paths ----
@pytest.mark.parametrize("name", ["a", "my-agent", "agent_2", "pdf.tools", "x" * 64])
def test_plausible_names_accepted(name):
    assert ia.safe_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "../../evil",
        "../evil",
        "sub/dir",
        "sub\\dir",
        "/abs",
        "C:/abs",
        "..",
        "",
        "x" * 65,
        "sp ace",
        "-leading-dash",  # must start alphanumeric, so a flag-lookalike is out
        "évil",  # non-ASCII: homoglyphs must not reach a path
    ],
)
def test_unsafe_names_rejected(name):
    with pytest.raises(ValueError):
        ia.safe_name(name)


def test_traversal_name_cannot_escape_target_dir():
    """The regression this guards: `--name ../../x` writing outside the repo."""
    with pytest.raises(ValueError):
        ia.safe_name("../../../.claude/agents/pwned")


def test_interior_newline_rejected():
    """`$` matches before a final newline, so a `^...$` slug is not the anchor it
    looks like. fullmatch + \\Z is, and an interior newline is the case a trailing
    strip() cannot launder away."""
    with pytest.raises(ValueError):
        ia.safe_name("ev\nil")
    with pytest.raises(ValueError):
        ia.safe_name("evil\nmore")


def test_trailing_whitespace_is_stripped_not_smuggled():
    assert ia.safe_name("evil\n") == "evil"
    assert ia.safe_name(" evil ") == "evil"


@pytest.mark.parametrize("name", ["con", "nul", "aux", "prn", "com1", "lpt9", "nul.md"])
def test_windows_reserved_device_names_rejected(name):
    """A skill named `nul` makes mkdir() succeed silently and the SKILL.md write
    inside it fail with an unhandled traceback. The name can come from upstream."""
    with pytest.raises(ValueError):
        ia.safe_name(name)


def test_names_are_lowercased_not_rejected():
    """Upstream repos are inconsistent about case, and these names become paths
    on a case-insensitive filesystem where the two spellings are one file."""
    assert ia.safe_name("Data-Engineer") == "data-engineer"
    assert ia.safe_name("  React-Specialist  ") == "react-specialist"


def test_uppercase_upstream_filename_still_installs():
    """Regression: lowercasing only in the skill branch made `Data-Engineer.md`
    exit 1 as an 'unsafe name' where it used to install fine."""
    assert ia.safe_name(ia.default_name("Data-Engineer.md", "agents/Data-Engineer.md"))


# --- detect_type: "skill" used to be unreachable for every .md file --------
def test_skill_md_filename_detected_as_skill():
    assert ia.detect_type("body", "SKILL.md") == "skill"
    assert ia.detect_type("body", "skill.md") == "skill"


def test_skills_directory_in_path_detected_as_skill():
    assert ia.detect_type("body", "thing.md", "repo/skills/thing/thing.md") == "skill"


def test_frontmatter_with_tools_detected_as_agent():
    content = "---\nname: x\ntools:\n  - Read\n---\nBody\n"
    assert ia.detect_type(content, "x.md") == "agent"


def test_plain_markdown_detected_as_command():
    assert ia.detect_type("# Do a thing\n", "do-thing.md") == "command"


# --- default_name: every skill file is literally named SKILL.md ------------
def test_skill_name_comes_from_its_directory():
    assert ia.default_name("SKILL.md", "skills/pdf-tools/SKILL.md") == "pdf-tools"


def test_skill_name_falls_back_to_stem_without_a_parent_dir():
    assert ia.default_name("SKILL.md", "SKILL.md") == "SKILL"


def test_non_skill_name_is_the_filename_stem():
    assert ia.default_name("my-agent.md", "agents/my-agent.md") == "my-agent"
