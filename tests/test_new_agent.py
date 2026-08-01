"""Tests for the recruiter — new_agent.py composes agents to standard."""

from __future__ import annotations

import new_agent as na

import scan_agent as sa


def test_compose_has_required_frontmatter_and_workflow():
    md = na.compose_agent(
        "doc-linter",
        "Lints docs. Use proactively before a docs PR.",
        "You are a documentation linter.",
        ["Read", "Grep", "Glob"],
        steps=["Find changed docs", "Check links"],
        returns="a list of broken links",
    )
    assert "name: doc-linter" in md
    assert "model: inherit" in md  # explicit grant by default
    assert "  - Read" in md and "  - Grep" in md
    assert "When invoked:" in md
    assert "1. Find changed docs" in md
    assert "Return: a list of broken links." in md


def test_composed_agent_scans_clean():
    md = na.compose_agent(
        "safe-agent",
        "Does a thing. Use when needed.",
        "You are a focused agent.",
        ["Read", "Grep"],
    )
    assert sa.worst(sa.scan(md)) == "CLEAN"


def test_compose_uses_placeholder_steps_by_default():
    md = na.compose_agent("x", "d. use it", "role", ["Read"])
    assert "1. ..." in md


def test_validate_rejects_non_kebab_name():
    problems = na.validate("Bad Name", ["Read"], "inherit")
    assert any("kebab-case" in p for p in problems)


def test_validate_rejects_unknown_tool():
    problems = na.validate("ok-name", ["Read", "Nuke"], "inherit")
    assert any("unknown tool" in p for p in problems)


def test_validate_rejects_empty_tools():
    assert any("at least one tool" in p for p in na.validate("ok", [], "inherit"))


def test_validate_rejects_bad_model():
    assert any("model" in p for p in na.validate("ok", ["Read"], "gpt4"))


def test_validate_accepts_clean_input():
    assert na.validate("good-name", ["Read", "Grep", "Glob"], "inherit") == []
