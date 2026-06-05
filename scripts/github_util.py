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
            encoding="utf-8",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310
        return r.read().decode()
