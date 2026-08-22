"""Tests for the search index — truncation, resilience, and status.

Three defects motivated these, and they compounded into one silent failure:

  * The embedding backend answered HTTP 500 past ~2k tokens and nothing
    truncated — `roadmap.md`, the largest and most important note, could not be
    embedded. That backend is gone (v4.8.0, [[decisions/no-ollama]]) but the cap
    stayed: the head of a note is the right thing to index either way.
  * One failing note aborted the whole build with a traceback, leaving the old
    index untouched.
  * Nothing ever rebuilt the index, so it sat at 24-of-28 notes while the README
    advertised semantics it was not delivering.

Degraded search returns *plausible* results. That is exactly why it went
unnoticed, and why `status` has to assert coverage, not just that rows exist.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "memory" / "memory-search.py"
spec = importlib.util.spec_from_file_location("memory_search", SKILL)
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

# The real one, captured at import. Tests that need the genuine embedder-chooser
# say so by name instead of assuming module state is pristine.
_real_pick_embedder = ms.pick_embedder


@pytest.fixture(autouse=True)
def _module_state_is_restored():
    """Fail any test that reassigns a module attribute without restoring it.

    Two tests here set `ms.pick_embedder = lambda ...` as a bare assignment.
    That survives the test and changes what every later test in the session
    sees — `pick_embedder` stayed stubbed for the rest of the run, so anything
    downstream depending on the real one was testing a leftover fake. It was
    caught by a probe, not by a failure: the suite stayed green because no test
    happened to notice.

    Snapshots every module-level function and class, and compares identity
    afterwards. `monkeypatch` undoes itself before this teardown runs, so
    legitimate patching passes and only bare assignment trips it.
    """
    import inspect

    before = {
        n: v
        for n, v in vars(ms).items()
        if inspect.isfunction(v) or inspect.isclass(v)
    }
    yield
    leaked = sorted(n for n, v in before.items() if getattr(ms, n, None) is not v)
    assert not leaked, (
        f"module attribute(s) left reassigned after the test: {leaked}. "
        "Use monkeypatch.setattr so it is undone."
    )



class Args:
    """Stand-in for the argparse namespace."""

    def __init__(self, vault, db=None):
        self.vault = vault
        self.db = db or vault / ".search-index.db"
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


# --- truncation: the root cause of the 500, kept for recall ---------------
def test_text_past_the_cap_does_not_reach_the_vector():
    """The cap has to be applied by the embedder, not merely documented.

    An earlier version of this test re-implemented the truncation inside the
    test itself, so it passed no matter what the source did — a mutation run
    caught it, which is the whole argument for mutating your own checks. This
    one can only pass if the real embed() drops what is past the cap: the
    trailing word is beyond it, so it must not move the vector at all.
    """
    emb = ms.HashEmbedder()
    filler = "x " * ms.MAX_EMBED_CHARS
    assert emb.embed(filler + " zebra") == emb.embed(filler)


def test_text_within_the_cap_is_indexed_whole():
    """Truncation must not clip an ordinary note: a word near the end of a
    short note still has to reach the vector."""
    emb = ms.HashEmbedder()
    assert emb.embed("alpha zebra") != emb.embed("alpha")


def test_the_cap_still_clips_the_biggest_note():
    """`roadmap.md` is ~14k chars. The cap outlived the 500s that first forced
    it, so this pins the surviving reason: index the head, where the topic is,
    rather than the whole note."""
    assert ms.MAX_EMBED_CHARS < 14_000


# --- one bad note must not abort the build --------------------------------
def test_a_failing_note_is_skipped_not_fatal(vault, capsys, monkeypatch):
    note(vault, "good-a.md")
    note(vault, "bad.md")
    note(vault, "good-b.md")

    class Flaky:
        name, model = "flaky", "flaky-1"

        def embed(self, text):
            if "bad" in text:
                raise OSError("boom")
            return [0.5, 0.5]

    monkeypatch.setattr(ms, "pick_embedder", lambda args: Flaky())
    assert ms.cmd_index(Args(vault)) == 0
    con = sqlite3.connect(vault / ".search-index.db")
    indexed = {r[0] for r in con.execute("SELECT path FROM vec")}
    assert indexed == {"good-a.md", "good-b.md"}, "the good notes must still land"
    assert "bad.md" in capsys.readouterr().err


def test_unembeddable_notes_are_named_as_unsearchable(vault, capsys, monkeypatch):
    note(vault, "bad.md")

    class AlwaysFails:
        name, model = "x", "x-1"

        def embed(self, text):
            raise OSError("nope")

    monkeypatch.setattr(ms, "pick_embedder", lambda args: AlwaysFails())
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


def test_status_flags_partial_coverage(vault, capsys):
    """24 of 28 notes indexed was the other half of the rot."""
    for n in ("a.md", "b.md", "c.md"):
        note(vault, n)
    _index_with(vault, "hash-256", 256, ["a.md"])
    assert ms.cmd_status(Args(vault)) == 1
    assert "2 not indexed" in capsys.readouterr().out


def test_status_passes_on_a_healthy_index(vault, capsys):
    for n in ("a.md", "b.md"):
        note(vault, n)
    _index_with(vault, "hash-256", 256, ["a.md", "b.md"])
    assert ms.cmd_status(Args(vault)) == 0
    assert "covers the vault" in capsys.readouterr().out


def test_status_flags_an_empty_index(vault, capsys):
    note(vault, "a.md")
    assert ms.cmd_status(Args(vault)) == 1
    assert "index is empty" in capsys.readouterr().out


def test_status_flags_mixed_embedders(vault, capsys):
    """Cosine scores from two different models are not comparable, so a mixed
    index silently ranks nonsense. Still reachable with one backend: change
    HASH_DIM, or index a vault that a previous version already embedded."""
    for n in ("a.md", "b.md"):
        note(vault, n)
    _index_with(vault, "hash-512", 512, ["a.md"])
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


# --- pick_embedder: one backend, one seam --------------------------------
def test_pick_embedder_returns_the_hash_embedder(vault):
    """There is one backend since v4.8.0. This pins that the seam still hands
    back a working embedder rather than, say, a class — the four tests it
    replaces all guarded a fallback that no longer has anything to fall back
    from."""
    emb = _real_pick_embedder(Args(vault))
    assert isinstance(emb, ms.HashEmbedder)
    assert emb.model == f"hash-{ms.HASH_DIM}"
    assert len(emb.embed("a note")) == ms.HASH_DIM


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
    would survive the rebuild and keep tripping the mixed-embedder check even
    after the operator "fixed" it."""
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
    args = Args(vault)
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
    directly. Pins the real pick_embedder explicitly rather than relying on no
    earlier test having replaced it — the autouse guard now enforces that, but
    stating the dependency keeps this test readable on its own."""
    monkeypatch.setattr(ms, "pick_embedder", _real_pick_embedder)
    note(vault, "a.md")
    assert ms.main(["--vault", str(vault), "index"]) == 0
    assert (vault / ".search-index.db").exists(), "default --db must derive from --vault"
    assert ms.main(["--vault", str(vault), "status"]) == 0
    assert ms.main(["--vault", str(vault), "search", "body", "-k", "1"]) == 0


# --- main(): the actual entry point, run as a real subprocess -------------
# These three exercise argparse wiring and the `if __name__ == "__main__"`
# guard that in-process importlib loading never triggers. Nothing here can
# touch the network: there is no backend left to reach.
def test_main_index_builds_a_real_cache_file(tmp_path):
    vault = tmp_path / "memory"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntype: note\n---\n# A\nhello\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "index"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "embedded 1" in result.stdout
    assert (vault / ".search-index.db").exists(), "default --db must derive from --vault"


def test_main_status_reports_a_healthy_index(tmp_path):
    vault = tmp_path / "memory"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntype: note\n---\n# A\nhello\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "index"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    status = subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert status.returncode == 0
    assert "covers the vault" in status.stdout


def test_main_search_finds_the_indexed_note(tmp_path):
    vault = tmp_path / "memory"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntype: note\n---\n# A\nhello\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SKILL), "--vault", str(vault), "index"],
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
