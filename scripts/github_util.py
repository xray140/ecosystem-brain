#!/usr/bin/env python3
"""Shared GitHub helpers for the agent supply chain (install + update).

Design:
  - Commit-SHA resolution goes through the `gh` CLI (same as catalog.py), so it
    reuses the user's `gh auth login` token. No secret handling lives here.
  - Raw file content is fetched over https from raw.githubusercontent.com, which
    is public and works unauthenticated — and crucially accepts a commit SHA in
    place of a branch, so a pinned install fetches immutable content.

Pinning model: record the commit SHA the content was vetted at. A mutable branch
(`main`) can be force-pushed or moved; a SHA can't. Updates re-resolve the tip,
re-scan the new content, and only then advance the pin.
"""

from __future__ import annotations

import hashlib
import subprocess
import urllib.parse
import urllib.request


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def is_github_source(source: str) -> bool:
    return source.startswith(("http", "github:"))


def parse_source(source: str) -> tuple[str, str] | None:
    """Return (repo, path) from a source string, or None if not a GitHub file.

    Accepts:
      github:user/repo/path/to/file.md
      https://raw.githubusercontent.com/user/repo/<ref>/path/to/file.md
    """
    if source.startswith("github:"):
        parts = source.removeprefix("github:").split("/", 2)  # user, repo, path
        if len(parts) < 3:
            return None
        return f"{parts[0]}/{parts[1]}", parts[2]
    prefix = "https://raw.githubusercontent.com/"
    if source.startswith(prefix):
        parts = source.removeprefix(prefix).split("/", 3)  # user, repo, ref, path
        if len(parts) < 4:
            return None
        return f"{parts[0]}/{parts[1]}", parts[3]
    return None


def raw_url(repo: str, path: str, ref: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def compare_url(repo: str, old: str, new: str) -> str:
    return f"https://github.com/{repo}/compare/{old}...{new}"


def short(sha: str | None) -> str:
    return sha[:7] if sha else "?"


def resolve_commit(repo: str, ref: str = "main") -> str | None:
    """Latest commit SHA on `ref` of `repo`, via gh. None if gh is unavailable
    or the call fails — callers then fall back to the mutable ref.
    """
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/{ref}", "--jq", ".sha"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8", errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


# Only these hosts serve raw file content for the sources this tool installs
# from. Anything else is not a supply chain we vetted.
ALLOWED_HOSTS = frozenset(
    {
        "raw.githubusercontent.com",
        "gist.githubusercontent.com",
        "objects.githubusercontent.com",  # where raw.* redirects large blobs
    }
)

# An agent/skill definition is prose. A megabyte is already absurd for one, and
# the cap keeps a hostile or mistaken URL from reading an unbounded body into
# memory before anything gets to inspect it.
MAX_FETCH_BYTES = 1_000_000


def check_url(url: str) -> None:
    """Reject anything that is not an https URL on an allowed host.

    urllib's opener honours whatever scheme it is handed, so without this
    `--url file:///…/.env` reads a local secret and hands it to the installer as
    "content to install" — the scanner and the SHA pinning downstream are both
    irrelevant if the fetch itself can be pointed at the filesystem.
    """
    parts = urllib.parse.urlparse(url)
    if parts.scheme != "https":
        raise ValueError(
            f"refusing non-https URL ({parts.scheme or 'no'} scheme): {url}"
        )
    if parts.hostname not in ALLOWED_HOSTS:
        raise ValueError(
            f"refusing host {parts.hostname!r} — allowed: {', '.join(sorted(ALLOWED_HOSTS))}"
        )


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-apply check_url on every hop, so a redirect cannot leave the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url: str, max_bytes: int = MAX_FETCH_BYTES) -> str:
    """Fetch raw text over https from an allowed host.

    Decodes strictly: a definition that is not valid UTF-8 is malformed, and
    silently replacing the undecodable bytes would hand the scanner different
    content from what was actually served.
    """
    check_url(url)
    opener = urllib.request.build_opener(_CheckedRedirect)
    with opener.open(url, timeout=15) as r:
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"refusing response larger than {max_bytes} bytes: {url}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"content is not valid UTF-8: {url}") from e
