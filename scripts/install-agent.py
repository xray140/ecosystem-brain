#!/usr/bin/env python3
"""Install an agent, skill, or command from a GitHub URL or local path.

Usage:
    # Install from a GitHub raw URL
    uv run python scripts/install-agent.py --url https://raw.githubusercontent.com/user/repo/main/agents/my-agent.md

    # Install from a GitHub repo (sparse-fetches a single file)
    uv run python scripts/install-agent.py --repo user/repo --path agents/my-agent.md

    # Install from a local file (copies + registers)
    uv run python scripts/install-agent.py --file /path/to/my-agent.md --type agent

    # List installed
    uv run python scripts/install-agent.py --list
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode accented paths
# or unicode markers. Force UTF-8 so output never crashes the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    # Errors carry the same accented paths and em-dashes as normal output; a
    # cp1252 stderr mangles them (or crashes the run) exactly the same way.
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Local modules (same dir): security scanner, GitHub helpers, install layout.
sys.path.insert(0, str(Path(__file__).parent))
import registry_io

import github_util as gh
import layout
from scan_agent import format_report, quarantine, scan, worst

REPO_ROOT = Path(__file__).parent.parent
REGISTRY_DIR = REPO_ROOT / "registry"
INSTALLED_FILE = REGISTRY_DIR / "installed.json"
# Install layout and name validation live in layout.py — update-agents.py reads
# the same rules, so the two cannot drift into writing to different places.
TYPE_DIRS = layout.TYPE_DIRS
safe_name = layout.safe_name
target_paths = layout.target_paths


def load_installed() -> dict:
    """Merged view of the registry — see registry_io for the shared/local split."""
    return registry_io.load(INSTALLED_FILE)


def save_installed(data: dict) -> None:
    """Writes the tracked half and this machine's half; callers pass the merge."""
    registry_io.save(data, INSTALLED_FILE)


def detect_type(content: str, filename: str, path: str = "") -> str:
    """Guess type from filename, source path, then frontmatter.

    Filename first: upstream skills are always `SKILL.md`, and that signal is
    unambiguous. The old order checked `.md` before anything skill-shaped, so
    "skill" was unreachable for every markdown file — i.e. always.
    """
    if filename.lower() == "skill.md" or "/skills/" in f"/{path.strip('/')}/":
        return "skill"
    if "tools:" in content and "---" in content:
        return "agent"
    return "command"


def default_name(filename: str, path: str = "") -> str:
    """Name to install under when --name is absent.

    For a skill the filename is always the literal `SKILL.md`, so the stem would
    name every skill "SKILL". The identity lives in the containing directory —
    `skills/pdf-tools/SKILL.md` is the skill `pdf-tools`.
    """
    if filename.lower() == "skill.md":
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if len(parts) >= 2:
            return parts[-2]
    return Path(filename).stem


def install_content(
    content: str,
    name: str,
    item_type: str,
    source: str,
    ref: str | None = None,
    commit: str | None = None,
) -> None:
    name = safe_name(name)
    repo_path, global_path = target_paths(item_type, name)
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.parent.mkdir(parents=True, exist_ok=True)

    # .gitattributes pins *.md to eol=lf. Two distinct sources of CRLF to kill:
    # text mode translating \n on Windows (newline="\n"), and upstream content
    # already shipping \r\n (the .replace). Either one dirties git status.
    repo_path.write_text(content.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    shutil.copy2(repo_path, global_path)

    # Provenance: ref (branch) + commit (immutable SHA the content was vetted at).
    prov = {k: v for k, v in (("ref", ref), ("commit", commit)) if v}
    installed = load_installed()
    key = f"{item_type}s"
    entries = installed.setdefault(key, [])
    today = datetime.now(UTC).date().isoformat()
    for entry in entries:  # update in place if already present
        if entry["name"] == name:
            entry.update({"source": source, "hash": gh.md5(content), "installed_at": today})
            entry.update(prov)
            break
    else:
        entries.append(
            {
                "name": name,
                "source": source,
                "hash": gh.md5(content),
                "installed_at": today,
                "global_path": str(global_path),
                **prov,
            }
        )
    save_installed(installed)
    pin = f"  @ {gh.short(commit)}" if commit else ""
    print(f"[ok] installed {item_type} '{name}' -> {global_path}{pin}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--url", help="Raw GitHub URL to a markdown file")
    ap.add_argument("--repo", help="GitHub repo (user/repo)")
    ap.add_argument("--path", help="Path within repo (used with --repo)")
    ap.add_argument("--branch", default="main", help="Branch (default: main)")
    ap.add_argument("--file", help="Local file path")
    ap.add_argument(
        "--type", choices=["agent", "command", "skill"], help="Override type detection"
    )
    ap.add_argument("--name", help="Override name (default: filename stem)")
    ap.add_argument("--list", action="store_true", help="List installed items")
    ap.add_argument(
        "--force", action="store_true", help="install even if the security scan flags HIGH risk"
    )
    args = ap.parse_args(argv)

    if args.list:
        data = load_installed()
        for kind in ("agents", "commands", "skills"):
            items = data.get(kind, [])
            if items:
                print(f"\n{kind}:")
                for item in items:
                    print(
                        f"  {item['name']:30s}  source={item['source']}  "
                        f"installed={item.get('installed_at', '?')}"
                    )
        return 0

    ref = commit = None
    if args.url:
        content = gh.fetch_url(args.url)
        src_path = urllib.parse.urlparse(args.url).path
        filename = src_path.rstrip("/").split("/")[-1]
        source = args.url
    elif args.repo and args.path:
        # Pin: resolve the branch tip to a commit SHA, then fetch the file AT that
        # SHA so the content is immutable (a moved/force-pushed branch can't swap
        # what we vetted). Fall back to the branch if gh can't resolve.
        ref = args.branch
        commit = gh.resolve_commit(args.repo, ref)
        if not commit:
            print(
                f"[warn] could not resolve a commit SHA for {args.repo}@{ref} "
                "(gh missing or API call failed) — installing UNPINNED from the "
                "mutable branch. Re-run later to pin, or check `gh auth status`."
            )
        content = gh.fetch_url(gh.raw_url(args.repo, args.path, commit or ref))
        src_path = args.path
        filename = src_path.split("/")[-1]
        source = f"github:{args.repo}/{args.path}"
    elif args.file:
        content = Path(args.file).read_text(encoding="utf-8")
        src_path = Path(args.file).as_posix()
        filename = Path(args.file).name
        source = "local"
    else:
        ap.error("provide --url, --repo+--path, or --file")
        return 1

    item_type = args.type or detect_type(content, filename, src_path)
    try:
        # Validate before anything touches the filesystem — `name` is a path
        # component for both the install target and the quarantine file.
        name = safe_name(args.name or default_name(filename, src_path))
    except ValueError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    # Security gate — scan untrusted content before activating it.
    findings = scan(content)
    level = worst(findings)
    if findings:
        print(f"security scan ({level}):")
        print(format_report(findings))
    if level == "HIGH" and not args.force:
        q = quarantine(name, content, f"install blocked: HIGH risk from {source}")
        print(
            f"\n[BLOCKED] '{name}' has HIGH-risk content — refusing to install.\n"
            f"          Quarantined for review: {q}\n"
            f"          Source: {source}\n"
            f"          Re-run with --force only if you trust it."
        )
        return 2

    install_content(content, name, item_type, source, ref=ref, commit=commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
