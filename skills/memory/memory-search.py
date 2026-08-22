#!/usr/bin/env python3
"""Local keyword search over the memory/ vault.

Embeds each note as a hashed bag-of-words vector and ranks queries by cosine
similarity. Embeddings are cached in a local SQLite DB and only recomputed when
a note's mtime changes. stdlib only (sqlite3 + math) — no numpy, no extra deps,
no server, no network.

What it matches: **wording, not meaning.** A query only finds a note if they
share vocabulary. This used to have an Ollama/nomic-embed-text backend that
matched meaning, removed in v4.8.0 — see [[decisions/no-ollama]]. Say "keyword
search" when describing this; the vault has already been burned once by an
index that advertised semantics it was not delivering.

Usage:
    python skills/memory-search.py index [--rebuild]
    python skills/memory-search.py search "what did we decide about render settings" -k 5
    python skills/memory-search.py status
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import sqlite3
import sys
from array import array
from pathlib import Path

FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
WORD_RE = re.compile(r"[a-z0-9]+")
HASH_DIM = 256


# --------------------------------------------------------------------- embedder
# The head of a note is the right thing to embed: frontmatter, title and opening
# paragraphs carry its topic, which is what recall matches on. The cap outlived
# the backend that forced it — nomic-embed-text answered 500 past ~2048 tokens,
# and `roadmap.md` (14k) once took the whole index build down with it — but the
# recall argument stands on its own, so the truncation stays.
MAX_EMBED_CHARS = 6000


class HashEmbedder:
    """Deterministic local embedder: hashed bag-of-words, L2-normalized."""

    name = "hash"

    def __init__(self, dim: int = HASH_DIM) -> None:
        self.dim = dim
        self.model = f"hash-{dim}"

    def embed(self, text: str) -> list[float]:
        """Return a normalized vector for one text."""
        vec = [0.0] * self.dim
        for tok in WORD_RE.findall(text[:MAX_EMBED_CHARS].lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)  # noqa: S324 (not security)
            vec[h % self.dim] += 1.0
        return _normalize(vec)


def _normalize(vec: list[float]) -> list[float]:
    """Scale a vector to unit length (no-op for the zero vector)."""
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (assumed normalized-ish)."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))  # lengths checked above
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------- vault io
def note_text(path: Path) -> str:
    """Note text with the frontmatter fence stripped, title prepended."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    body = FM_RE.sub("", raw, count=1)
    return f"{path.stem}\n{body}"


def snippet(path: Path, width: int = 160) -> str:
    """One-line preview of a note's body."""
    body = FM_RE.sub("", path.read_text(encoding="utf-8", errors="replace"), count=1)
    flat = " ".join(body.split())
    return flat[:width] + ("..." if len(flat) > width else "")


# --------------------------------------------------------------------- storage
def connect(db: Path) -> sqlite3.Connection:
    """Open the cache DB, creating the schema if needed."""
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS vec ("
        "path TEXT PRIMARY KEY, mtime REAL, model TEXT, dim INTEGER, data BLOB)"
    )
    return con


def pack(vec: list[float]) -> bytes:
    """Serialize a float vector to bytes."""
    return array("f", vec).tobytes()


def unpack(blob: bytes) -> list[float]:
    """Deserialize bytes back to a float list."""
    a = array("f")
    a.frombytes(blob)
    return list(a)


# --------------------------------------------------------------------- commands
def pick_embedder(args) -> HashEmbedder:
    """The vault's embedder. One indirection, kept deliberately.

    There is only one backend now, so this looks like a pointless wrapper. It
    is the seam every caller and test goes through, and it is what a second
    backend would slot into — the previous one was chosen here too.
    """
    return HashEmbedder()


def cmd_index(args) -> int:
    """Embed all notes whose mtime changed (or all, with --rebuild)."""
    vault = args.vault
    if not vault.is_dir():
        print(f"[error] vault not found: {vault}", file=sys.stderr)
        return 1
    emb = pick_embedder(args)
    con = connect(args.db)
    if args.rebuild:
        con.execute("DELETE FROM vec")
    cached = {
        row[0]: row[1]
        for row in con.execute("SELECT path, mtime FROM vec WHERE model=?", (emb.model,))
    }
    done = skipped = 0
    failed: list[str] = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        mtime = path.stat().st_mtime
        if cached.get(rel) == mtime:
            skipped += 1
            continue
        try:
            vec = emb.embed(note_text(path))
        except (OSError, KeyError, ValueError) as exc:
            # One unembeddable note must not abort the whole build. It used to:
            # a single 500 left the index untouched and stale, so the vault kept
            # answering from an old cache that nobody knew was there. The hash
            # embedder cannot fail that way, but an unreadable file still can.
            print(f"[warn] {rel}: {exc}", file=sys.stderr)
            failed.append(rel)
            continue
        con.execute(
            "INSERT OR REPLACE INTO vec(path, mtime, model, dim, data) VALUES (?,?,?,?,?)",
            (rel, mtime, emb.model, len(vec), pack(vec)),
        )
        done += 1
    con.commit()
    if failed:
        print(
            f"[warn] {len(failed)} note(s) could not be embedded and are NOT searchable: "
            + ", ".join(failed),
            file=sys.stderr,
        )
    con.close()
    print(f"[ok] embedded {done}, unchanged {skipped} (model: {emb.model}) -> {args.db}")
    return 0


def cmd_search(args) -> int:
    """Embed the query and print the top-k most similar notes."""
    emb = pick_embedder(args)
    con = connect(args.db)
    rows = con.execute(
        "SELECT path, data FROM vec WHERE model=?", (emb.model,)
    ).fetchall()
    con.close()
    if not rows:
        print(f"[error] no embeddings for model '{emb.model}'. Run: index", file=sys.stderr)
        return 1
    qv = emb.embed(args.query)
    scored = sorted(
        ((cosine(qv, unpack(blob)), path) for path, blob in rows),
        reverse=True,
    )
    for score, path in scored[: args.top]:
        print(f"{score:5.3f}  {path}")
        print(f"        {snippet(args.vault / path)}")
    return 0


def cmd_status(args) -> int:
    """Is the search index covering the vault, and with the intended embedder?

    Both had rotted here without a sound. The index held 24 of 28 notes while
    the README advertised semantic search it was not doing — nothing rebuilt
    it, so it kept answering from a cache built once, by hand. Degraded search
    returns *plausible* results, which is precisely why nobody noticed.
    """
    con = connect(args.db)
    rows = list(con.execute("SELECT model, dim, COUNT(*) FROM vec GROUP BY model, dim"))
    con.close()
    notes = len(list(args.vault.rglob("*.md"))) if args.vault.is_dir() else 0
    print(f"memory search index — vault has {notes} note(s)")
    if not rows:
        print("  [!!] index is empty — run: memory-search.py index")
        return 1

    problems = 0
    for model, dim, count in rows:
        missing = notes - count
        detail = f"{count} note(s), {model} ({dim}d)"
        if missing > 0:
            detail += f", {missing} not indexed"
            problems += 1
        print(f"  [{'ok' if not problems else '!!'}] {detail}")
    if len(rows) > 1:
        print("  [!!] more than one embedder in the index — cosine scores are not comparable")
        problems += 1

    if problems:
        print("\n[!] search is degraded. Rebuild: memory-search.py index --rebuild")
        return 1
    print("\n[ok] index covers the vault with the intended embedder")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default=Path("memory"), type=Path)
    ap.add_argument("--db", default=None, type=Path, help="cache DB (default: <vault>/.search-index.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index", help="build/update the embedding cache")
    pi.add_argument("--rebuild", action="store_true", help="discard the cache and re-embed all")
    ps = sub.add_parser("search", help="query the vault")
    ps.add_argument("query")
    ps.add_argument("-k", "--top", type=int, default=5)
    sub.add_parser("status", help="is the index fresh and using the intended embedder?")
    args = ap.parse_args(argv)
    if args.db is None:
        args.db = args.vault / ".search-index.db"
    return {"index": cmd_index, "search": cmd_search, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
