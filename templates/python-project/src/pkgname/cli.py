#!/usr/bin/env python3
"""Command-line entry point for the pkgname package."""

from __future__ import annotations

import argparse

from pkgname.core import slugify


def main(argv: list[str] | None = None) -> int:
    """Parse args and print the kebab-case slug of the given text."""
    parser = argparse.ArgumentParser(description="Slugify text to kebab-case.")
    parser.add_argument("text", help="text to slugify")
    args = parser.parse_args(argv)
    print(slugify(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
