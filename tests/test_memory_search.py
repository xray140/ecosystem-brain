"""Tests for the semantic search index — truncation, resilience, and status.

Three defects motivated these, and they compounded into one silent failure:

  * `nomic-embed-text` answers HTTP 500 past ~2k tokens, and nothing truncated —
    `roadmap.md`, the largest and most important note, could not be embedded.
  * One failing note aborted the whole build with a traceback, leaving the old
    index untouched.
  * Nothing ever rebuilt the index, so it sat at 24-of-28 notes on the offline
    hash fallback while the README advertised Ollama embeddings.

Degraded search returns *plausible* results. That is exactly why it went
unnoticed, and why `status` has to assert the embedder, not just that rows exist.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import urllib.error
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "memory" / "memory-search.py"
spec = importlib.util.spec_from_file_location("memory_search", SKILL)
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)


class Args:
    """Stand-in for the argparse namespace."""

    def __init__(self, vault, db=None, offline=False, model="nomic-embed-text"):
        self.vault = vault
        self.db = db or vault / ".search-index.db"
        self.offline = offline
        self.model = model
        self.ollama_host = "http://localhost:11434"
        self.rebuild = False


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "memory"
    v.mkdir()
    return v


def note(vault, name, body="body text"):
    p = vault / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntype: note\n---\n# {name}\n{body}\n", encoding="utf-8")
    return p


# --- truncation: the root cause of the 500 --------------------------------
def test_long_text_is_truncated_before_sending():
    """Ollama answers 500 rather than truncating for you, and that 500 took the
    whole index build down."""
    sent = {}

    class Probe(ms.OllamaEmbedder):
        def embed(self, text):
            sent["len"] = len(text[: ms.MAX_EMBED_CHARS])
            return [1.0]

    Probe("m", "http://x").embed("x" * 100_000)
    assert sent["len"] == ms.MAX_EMBED_CHARS


def test_the_cap_is_below_what_actually_failed():
    """Measured on this vault: 4k chars fine, 14k (roadmap.md) and 20k → 500."""
    assert ms.MAX_EMBED_CHARS < 14_000


# --- one bad note must not abort the build --------------------------------
def test_a_failing_note_is_skipped_not_fatal(vault, capsys):
    note(vault, "good-a.md")
    note(vault, "bad.md")
    note(vault, "good-b.md")

    class Flaky:
        name, model = "flaky", "flaky-1"

        def embed(self, text):
            if "bad" in text:
                raise urllib.error.HTTPError("u", 500, "boom", {}, None)
            return [0.5, 0.5]

    ms.pick_embedder = lambda args: Flaky()
    assert ms.cmd_index(Args(vault)) == 0
    con = sqlite3.connect(vault / ".search-index.db")
    indexed = {r[0] for r in con.execute("SELECT path FROM vec")}
    assert indexed == {"good-a.md", "good-b.md"}, "the good notes must still land"
    assert "bad.md" in capsys.readouterr().err


def test_unembeddable_notes_are_named_as_unsearchable(vault, capsys):
    note(vault, "bad.md")

    class AlwaysFails:
        name, model = "x", "x-1"

        def embed(self, text):
            raise OSError("nope")

    ms.pick_embedder = lambda args: AlwaysFails()
    ms.cmd_index(Args(vault))
    err = capsys.readouterr().err
    assert "NOT searchable" in err
    assert "bad.md" in err


# --- status: the guard against silent degradation -------------------------
def _index_with(vault, model, dim, paths):
    con = ms.connect(vault / ".search-index.db")
    for p in paths:
        con.execute(
            "INSERT OR REPLACE INTO vec(path, mtime, model, dim, data) VALUES (?,?,?,?,?)",
            (p, 0.0, model, dim, ms.pack([0.1] * dim)),
        )
    con.commit()
    con.close()


def test_status_flags_the_offline_fallback(vault, capsys):
    """The exact state this vault was in: rows present, search 'working',
    every vector a bag of words."""
    note(vault, "a.md")
    _index_with(vault, "hash-256", 256, ["a.md"])
    assert ms.cmd_status(Args(vault)) == 1
    out = capsys.readouterr().out
    assert "expected real embeddings" in out
    assert "degraded" in out


def test_status_accepts_the_fallback_when_it_was_asked_for(vault):
    note(vault, "a.md")
    _index_with(vault, "hash-256", 256, ["a.md"])
    assert ms.cmd_status(Args(vault, offline=True)) == 0


def test_status_flags_partial_coverage(vault, capsys):
    """24 of 28 notes indexed was the other half of the rot."""
    for n in ("a.md", "b.md", "c.md"):
        note(vault, n)
    _index_with(vault, "nomic-embed-text", 768, ["a.md"])
    assert ms.cmd_status(Args(vault)) == 1
    assert "2 not indexed" in capsys.readouterr().out


def test_status_passes_on_a_healthy_index(vault, capsys):
    for n in ("a.md", "b.md"):
        note(vault, n)
    _index_with(vault, "nomic-embed-text", 768, ["a.md", "b.md"])
    assert ms.cmd_status(Args(vault)) == 0
    assert "covers the vault" in capsys.readouterr().out


def test_status_flags_an_empty_index(vault, capsys):
    note(vault, "a.md")
    assert ms.cmd_status(Args(vault)) == 1
    assert "index is empty" in capsys.readouterr().out


def test_status_flags_mixed_embedders(vault, capsys):
    """Cosine scores from two different models are not comparable, so a mixed
    index silently ranks nonsense."""
    for n in ("a.md", "b.md"):
        note(vault, n)
    _index_with(vault, "nomic-embed-text", 768, ["a.md"])
    _index_with(vault, "hash-256", 256, ["b.md"])
    assert ms.cmd_status(Args(vault)) == 1
    assert "not comparable" in capsys.readouterr().out


# --- the hash embedder stays usable ---------------------------------------
def test_hash_embedder_is_deterministic_and_normalised():
    a = ms.HashEmbedder().embed("some note text")
    b = ms.HashEmbedder().embed("some note text")
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-9


def test_cosine_of_identical_vectors_is_one():
    v = ms.HashEmbedder().embed("hello")
    assert abs(ms.cosine(v, v) - 1.0) < 1e-9
