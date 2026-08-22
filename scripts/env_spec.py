#!/usr/bin/env python3
"""What a project's `.env.example` declares, and what `.env` is missing.

One implementation, two callers: `project_doctor.py` imports `gaps()`, and
`skills/secrets/secrets-doctor.sh` shells out to the CLI below. They used to
parse the format independently, and a test comparing them immediately found a
disagreement — the bash side excluded `optional` keys from its per-key loop but
not `one-of` members, so it reported the unchosen member missing. That is the
exact defect the markers exist to prevent, reintroduced one layer down.

## The format

    KEY=placeholder                 required: must exist in .env
    #! optional: A, B               declared but never required
    #! one-of: A, B                 satisfied by any one member

Both markers exist because a plain set difference cannot tell "not configured
yet" from a deliberate choice:

  * `optional` — reserved names a project documents for external tools it does
    not itself read. The four multi-LLM keys here are consumed by nothing in
    this repo; they exist so whichever assistant you use finds its key.
  * `one-of` — alternatives for a single job. Pick Groq *or* Anthropic; the
    unused one is not missing, and no edit short of pasting a key you have
    chosen not to use would clear the warning.

A warning whose only remedy is unavailable is one the reader learns to skip.

Usage:
    uv run --no-project python scripts/env_spec.py               # cwd
    uv run --no-project python scripts/env_spec.py --dir PATH
Exit: 0 no gaps, 1 gaps found (one per line on stdout), 2 nothing to compare.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ONE_OF_RE = re.compile(r"^#!\s*one-of:\s*(.+)$", re.M)
OPTIONAL_RE = re.compile(r"^#!\s*optional:\s*(.+)$", re.M)

NOTHING_TO_COMPARE = 2


def declared_keys(text: str) -> set[str]:
    """Assignment names in an env file. Comments (including `#!`) are not keys."""
    out = set()
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            out.add(line.split("=", 1)[0].strip())
    return out


def _listed(pattern: re.Pattern[str], text: str) -> list[list[str]]:
    return [[k.strip() for k in m.group(1).split(",") if k.strip()] for m in pattern.finditer(text)]


def gaps(example: Path, env: Path) -> list[str]:
    """Keys `.env.example` requires that `.env` does not supply.

    A one-of group that no member satisfies is reported once, as the choice it
    is, rather than as N independent missing keys.
    """
    example_text = example.read_text(encoding="utf-8", errors="replace")
    present = declared_keys(env.read_text(encoding="utf-8", errors="replace"))

    groups = _listed(ONE_OF_RE, example_text)
    optional = {k for group in _listed(OPTIONAL_RE, example_text) for k in group}
    grouped = {k for g in groups for k in g}

    missing = sorted(declared_keys(example_text) - present - grouped - optional)
    for g in groups:
        if not present.intersection(g):
            missing.append("one of " + "|".join(g))
    return missing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, default=Path("."), help="project root (default: cwd)")
    args = ap.parse_args(argv)

    example, env = args.dir / ".env.example", args.dir / ".env"
    if not example.is_file() or not env.is_file():
        return NOTHING_TO_COMPARE
    found = gaps(example, env)
    for key in found:
        print(key)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
