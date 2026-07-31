#!/usr/bin/env python3
"""Build memory/index.json from the frontmatter of every note in the vault.

Walks the memory/ vault, extracts simple YAML frontmatter (stdlib only — no
PyYAML dependency), collects [[wikilinks]] from each body, and writes a compact
manifest the agent loads instead of reading the whole vault.

Usage:
    python skills/memory-index.py [--vault memory] [--out memory/index.json] [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
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
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vault": vault.as_posix(),
        "counts": {
            "notes": len(notes), "by_type": by_type,
            "edges": len(edges), "unresolved": unresolved_total,
        },
        "notes": notes,
        "edges": edges,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", default="memory", type=Path)
    ap.add_argument("--out", default=None, type=Path)
    ap.add_argument("--check", action="store_true",
                    help="print summary only, do not write")
    args = ap.parse_args(argv)

    if not args.vault.is_dir():
        print(f"[error] vault not found: {args.vault}", file=sys.stderr)
        return 1

    index = build(args.vault)
    if args.check:
        print(json.dumps(index["counts"], indent=2))
        return 0

    out = args.out or args.vault / "index.json"
    out.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[ok] {index['counts']['notes']} notes -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
