"""Tests for the shared GitHub helpers (supply-chain pinning)."""

from __future__ import annotations

import pytest

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


# --- fetch allowlist ------------------------------------------------------
# The fetch is upstream of every other control: the scanner and the SHA pinning
# are irrelevant if the fetch itself can be pointed at the local filesystem.


def test_raw_github_url_accepted():
    gh.check_url("https://raw.githubusercontent.com/u/r/abc/a.md")
    gh.check_url("https://gist.githubusercontent.com/u/id/raw/a.md")


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Users/me/.env",
        "file:///etc/passwd",
        "ftp://example.com/a.md",
        "http://raw.githubusercontent.com/u/r/abc/a.md",  # plaintext downgrade
        "data:text/plain,hello",
    ],
)
def test_non_https_schemes_refused(url):
    with pytest.raises(ValueError, match="non-https"):
        gh.check_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/a.md",
        "https://raw.githubusercontent.com.evil.com/a.md",  # suffix lookalike
        "https://notraw.githubusercontent.com/a.md",
        "https://github.com/u/r/blob/main/a.md",  # HTML page, not raw content
    ],
)
def test_hosts_outside_the_allowlist_refused(url):
    with pytest.raises(ValueError, match="refusing host"):
        gh.check_url(url)


def test_userinfo_cannot_spoof_the_host():
    """`https://raw.githubusercontent.com@evil.com/a.md` has hostname evil.com —
    parsing must key on the real host, not the visible prefix."""
    with pytest.raises(ValueError, match="refusing host"):
        gh.check_url("https://raw.githubusercontent.com@evil.com/a.md")


def test_fetch_refuses_bad_url_before_opening_anything(monkeypatch):
    """check_url must run before any network/filesystem access."""

    def explode(*a, **k):
        raise AssertionError("opener was invoked for a rejected URL")

    monkeypatch.setattr(gh.urllib.request, "build_opener", explode)
    with pytest.raises(ValueError):
        gh.fetch_url("file:///C:/Users/me/.env")


def test_oversized_response_refused(monkeypatch):
    class _Resp:
        def read(self, n):
            return b"x" * n  # always returns the full ask -> over the cap

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        gh.urllib.request, "build_opener", lambda *a: type("O", (), {"open": lambda s, u, timeout: _Resp()})()
    )
    with pytest.raises(ValueError, match="larger than"):
        gh.fetch_url("https://raw.githubusercontent.com/u/r/abc/a.md", max_bytes=10)


def test_non_utf8_content_refused(monkeypatch):
    class _Resp:
        def read(self, n):
            return b"\xff\xfe not utf-8"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        gh.urllib.request, "build_opener", lambda *a: type("O", (), {"open": lambda s, u, timeout: _Resp()})()
    )
    with pytest.raises(ValueError, match="not valid UTF-8"):
        gh.fetch_url("https://raw.githubusercontent.com/u/r/abc/a.md")


def test_fetch_returns_decoded_text(monkeypatch):
    class _Resp:
        def read(self, n):
            return "# agent\nbody é\n".encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        gh.urllib.request, "build_opener", lambda *a: type("O", (), {"open": lambda s, u, timeout: _Resp()})()
    )
    assert gh.fetch_url("https://raw.githubusercontent.com/u/r/abc/a.md") == "# agent\nbody é\n"
