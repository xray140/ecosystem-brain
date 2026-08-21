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
import json
import sqlite3
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "memory" / "memory-search.py"
spec = importlib.util.spec_from_file_location("memory_search", SKILL)
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

# Captured before any test can reassign ms.pick_embedder at module scope
# (several existing tests do `ms.pick_embedder = lambda args: ...` without
# restoring it, which otherwise leaks into whichever test runs next).
_real_pick_embedder = ms.pick_embedder


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
def test_long_text_is_truncated_before_sending(monkeypatch):
    """Ollama answers 500 rather than truncating for you, and that 500 took the
    whole index build down.

    This intercepts the payload the REAL embed() builds. An earlier version
    subclassed OllamaEmbedder and re-implemented the truncation inside the test,
    so it passed no matter what the source did — a mutation run caught it, which
    is the whole argument for mutating your own checks.
    """
    sent = {}

    class FakeResponse:
        def read(self):
            return json.dumps({"embedding": [1.0, 0.0]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def capture(req, timeout=None):
        sent["payload"] = json.loads(req.data.decode())
        return FakeResponse()

    monkeypatch.setattr(ms.urllib.request, "urlopen", capture)
    ms.OllamaEmbedder("m", "http://x").embed("x" * 100_000)
    assert len(sent["payload"]["prompt"]) == ms.MAX_EMBED_CHARS


def test_short_text_is_sent_whole(monkeypatch):
    """Truncation must not clip an ordinary note."""
    sent = {}

    class FakeResponse:
        def read(self):
            return json.dumps({"embedding": [1.0, 0.0]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        ms.urllib.request,
        "urlopen",
        lambda req, timeout=None: (
            sent.update(payload=json.loads(req.data.decode())),
            FakeResponse(),
        )[1],
    )
    ms.OllamaEmbedder("m", "http://x").embed("a short note")
    assert sent["payload"]["prompt"] == "a short note"


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


# --- pure helpers: cosine, snippet, unpack --------------------------------
def test_cosine_of_mismatched_length_vectors_is_zero():
    """A dim mismatch means two different embedders got compared (e.g. a stale
    hash-256 row scored against a 768-d query). Treating that as similar would
    rank garbage as a match instead of refusing to compare."""
    assert ms.cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_a_zero_vector_is_not_a_perfect_match():
    """The `if na and nb` guard is doing real work, not just dodging a
    ZeroDivisionError. A zero vector is what a failed or empty embedding leaves
    behind, and scoring it 1.0 would float that garbage to the top of every
    search — in a module whose whole history is degrading without failing.
    Added in review: a mutation returning 1.0 here passed all 31 tests."""
    assert ms.cosine([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert ms.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_snippet_strips_frontmatter_and_collapses_whitespace(vault):
    """`search` prints this as the human-facing preview; a leaked frontmatter
    fence or a raw newline would make every result look broken."""
    p = note(vault, "a.md", body="line one\n\nline   two")
    assert ms.snippet(p) == "# a.md line one line two"


def test_snippet_truncates_long_bodies_with_an_ellipsis(vault):
    p = note(vault, "long.md", body="word " * 200)
    result = ms.snippet(p, width=20)
    assert len(result) == 23
    assert result.endswith("...")


def test_snippet_no_ellipsis_when_body_fits(vault):
    p = note(vault, "short.md", body="hi")
    result = ms.snippet(p, width=160)
    assert result == "# short.md hi"
    assert not result.endswith("...")


def test_pack_unpack_roundtrip():
    """`search` decodes every cached vector through unpack() before scoring
    it. Floats round-trip through a float32 array, so pin approximate
    equality rather than exact — a broken (de)serialization would still fail
    this."""
    original = [0.5, -0.25, 1.0, 0.0]
    assert ms.unpack(ms.pack(original)) == pytest.approx(original, rel=1e-6)


# --- pick_embedder: the fallback the whole file exists to catch -----------
def test_pick_embedder_short_circuits_when_offline(vault, monkeypatch):
    """--offline must never attempt to reach Ollama at all, not merely prefer
    not to."""

    def fail_if_called(self, text):
        raise AssertionError("must not attempt a network call when --offline is set")

    monkeypatch.setattr(ms.OllamaEmbedder, "embed", fail_if_called)
    emb = _real_pick_embedder(Args(vault, offline=True))
    assert isinstance(emb, ms.HashEmbedder)


def test_pick_embedder_uses_ollama_when_reachable(vault, monkeypatch):
    """The non-degraded path: a healthy server must not be routed to the
    fallback."""

    class FakeResponse:
        def read(self):
            return json.dumps({"embedding": [1.0, 0.0]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ms.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())
    emb = _real_pick_embedder(Args(vault, offline=False))
    assert isinstance(emb, ms.OllamaEmbedder)
    assert emb.model == "nomic-embed-text"


def test_pick_embedder_falls_back_to_hash_when_ollama_unreachable(vault, monkeypatch, capsys):
    """The exact defect `cmd_status` exists to catch: this must not raise and
    must not silently hand back an embedder that will fail on every note — it
    has to warn and return something usable."""

    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(ms.urllib.request, "urlopen", boom)
    emb = _real_pick_embedder(Args(vault, offline=False))
    assert isinstance(emb, ms.HashEmbedder)
    assert "Ollama unavailable" in capsys.readouterr().err


def test_pick_embedder_falls_back_on_malformed_response(vault, monkeypatch):
    """A response body without an "embedding" key (an error payload, a wrong
    endpoint) raises KeyError inside embed(); that must be caught here too, or
    one bad response aborts the whole run instead of degrading gracefully."""

    class FakeResponse:
        def read(self):
            return json.dumps({"error": "model not found"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ms.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())
    emb = _real_pick_embedder(Args(vault, offline=False))
    assert isinstance(emb, ms.HashEmbedder)


# --- cmd_index: the vault guard, --rebuild, and the mtime cache -----------
def test_cmd_index_reports_missing_vault(tmp_path, capsys):
    """Same contract as memory-index.py: "no vault" must not read as "empty
    vault, nothing to do"."""
    missing = tmp_path / "nope"
    assert ms.cmd_index(Args(missing)) == 1
    assert "vault not found" in capsys.readouterr().err


def test_cmd_index_skips_unchanged_notes_without_reembedding(vault, monkeypatch):
    """Re-embedding on every run regardless of mtime would make `index` slow
    and would burn API calls on notes that already succeeded."""
    note(vault, "a.md")
    calls = []

    class Counting:
        name, model = "counting", "counting-1"

        def embed(self, text):
            calls.append(text)
            return [0.1, 0.2]

    monkeypatch.setattr(ms, "pick_embedder", lambda args: Counting())
    ms.cmd_index(Args(vault))
    assert len(calls) == 1
    ms.cmd_index(Args(vault))
    assert len(calls) == 1, "an unchanged note must not be re-embedded on the second run"


def test_cmd_index_rebuild_clears_the_whole_table(vault, monkeypatch):
    """--rebuild is the fix `cmd_status` prescribes for a degraded index. If
    the DELETE did not run, a stale row (wrong model, or a note since deleted)
    would survive the rebuild and keep tripping the mixed-embedder or
    offline-fallback check even after the operator "fixed" it."""
    note(vault, "a.md")
    _index_with(vault, "old-model", 2, ["a.md", "ghost.md"])

    class Counting:
        name, model = "counting", "counting-1"

        def embed(self, text):
            return [0.1, 0.2]

    monkeypatch.setattr(ms, "pick_embedder", lambda args: Counting())
    args = Args(vault)
    args.rebuild = True
    ms.cmd_index(args)
    con = sqlite3.connect(vault / ".search-index.db")
    rows = {(r[0], r[1]) for r in con.execute("SELECT path, model FROM vec")}
    con.close()
    assert rows == {("a.md", "counting-1")}, (
        "rebuild must wipe stale/ghost rows, not accumulate them"
    )


# --- cmd_search: nothing exercised this before -----------------------------
def _insert_vec(vault, model, path, vec):
    con = ms.connect(vault / ".search-index.db")
    con.execute(
        "INSERT OR REPLACE INTO vec(path, mtime, model, dim, data) VALUES (?,?,?,?,?)",
        (path, 0.0, model, len(vec), ms.pack(vec)),
    )
    con.commit()
    con.close()


def test_cmd_search_errors_when_no_embeddings_for_model(vault, capsys):
    """A missing index for the active model must fail loudly. Read as "no
    results" it would look identical to a query that simply matched nothing."""
    args = Args(vault, offline=True)
    args.query = "anything"
    args.top = 5
    assert ms.cmd_search(args) == 1
    assert "no embeddings" in capsys.readouterr().err


def test_cmd_search_ranks_by_cosine_and_caps_at_top_k(vault, monkeypatch, capsys):
    """Pins the actual output contract: closest match first, capped at -k,
    with a 3-decimal score. A wrong sort direction or an off-by-one slice
    would silently invert or truncate results while still returning 0."""
    note(vault, "close.md", body="alpha")
    note(vault, "far.md", body="beta")
    _insert_vec(vault, "hash-256", "close.md", [1.0, 0.0])
    _insert_vec(vault, "hash-256", "far.md", [0.0, 1.0])

    class FixedQuery:
        name, model = "hash", "hash-256"

        def embed(self, text):
            return [1.0, 0.0]

    monkeypatch.setattr(ms, "pick_embedder", lambda args: FixedQuery())
    args = Args(vault)
    args.query = "alpha"
    args.top = 1
    assert ms.cmd_search(args) == 0
    out = capsys.readouterr().out
    assert "close.md" in out
    assert "far.md" not in out, "top=1 must cap results, and the closer note must win"
    assert "1.000" in out


# --- main(): argparse wiring, exercised in-process for coverage ----------
def test_main_in_process_dispatches_index_search_status(vault, monkeypatch):
    """main() is the actual wiring between argv and cmd_index/cmd_search/
    cmd_status; every other test in this file bypasses it by calling those
    directly. Restores the real pick_embedder first: earlier tests reassign
    ms.pick_embedder as a bare module attribute (not via monkeypatch) and
    never restore it, which would otherwise leak into this test."""
    monkeypatch.setattr(ms, "pick_embedder", _real_pick_embedder)
    note(vault, "a.md")
    assert ms.main(["--vault", str(vault), "--offline", "index"]) == 0
    assert (vault / ".search-index.db").exists(), "default --db must derive from --vault"
    assert ms.main(["--vault", str(vault), "--offline", "status"]) == 0
    assert ms.main(["--vault", str(vault), "--offline", "search", "body", "-k", "1"]) == 0


# --- main(): the actual entry point, run as a real subprocess -------------
# These three exercise argparse wiring and the `if __name__ == "__main__"`
# guard that in-process importlib loading never triggers. --offline keeps
# them off the network and off Ollama.
def test_main_offline_index_builds_a_real_cache_file(tmp_path):
    vault = tmp_path / "memory"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntype: note\n---\n# A\nhello\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "--offline", "index"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "embedded 1" in result.stdout
    assert (vault / ".search-index.db").exists(), "default --db must derive from --vault"


def test_main_offline_status_reports_a_healthy_index(tmp_path):
    vault = tmp_path / "memory"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntype: note\n---\n# A\nhello\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "--offline", "index"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    status = subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "--offline", "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert status.returncode == 0
    assert "covers the vault" in status.stdout


def test_main_offline_search_finds_the_indexed_note(tmp_path):
    vault = tmp_path / "memory"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntype: note\n---\n# A\nhello\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "--offline", "index"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SKILL),
            "--vault",
            str(vault),
            "--offline",
            "search",
            "hello",
            "-k",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "a.md" in result.stdout
