"""Tests for the memory-index link resolver.

The bug this guards: path-qualified links (`[[decisions/hook-format]]`) used to
dangle because the indexer matched note ids by basename only, fragmenting the
graph and orphaning the roadmap hub.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "memory" / "memory-index.py"
spec = importlib.util.spec_from_file_location("memory_index", SKILL)
mi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mi)


def test_link_basename_strips_folder_and_refs():
    assert mi.link_basename("decisions/hook-format") == "hook-format"
    assert mi.link_basename("hook-format") == "hook-format"
    assert mi.link_basename("decisions/hook-format#Rules") == "hook-format"
    assert mi.link_basename("projects/x^block") == "x"


def _vault(tmp_path):
    (tmp_path / "decisions").mkdir()
    (tmp_path / "decisions" / "hook-format.md").write_text(
        "---\ntype: decision\n---\n# Hook format\n", encoding="utf-8"
    )
    # A hub that links via the PATH form — must still resolve to the note.
    (tmp_path / "roadmap.md").write_text(
        "---\ntype: moc\n---\n# Roadmap\nSee [[decisions/hook-format]].\n",
        encoding="utf-8",
    )
    # A note with a genuinely dangling link.
    (tmp_path / "stray.md").write_text(
        "---\ntype: note\n---\nlink to [[does-not-exist]].\n", encoding="utf-8"
    )
    return tmp_path


def test_path_form_link_resolves_to_an_edge(tmp_path):
    idx = mi.build(_vault(tmp_path))
    edges = {tuple(e) for e in idx["edges"]}
    assert ("roadmap", "hook-format") in edges  # path-form resolved -> real edge


def test_dangling_link_is_surfaced_not_faked(tmp_path):
    idx = mi.build(_vault(tmp_path))
    stray = next(n for n in idx["notes"] if n["id"] == "stray")
    assert stray["unresolved"] == ["does-not-exist"]
    assert stray["links"] == []  # no fake edge created
    assert idx["counts"]["unresolved"] == 1


def test_no_self_edges(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\ntype: note\n---\nI link [[a]] myself.\n", encoding="utf-8"
    )
    idx = mi.build(tmp_path)
    a = next(n for n in idx["notes"] if n["id"] == "a")
    assert "a" not in a["links"]
