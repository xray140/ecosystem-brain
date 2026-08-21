"""`.env.example` can offer a choice of key; satisfying it must be possible.

The defect: `env_gap` did a plain set difference, so an example offering a
provider choice — pick Groq *or* Anthropic — reported the unused one as missing
forever. There was no edit that cleared it short of storing a key you had
deliberately chosen not to use, and a warning you cannot clear is one you learn
to skip. `viral-videos-sm` sat in exactly that state.
"""

from __future__ import annotations

import project_doctor as pd
import pytest

EXAMPLE = """# script generation — pick ONE.
#! one-of: GROQ_API_KEY, ANTHROPIC_API_KEY
GROQ_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

YOUTUBE_API_KEY=your_key_here
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".env.example").write_text(EXAMPLE, encoding="utf-8")
    return tmp_path


def _env(project, body):
    (project / ".env").write_text(body, encoding="utf-8")
    return project


def test_either_member_satisfies_the_group(project):
    for chosen in ("GROQ_API_KEY", "ANTHROPIC_API_KEY"):
        _env(project, f"{chosen}=x\nYOUTUBE_API_KEY=y\n")
        assert pd.env_gap(project) == [], f"{chosen} should satisfy the group"


def test_the_unchosen_member_is_not_reported_as_missing(project):
    """The actual viral-videos-sm shape: Groq configured, Anthropic deliberately
    absent. Anthropic must not appear."""
    _env(project, "GROQ_API_KEY=x\nYOUTUBE_API_KEY=y\n")
    assert "ANTHROPIC_API_KEY" not in " ".join(pd.env_gap(project))


def test_neither_member_reports_once_as_a_choice(project):
    """Not two independent missing keys — one unmet choice."""
    _env(project, "YOUTUBE_API_KEY=y\n")
    gap = pd.env_gap(project)
    assert gap == ["one of GROQ_API_KEY|ANTHROPIC_API_KEY"]


def test_ungrouped_keys_are_still_reported(project):
    """The group must not become a way to silence everything around it."""
    _env(project, "GROQ_API_KEY=x\n")
    assert pd.env_gap(project) == ["YOUTUBE_API_KEY"]


def test_a_directive_line_is_not_itself_read_as_a_key(project):
    """`#! one-of: ...` contains a colon and words; it must not become a key."""
    _env(project, "GROQ_API_KEY=x\nYOUTUBE_API_KEY=y\n")
    assert pd.env_gap(project) == []


def test_an_example_without_directives_behaves_exactly_as_before(tmp_path):
    """No marker, no behaviour change — the plain set difference still holds."""
    (tmp_path / ".env.example").write_text("A=1\nB=2\n", encoding="utf-8")
    (tmp_path / ".env").write_text("A=1\n", encoding="utf-8")
    assert pd.env_gap(tmp_path) == ["B"]
