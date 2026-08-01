#!/usr/bin/env python3
"""Local semantic search over the memory/ vault.

Embeds each note and answers natural-language queries by cosine similarity.
Embeddings are cached in a local SQLite DB and only recomputed when a note's
mtime changes. stdlib only (sqlite3 + urllib + math) — no numpy, no extra deps.

Backends:
  * Ollama (default): POST to $OLLAMA_HOST/api/embeddings with --model
    (e.g. nomic-embed-text). Fully local, zero API cost.
  * Hash (--offline, or automatic fallback if Ollama is unreachable): a
    deterministic bag-of-words embedder. Lower quality, but keeps search usable
    offline and makes the storage/ranking logic testable without a model.

Usage:
    python skills/memory-search.py index [--model nomic-embed-text] [--rebuild]
    python skills/memory-search.py search "what did we decide about render settings" -k 5
    python skills/memory-search.py index --offline      # no Ollama needed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from array import array
from pathlib import Path

FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
WORD_RE = re.compile(r"[a-z0-9]+")
HASH_DIM = 256


# --------------------------------------------------------------------- embedders
class HashEmbedder:
    """Deterministic offline embedder: hashed bag-of-words, L2-normalized."""

    name = "hash"

    def __init__(self, dim: int = HASH_DIM) -> None:
        self.dim = dim
        self.model = f"hash-{dim}"

    def embed(self, text: str) -> list[float]:
        """Return a normalized vector for one text."""
        vec = [0.0] * self.dim
        for tok in WORD_RE.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)  # noqa: S324 (not security)
            vec[h % self.dim] += 1.0
        return _normalize(vec)


class OllamaEmbedder:
    """Calls a local Ollama server for embeddings (one note per request)."""

    name = "ollama"

    def __init__(self, model: str, host: str, timeout: float = 30.0) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        """Return the embedding for one text via $OLLAMA_HOST/api/embeddings."""
        payload = json.dumps({"model": self.model, "prompt": text}).encode()
        req = urllib.request.Request(  # noqa: S310 (localhost Ollama)
            f"{self.host}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (localhost)
            data = json.loads(resp.read())
        return _normalize([float(x) for x in data["embedding"]])


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
def pick_embedder(args) -> HashEmbedder | OllamaEmbedder:
    """Choose Ollama if reachable, else fall back to the hash embedder."""
    if args.offline:
        return HashEmbedder()
    emb = OllamaEmbedder(args.model, args.ollama_host)
    try:
        emb.embed("ping")
    except (urllib.error.URLError, OSError, KeyError) as exc:
        print(f"[warn] Ollama unavailable ({exc}); using offline hash embedder", file=sys.stderr)
        return HashEmbedder()
    return emb


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
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        mtime = path.stat().st_mtime
        if cached.get(rel) == mtime:
            skipped += 1
            continue
        vec = emb.embed(note_text(path))
        con.execute(
            "INSERT OR REPLACE INTO vec(path, mtime, model, dim, data) VALUES (?,?,?,?,?)",
            (rel, mtime, emb.model, len(vec), pack(vec)),
        )
        done += 1
    con.commit()
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default=Path("memory"), type=Path)
    ap.add_argument("--db", default=None, type=Path, help="cache DB (default: <vault>/.search-index.db)")
    ap.add_argument("--model", default="nomic-embed-text")
    ap.add_argument("--ollama-host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ap.add_argument("--offline", action="store_true", help="force the hash embedder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index", help="build/update the embedding cache")
    pi.add_argument("--rebuild", action="store_true", help="discard the cache and re-embed all")
    ps = sub.add_parser("search", help="query the vault")
    ps.add_argument("query")
    ps.add_argument("-k", "--top", type=int, default=5)
    args = ap.parse_args(argv)
    if args.db is None:
        args.db = args.vault / ".search-index.db"
    return cmd_index(args) if args.cmd == "index" else cmd_search(args)


if __name__ == "__main__":
    raise SystemExit(main())
