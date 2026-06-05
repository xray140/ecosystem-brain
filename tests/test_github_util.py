"""Tests for the shared GitHub helpers (supply-chain pinning)."""

from __future__ import annotations

import github_util as gh


def test_is_github_source():
    assert gh.is_github_source("github:user/repo/a.md")
    assert gh.is_github_source("https://raw.githubusercontent.com/u/r/main/a.md")
    assert not gh.is_github_source("local")


def test_parse_source_github_form():
    assert gh.parse_source("github:VoltAgent/awesome/categories/x/y.md") == (
        "VoltAgent/awesome",
        "categories/x/y.md",
    )


def test_parse_source_raw_url_form():
    url = "https://raw.githubusercontent.com/u/r/abc123/path/to/a.md"
    assert gh.parse_source(url) == ("u/r", "path/to/a.md")


def test_parse_source_rejects_non_github():
    assert gh.parse_source("local") is None
    assert gh.parse_source("github:tooShort") is None


def test_raw_url_uses_ref():
    assert (
        gh.raw_url("u/r", "p/a.md", "abc123")
        == "https://raw.githubusercontent.com/u/r/abc123/p/a.md"
    )


def test_compare_url():
    assert (
        gh.compare_url("u/r", "old", "new")
        == "https://github.com/u/r/compare/old...new"
    )


def test_short():
    assert gh.short("abcdef1234567890") == "abcdef1"
    assert gh.short(None) == "?"
    assert gh.short("") == "?"


def test_md5_stable():
    assert gh.md5("hello") == gh.md5("hello")
    assert gh.md5("a") != gh.md5("b")
