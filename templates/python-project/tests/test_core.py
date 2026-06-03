"""Tests for pkgname.core."""

import pytest

from pkgname.core import slugify


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hello World", "hello-world"),
        ("  Phonk_Shinobi  ", "phonk-shinobi"),
        ("a--b__c", "a-b-c"),
        ("Deja vu!", "deja-vu"),
    ],
)
def test_slugify(raw, expected):
    assert slugify(raw) == expected


def test_slugify_empty():
    assert slugify("   ") == ""
