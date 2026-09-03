"""Tests for the committed catalog seed.

`registry/catalog.json` is rewritten every Sunday by a scheduled task. As a
tracked file that meant a weekly uncommitted diff nobody landed: it sat at its
2026-06-05 state for eleven weeks while the task reported success, and the
2026-08-16 refresh was swept into an auto-stash during unrelated branch work and
nearly lost.

It is now gitignored, with `registry/catalog.seed.json` as the committed floor a
fresh clone reads until its first build. The properties that arrangement needs:
the live file wins when present, the seed answers when it is not, and a reader
is told which one spoke — a stale answer that looks authoritative is the failure
mode this exists to avoid.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import catalog as cat
import init_project as ip
import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "hooks" / "scripts" / "suggest-agents.py"

_spec = importlib.util.spec_from_file_location("suggest_agents", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

MODULES = [("catalog.py", cat), ("init_project.py", ip), ("suggest-agents.py", hook)]


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Point every module's CATALOG/CATALOG_SEED at the same temp pair."""
    live, seed = tmp_path / "catalog.json", tmp_path / "catalog.seed.json"
    for _, mod in MODULES:
        monkeypatch.setattr(mod, "CATALOG", live)
        monkeypatch.setattr(mod, "CATALOG_SEED", seed)
    return live, seed


def write(path, count, names=("alpha",)):
    path.write_text(
        json.dumps(
            {
                "count": count,
                "agents": [
                    # repo/path mirror real catalog entries — classify_agents
                    # reads both when resolving a github-sourced agent.
                    {"name": n, "repo": "o/r", "path": f"categories/{n}.md", "tags": []}
                    for n in names
                ],
            }
        ),
        encoding="utf-8",
    )


# --- resolution order ------------------------------------------------------
@pytest.mark.parametrize(("label", "mod"), MODULES)
def test_the_live_catalog_wins_when_present(paths, label, mod):
    live, seed = paths
    write(live, 158)
    write(seed, 154)
    assert mod.catalog_path() == live, label


@pytest.mark.parametrize(("label", "mod"), MODULES)
def test_the_seed_answers_when_there_is_no_live_catalog(paths, label, mod):
    """The fresh-clone case the seed exists for."""
    _, seed = paths
    write(seed, 154)
    assert mod.catalog_path() == seed, label


@pytest.mark.parametrize(("label", "mod"), MODULES)
def test_neither_present_resolves_to_nothing(paths, label, mod):
    assert mod.catalog_path() is None, label


def test_all_three_resolvers_agree(paths):
    """The resolver is duplicated three ways — the hook must stay importable
    from nothing, and init_project has no shared-module habit. This is what
    stops the copies drifting apart."""
    live, seed = paths
    write(seed, 154)
    assert len({mod.catalog_path() for _, mod in MODULES}) == 1
    write(live, 158)
    assert len({mod.catalog_path() for _, mod in MODULES}) == 1


# --- a reader is told which file answered ---------------------------------
def test_reading_the_seed_says_so(paths, capsys):
    _, seed = paths
    write(seed, 154)
    cat.load_catalog()
    assert "seed" in capsys.readouterr().err


def test_reading_the_live_catalog_is_quiet(paths, capsys):
    live, _ = paths
    write(live, 158)
    cat.load_catalog()
    assert capsys.readouterr().err == ""


def test_no_catalog_and_no_seed_exits(paths):
    with pytest.raises(SystemExit):
        cat.load_catalog()


# --- the degradation the seed prevents ------------------------------------
def test_init_resolves_catalog_agents_from_the_seed(paths):
    """Without a catalog, classify_agents drops every catalog agent as unknown —
    a fresh clone would quietly scaffold projects with the roster stripped."""
    _, seed = paths
    write(seed, 2, names=("alpha", "beta"))
    resolved, dropped = ip.classify_agents(["alpha"], {"local_agents": []})
    assert dropped == []
    assert [r["name"] for r in resolved] == ["alpha"]


def test_init_still_drops_an_agent_in_neither_catalog_nor_local(paths):
    """Not-dropping must not become never-dropping."""
    _, seed = paths
    write(seed, 1, names=("alpha",))
    _, dropped = ip.classify_agents(["nope"], {"local_agents": []})
    assert dropped == ["nope"]


# --- repo invariants -------------------------------------------------------
def test_the_seed_is_committed_and_the_live_catalog_is_not():
    """The whole point: the weekly rewrite must not dirty the repo, and a fresh
    clone must still have a catalog."""
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "registry/catalog.json", "registry/catalog.seed.json"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=False,
    ).stdout.split()
    assert "registry/catalog.seed.json" in tracked
    assert "registry/catalog.json" not in tracked


def test_the_committed_seed_is_a_usable_catalog():
    """A seed that does not parse is worse than none — it is the fallback."""
    data = json.loads((REPO / "registry" / "catalog.seed.json").read_text(encoding="utf-8"))
    assert data["count"] == len(data["agents"])
    assert data["count"] > 100
    assert all("name" in a for a in data["agents"])
