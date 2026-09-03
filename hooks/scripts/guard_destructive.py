#!/usr/bin/env python3
"""PreToolUse(Bash): hard-block catastrophic commands.

Softer confirmations come from `permissions.ask`; this refuses outright.

Why this is Python and not a `case` statement. The previous shell version
matched literal substrings, which failed in both directions:

  * False negatives — only exact spacing was caught. `rm  -rf /`, `rm -r -f /`
    and `rm --recursive --force /` all sailed through.
  * False positives — the home-directory patterns were prefixes, so
    `rm -rf ~/.claude/skills/one-thing` was refused as "a catastrophic delete
    of root/home". A guard that blocks ordinary work gets worked around, which
    costs more than it protects.

So: tokenize, normalize the flags, and compare each *target* against the set of
paths that are actually catastrophic — never a prefix of one.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Deleting any of these recursively is unrecoverable. Compared exactly, after
# normalization — `/etc` is here, `/etc/myapp/cache` is ordinary work.
CATASTROPHIC = {
    "/",
    "~",
    "$HOME",
    "${HOME}",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/var",
    "/boot",
    "/sys",
    "/proc",
    "/root",
    "/home",
    "/opt",
    "C:",
    "C:/",
    "C:\\",
    "/c",
    "/c/",
    "/c/Windows",
    "/c/Users",
}

# A bare wildcard as the target of a recursive delete: `rm -rf *`.
WILDCARDS = {"*", "*/", "./*", ".", ".."}

LONG_FLAGS = {"--recursive": "r", "--force": "f", "--dir": "d"}


def statements(command: str) -> list[str]:
    """Split a command line into the statements it would actually run.

    `safe_thing && rm -rf /` is not a safe command; each segment is judged.
    """
    return [s for s in re.split(r"&&|\|\||;|\n|\|", command) if s.strip()]


def _tokens(statement: str) -> list[str]:
    try:
        return shlex.split(statement)
    except ValueError:  # unbalanced quotes — fall back to whitespace split
        return statement.split()


def rm_targets(tokens: list[str]) -> tuple[set[str], set[str]]:
    """(flags, targets) for an `rm` invocation. Empty flags if not an rm."""
    if not tokens or tokens[0] != "rm":
        return set(), set()
    flags: set[str] = set()
    targets: set[str] = set()
    for tok in tokens[1:]:
        if tok in LONG_FLAGS:
            flags.add(LONG_FLAGS[tok])
        elif tok.startswith("--"):
            continue
        elif tok.startswith("-") and len(tok) > 1:
            flags.update(tok[1:])  # -rf and -r -f both land as {r, f}
        else:
            targets.add(tok)
    return flags, targets


def _normalize_target(target: str) -> str:
    """Strip a trailing slash so `/etc/` and `/etc` compare equal (but keep a
    lone `/`), and collapse `~/` to `~` only when nothing follows it."""
    t = target.strip().strip('"').strip("'")
    if len(t) > 1:
        t = t.rstrip("/\\") or t[0]
    return t


def check_rm(statement: str) -> str | None:
    """Reason to block this rm, or None."""
    tokens = _tokens(statement)
    flags, targets = rm_targets(tokens)
    if "r" not in flags:  # non-recursive rm cannot wipe a tree
        return None
    for raw in targets:
        target = _normalize_target(raw)
        if target in CATASTROPHIC:
            return f"refusing recursive delete of {target!r} — a catastrophic target"
        if target in WILDCARDS:
            return f"refusing recursive delete of the bare wildcard {target!r}"
    return None


def check_git_push(statement: str) -> str | None:
    """Reason to block this push, or None. Force-pushing a protected branch
    rewrites history others may have pulled."""
    tokens = _tokens(statement)
    if len(tokens) < 2 or tokens[0] != "git" or tokens[1] != "push":
        return None
    protected = {"main", "master"}
    forced = any(t in ("--force", "-f") or t.startswith("--force=") for t in tokens)
    # `--force-with-lease` is the safe form: it refuses if the remote moved.
    if any(t.startswith("--force-with-lease") for t in tokens):
        forced = False
    for tok in tokens[2:]:
        # `git push origin +main` forces via the refspec, with no --force flag.
        if tok.startswith("+") and tok.lstrip("+").split(":")[-1] in protected:
            return f"refusing forced refspec push to {tok.lstrip('+')!r}"
        if forced and tok.split(":")[-1] in protected:
            return f"refusing force-push to {tok!r}"
    return None


def check(command: str) -> str | None:
    """The reason to block `command`, or None to allow it."""
    for statement in statements(command):
        for reason in (check_rm(statement), check_git_push(statement)):
            if reason:
                return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # unparseable input is not grounds to block a command
    command = (payload.get("tool_input") or {}).get("command") or ""
    reason = check(command)
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
