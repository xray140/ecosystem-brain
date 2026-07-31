#!/usr/bin/env python3
"""Generate a new project from a templates/ blueprint.

Copies templates/<type>/ to <dest-root>/<name>/, renames the placeholder
package `pkgname` to one derived from <name>, and substitutes the token
throughout. stdlib only.

Usage:
    uv run python scripts/scaffold.py --type python-project --name my-tool
    uv run python scripts/scaffold.py --type python-project --name my-tool \
        --dest-root /some/root --templates-root templates [--git] [--force]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOKEN = "pkgname"

# Where projects land when --dest-root is omitted. Mirrors init_project.py:
# the clone's parent, overridable by env. Never a hardcoded absolute path —
# this repo bootstraps from any location on any machine.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_ROOT = Path(os.environ.get("ECOSYSTEM_DEST_ROOT") or REPO_ROOT.parent)


def to_package(name: str) -> str:
    """Derive an importable package name from a project name."""
    pkg = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not pkg:
        return "pkg"
    if not pkg[0].isalpha():
        return f"pkg_{pkg}"
    return pkg


def substitute(root: Path, package: str, project: str) -> None:
    """Replace the placeholder token in every text file under root."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = text.replace(TOKEN, package)
        if path.name == "pyproject.toml":
            # keep the distribution name human-friendly (kebab) on the name line
            new = re.sub(r'(?m)^name = ".*"$', f'name = "{project}"', new, count=1)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--type", required=True, help="template name under --templates-root")
    ap.add_argument("--name", required=True, help="project name (kebab-case)")
    ap.add_argument("--templates-root", default="templates", type=Path)
    ap.add_argument("--dest-root", default=DEST_ROOT, type=Path)
    ap.add_argument("--git", action="store_true", help="git init + first commit")
    ap.add_argument("--force", action="store_true", help="overwrite if dest exists")
    args = ap.parse_args(argv)

    template = args.templates_root / args.type
    if not template.is_dir():
        print(f"[error] template not found: {template}", file=sys.stderr)
        return 1

    dest = args.dest_root / args.name
    if dest.exists():
        if not args.force:
            print(f"[error] destination exists: {dest} (use --force)", file=sys.stderr)
            return 1
        shutil.rmtree(dest)

    package = to_package(args.name)
    shutil.copytree(template, dest)

    # Overlay shared files (.vscode, etc.) from templates/_common into every project.
    common = args.templates_root / "_common"
    if common.is_dir():
        shutil.copytree(common, dest, dirs_exist_ok=True)

    src_pkg = dest / "src" / TOKEN
    if src_pkg.is_dir():
        src_pkg.rename(dest / "src" / package)

    substitute(dest, package, args.name)

    is_ts = (dest / "package.json").exists()

    if args.git:
        subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
        subprocess.run(["git", "add", "."], cwd=dest, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"feat: scaffold {args.name}"],
            cwd=dest, check=True,
        )

    print(f"[ok] {args.type} -> {dest}  (package: {package})")
    if is_ts:
        print("next: cd into it, then `npm install` && `npm test`")
    else:
        print("next: cd into it, then `uv sync` && `uv run pytest -q`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
