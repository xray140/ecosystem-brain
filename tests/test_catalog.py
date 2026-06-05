"""Tests for the pure tagging logic in catalog.py."""

from __future__ import annotations

import catalog


def test_infer_tags_keywords_and_category():
    tags = catalog.infer_tags("categories/02-language-specialists/react-specialist.md")
    assert "react" in tags
    assert "frontend" in tags  # react keyword expands to frontend
    assert "02-language-specialists" in tags  # category folder


def test_infer_tags_python():
    tags = catalog.infer_tags("categories/01-core-development/python-pro.md")
    assert "python" in tags
    assert "01-core-development" in tags


def test_infer_tags_returns_sorted_unique():
    tags = catalog.infer_tags("categories/01-core-development/api-graphql.md")
    assert tags == sorted(tags)
    assert len(tags) == len(set(tags))


def test_infer_tags_no_match_outside_categories():
    assert catalog.infer_tags("README.md") == []
