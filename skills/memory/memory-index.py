#!/usr/bin/env python3
"""Build memory/index.json from the frontmatter of every note in the vault.

Walks the memory/ vault, extracts simple YAML frontmatter (stdlib only — no
PyYAML dependency), collects [[wikilinks]] from each body, and writes a compact
manifest the agent loads instead of reading the whole vault.

`--check` compares the manifest on disk against a fresh build and exits
non-zero when they disagree. It used to print counts and return 0 whatever it
found, so nothing ever noticed the manifest going stale: on 2026-08-21 it had
been frozen for 18 days, listing a note that no longer existed and missing three
that did — while every check reported the vault healthy.

`--dry-run` is the older behaviour under an honest name: walk the vault, print
counts, write and judge nothing. `selfcheck` uses it to assert the indexer can
parse every note — a question that has an answer on a fresh clone, where the
manifest is gitignored and absent.

Usage:
    python skills/memory-index.py [--vault memory] [--out memory/index.json]
    python skills/memory-index.py --check      # gate: manifest vs vault
    python skills/memory-index.py --dry-run    # counts only, never fails on drift
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")


def parse_scalar(value: str):
    """Parse a minimal frontmatter value: flow list [a, b] or scalar."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip('"').strip("'") for v in inner.split(",")]
    return value.strip('"').strip("'")


def parse_frontmatter(text: str) -> dict:
    """Return the leading frontmatter block as a dict, or {} if absent."""
    m = FM_RE.match(text)
    if not m:
        return {}
    data: dict = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        data[key.strip()] = parse_scalar(raw)
    return data


def wikilinks(text: str) -> list[str]:
    """Unique [[wikilink]] targets, dropping any |alias part."""
    out: list[str] = []
    for raw in LINK_RE.findall(text):
        target = raw.split("|")[0].strip()
        if target and target not in out:
            out.append(target)
    return out


def link_basename(target: str) -> str:
    """Resolve a wikilink target to a note id, the way Obsidian does.

    `decisions/hook-format` -> `hook-format`; strips folder paths and any
    `#heading` / `^block` ref. So a path-qualified link resolves to its note
    instead of dangling as a phantom.
    """
    target = target.split("#", 1)[0].split("^", 1)[0]
    return target.rstrip("/").rsplit("/", 1)[-1].strip()


def build(vault: Path) -> dict:
    """Scan the vault and return the index structure.

    Links are resolved to real note ids (basename match, path-aware). A link to
    something that isn't a note is recorded under `unresolved` — surfaced, never
    faked into a graph edge — so dangling links are visible to the curator.
    """
    raw = []
    for path in sorted(vault.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        raw.append((path, parse_frontmatter(text), wikilinks(text)))
    ids = {path.stem for path, _, _ in raw}

    notes, edges, unresolved_total = [], [], 0
    for path, fm, links in raw:
        resolved: list[str] = []
        unresolved: list[str] = []
        for t in links:
            base = link_basename(t)
            if base in ids and base != path.stem:
                if base not in resolved:
                    resolved.append(base)
            elif base not in ids and t not in unresolved:
                unresolved.append(t)
        notes.append({
            "id": path.stem,
            "path": path.relative_to(vault).as_posix(),
            "type": fm.get("type", "note"),
            "status": fm.get("status"),
            "tags": fm.get("tags", []),
            "updated": fm.get("updated"),
            "links": resolved,
            "unresolved": unresolved,
        })
        edges.extend([path.stem, t] for t in resolved)
        unresolved_total += len(unresolved)

    by_type: dict[str, int] = {}
    for n in notes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1

    return {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "vault": vault.as_posix(),
        "counts": {
            "notes": len(notes), "by_type": by_type,
            "edges": len(edges), "unresolved": unresolved_total,
        },
        "notes": notes,
        "edges": edges,
    }


def compare(built: dict, existing: dict) -> list[str]:
    """Disagreements between a fresh build and the manifest on disk.

    Compared on the notes themselves, keyed by path. `generated` and `vault` are
    excluded on purpose: the timestamp always differs, and the vault path varies
    with how the script was invoked — neither says anything about whether the
    manifest describes the vault.

    The three findings this exists for, all present on 2026-08-21:
      phantom  — listed, but the file is gone (a note from an unmerged branch)
      unlisted — on disk, never indexed (every new maintenance report)
      stale    — indexed, but its frontmatter or links have since changed
    """
    fresh = {n["path"]: n for n in built.get("notes", [])}
    old = {n["path"]: n for n in existing.get("notes", []) if isinstance(n, dict) and "path" in n}
    problems = [f"phantom  {p} — listed in the manifest, not in the vault" for p in sorted(old.keys() - fresh.keys())]
    problems += [f"unlisted {p} — in the vault, missing from the manifest" for p in sorted(fresh.keys() - old.keys())]
    problems += [
        f"stale    {p} — indexed, but its frontmatter or links have changed"
        for p in sorted(fresh.keys() & old.keys())
        if fresh[p] != old[p]
    ]
    return problems


def check(index: dict, out: Path) -> int:
    """Gate: is `out` a faithful manifest of the vault we just walked?"""
    if not out.is_file():
        print(f"[!] no manifest at {out}")
        print("    build it: memory-index.py --vault <vault>")
        return 1
    try:
        existing = json.loads(out.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[!] manifest at {out} is unreadable: {exc}")
        return 1
    problems = compare(index, existing)
    if problems:
        print(f"[!] manifest disagrees with the vault — {len(problems)} finding(s):")
        for line in problems:
            print(f"    {line}")
        print("    refresh it: memory-index.py --vault <vault>")
        return 1
    print(f"[ok] manifest matches the vault ({index['counts']['notes']} notes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", default="memory", type=Path)
    ap.add_argument("--out", default=None, type=Path)
    ap.add_argument("--check", action="store_true",
                    help="compare the manifest against the vault; non-zero if they disagree")
    ap.add_argument("--dry-run", action="store_true",
                    help="walk the vault and print counts, writing and judging nothing")
    args = ap.parse_args(argv)

    if not args.vault.is_dir():
        print(f"[error] vault not found: {args.vault}", file=sys.stderr)
        return 1

    index = build(args.vault)
    out = args.out or args.vault / "index.json"
    # Two different questions, and conflating them broke a caller. --dry-run
    # asks "can the indexer walk this vault?" — it fails only when a note cannot
    # be parsed. --check asks "does the manifest still describe the vault?",
    # which needs a manifest to exist and so cannot speak for a fresh clone,
    # where `index.json` is gitignored and absent.
    if args.dry_run:
        print(json.dumps(index["counts"], indent=2))
        return 0
    if args.check:
        return check(index, out)

    out.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[ok] {index['counts']['notes']} notes -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
