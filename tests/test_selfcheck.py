"""Tests for selfcheck's agent-frontmatter lint."""

from __future__ import annotations

import selfcheck as sc

GOOD = """---
name: demo
description: Does a thing. Use proactively when needed.
tools:
  - Read
model: haiku
---
Body.
"""


def test_conformant_agent_has_no_problems():
    assert sc.frontmatter_problems(GOOD) == []


def test_full_model_id_is_accepted():
    assert (
        sc.frontmatter_problems(GOOD.replace("model: haiku", "model: claude-fable-5"))
        == []
    )


def test_missing_frontmatter_flagged():
    assert sc.frontmatter_problems("no frontmatter here") == ["missing frontmatter"]


def test_missing_keys_flagged():
    text = "---\nname: x\n---\nBody.\n"
    problems = sc.frontmatter_problems(text)
    assert "missing 'description:'" in problems
    assert "missing 'tools:'" in problems
    assert "missing 'model:'" in problems


def test_unknown_model_flagged():
    problems = sc.frontmatter_problems(GOOD.replace("model: haiku", "model: gpt-5"))
    assert any("unknown model" in p for p in problems)


def test_fable_alias_accepted():
    assert sc.frontmatter_problems(GOOD.replace("model: haiku", "model: fable")) == []
