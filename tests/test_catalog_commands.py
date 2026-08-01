"""Tests for catalog.py's three subcommands.

`gh` and the installer subprocess are stubbed throughout. What matters here is
that a batch install reports the security scanner's verdict honestly: a blocked
agent must be counted as blocked, never folded into the error bucket or the
success count, because this is the one command that installs many agents at once
and the summary line is all anyone reads.
"""

from __future__ import annotations

import json
import subprocess

import catalog
import pytest


@pytest.fixture
def catalog_file(tmp_path, monkeypatch):
    p = tmp_path / "catalog.json"
    monkeypatch.setattr(catalog, "CATALOG", p)
    return p


def _write(catalog_file, agents, repo="u/r"):
    catalog_file.write_text(
        json.dumps({"repo": repo, "count": len(agents), "agents": agents}),
        encoding="utf-8",
    )


def _agent(name, category="01-core", path=None):
    return {
        "name": name,
        "repo": "u/r",
        "path": path or f"categories/{category}/{name}.md",
        "category": category,
        "tags": [],
    }


# --- build ----------------------------------------------------------------
def test_build_keeps_only_category_markdown(catalog_file, monkeypatch, capsys):
    monkeypatch.setattr(
        catalog,
        "gh_api",
        lambda args: {
            "tree": [
                {"path": "categories/01-core/python-pro.md"},
                {"path": "categories/01-core/README.md"},  # excluded
                {"path": "README.md"},  # excluded
                {"path": "categories/02-lang/rust-pro.md"},
                {"path": "categories/01-core/notes.txt"},  # excluded
            ]
        },
    )
    assert catalog.main(["build"]) == 0
    written = json.loads(catalog_file.read_text(encoding="utf-8"))
    assert [a["name"] for a in written["agents"]] == ["python-pro", "rust-pro"]
    assert written["count"] == 2
    assert "2 agents across 2 categories" in capsys.readouterr().out


def test_build_records_category_and_inferred_tags(catalog_file, monkeypatch):
    monkeypatch.setattr(
        catalog, "gh_api", lambda args: {"tree": [{"path": "categories/01-core/python-pro.md"}]}
    )
    catalog.main(["build"])
    agent = json.loads(catalog_file.read_text(encoding="utf-8"))["agents"][0]
    assert agent["category"] == "01-core"
    assert "python" in agent["tags"]


def test_build_writes_lf(catalog_file, monkeypatch):
    monkeypatch.setattr(
        catalog, "gh_api", lambda args: {"tree": [{"path": "categories/01-core/a.md"}]}
    )
    catalog.main(["build"])
    assert b"\r\n" not in catalog_file.read_bytes()


def test_build_survives_an_unexpected_response_shape(catalog_file, monkeypatch):
    monkeypatch.setattr(catalog, "gh_api", lambda args: [])
    assert catalog.main(["build"]) == 0
    assert json.loads(catalog_file.read_text(encoding="utf-8"))["agents"] == []


# --- categories -----------------------------------------------------------
def test_categories_counts_per_folder(catalog_file, capsys):
    _write(catalog_file, [_agent("a"), _agent("b"), _agent("c", "02-lang")])
    assert catalog.main(["categories"]) == 0
    out = capsys.readouterr().out
    assert "2  01-core" in out
    assert "1  02-lang" in out


def test_missing_catalog_tells_you_to_build(catalog_file):
    with pytest.raises(SystemExit, match=r"catalog\.py build"):
        catalog.main(["categories"])


# --- install --------------------------------------------------------------
def _installer(monkeypatch, codes):
    """Stub the per-agent installer subprocess with a sequence of exit codes."""
    seq = iter(codes)
    monkeypatch.setattr(
        catalog.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], next(seq), "", "boom"),
    )


def test_install_counts_blocked_separately_from_errors(catalog_file, monkeypatch, capsys):
    """Exit 2 is the security scanner refusing an agent. Reporting that as a
    generic error, or as a success, would hide the one outcome that matters."""
    _write(catalog_file, [_agent("good"), _agent("evil"), _agent("broken")])
    _installer(monkeypatch, [0, 2, 1])
    assert catalog.main(["install", "01-core"]) == 0
    out = capsys.readouterr().out
    assert "[ok]      good" in out
    assert "[BLOCKED] evil" in out
    assert "[error]   broken" in out
    assert "installed 1, blocked 1, of 3" in out


def test_install_respects_the_limit(catalog_file, monkeypatch, capsys):
    _write(catalog_file, [_agent(f"a{i}") for i in range(5)])
    _installer(monkeypatch, [0] * 5)
    catalog.main(["install", "01-core", "--limit", "2"])
    assert "installed 2, blocked 0, of 2" in capsys.readouterr().out


def test_install_of_an_unknown_category_fails_cleanly(catalog_file, capsys):
    _write(catalog_file, [_agent("a")])
    assert catalog.main(["install", "99-nope"]) == 1
    assert "no agents in category" in capsys.readouterr().out


def test_install_goes_through_the_scanning_installer(catalog_file, monkeypatch):
    """Batch install must not become a shortcut around the security gate."""
    seen: list[list[str]] = []

    def fake_run(cmd, *a, **k):
        seen.append(cmd)
        return subprocess.CompletedProcess([], 0, "", "")

    _write(catalog_file, [_agent("a")])
    monkeypatch.setattr(catalog.subprocess, "run", fake_run)
    catalog.main(["install", "01-core"])
    assert any("install-agent.py" in part for part in seen[0])
    assert "--repo" in seen[0] and "--path" in seen[0]


# --- gh failure modes -----------------------------------------------------
def test_missing_gh_cli_exits_with_guidance(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(catalog.subprocess, "run", boom)
    with pytest.raises(SystemExit, match="gh auth login"):
        catalog.gh_api(["whatever"])


def test_gh_api_error_is_reported(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "gh", stderr="rate limited")

    monkeypatch.setattr(catalog.subprocess, "run", boom)
    with pytest.raises(SystemExit, match="rate limited"):
        catalog.gh_api(["whatever"])
