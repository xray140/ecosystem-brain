"""The secret-file deny list must exempt `.env.example` and nothing else.

`.env.example` is the committed, placeholder-only template every scaffolded
project ships, and the file `project_doctor` diffs `.env` against. The old
`.env.*` catch-all matched it, which made the one file meant to be edited the
one file that could not be read.

Narrowing a deny list is the kind of change that is easy to over-do quietly, so
both halves are pinned here: the exemption, and the secrets that must stay
denied regardless.
"""

from __future__ import annotations

import fnmatch

import pytest

import bootstrap as bs

DENY = bs.PERMISSIONS["deny"]


def _denied(path: str) -> bool:
    """True if any Read(...) deny rule matches this path.

    fnmatch is an approximation of the harness matcher, adequate for asserting
    which patterns are present: `**/` is normalised to a prefix wildcard.
    """
    for rule in DENY:
        if not rule.startswith("Read("):
            continue
        pat = rule[len("Read(") : -1]
        for candidate in {pat, pat.replace("./", ""), pat.replace("**/", "*")}:
            if fnmatch.fnmatch(path, candidate) or fnmatch.fnmatch(path, f"*/{candidate}"):
                return True
    return False


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "sub/.env",
        ".env.local",
        "sub/.env.local",
        ".env.production.local",
        ".identity.local.env",
        "creds.local.env",
    ],
)
def test_secret_bearing_files_stay_denied(path):
    assert _denied(path), f"{path} must not be readable"


@pytest.mark.parametrize("path", [".env.example", "sub/.env.example"])
def test_the_committed_template_is_readable(path):
    assert not _denied(path), (
        f"{path} is the placeholder-only template meant to be edited — "
        "a catch-all that denies it defeats its purpose"
    )


def test_no_rule_reintroduces_the_catch_all():
    """`.env.*` is the specific pattern that swept in `.env.example`. If it comes
    back, the exemption above is silently undone."""
    assert "Read(./.env.*)" not in DENY
    assert "Read(**/.env.*)" not in DENY


def test_deny_still_covers_the_documented_secret_files():
    """AGENTS.md states secrets live in `.env` / `.identity.local.env` only. The
    enumeration replaced a catch-all, so it must at minimum cover what the
    written policy names."""
    assert _denied(".env")
    assert _denied(".identity.local.env")


# --- destructive commands, both spellings ----------------------------------

ASK = bs.PERMISSIONS["ask"]


@pytest.mark.parametrize("verb", ["push", "reset --hard", "clean"])
def test_the_git_c_spelling_is_gated_too(verb):
    """Patterns match from the start of the command, so `Bash(git push*)` does
    not cover `git -C <path> push` — the form that acts on a sibling repo.

    The gap did not make the wider action safer: it fell through to the
    classifier and hard-failed, while the narrower spelling merely prompted.
    """
    plain = next(r for r in ASK if r.startswith(f"Bash(git {verb}"))
    scoped = f"Bash(git -C * {verb}*)"
    assert plain in ASK
    assert scoped in ASK, f"{verb} is gated as `git {verb}` but not as `git -C … {verb}`"


def test_nothing_destructive_is_auto_allowed():
    """`ask` prompts, `allow` does not. The spelling that can target any repo on
    disk must never be the one that skips the prompt."""
    allow = bs.PERMISSIONS.get("allow", [])
    for rule in allow:
        assert "push" not in rule
        assert "reset" not in rule
        assert "clean" not in rule
        assert "rm " not in rule
