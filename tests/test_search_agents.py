"""Tests for the GitHub agent search.

Every `gh` call is stubbed — these pin the query construction and the result
shaping, not GitHub's behaviour. The query strings matter: they are what keeps
generic "awesome" lists from crowding out real agent repos.
"""

from __future__ import annotations

import json

import pytest
import search_agents as sa


class _Gh:
    """Records the args handed to gh_api and serves a settable payload."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.payload: dict = {"items": []}

    def __call__(self, args):
        self.calls.append(args)
        return self.payload

    def returns(self, payload):
        self.payload = payload


@pytest.fixture
def captured(monkeypatch):
    gh = _Gh()
    monkeypatch.setattr(sa, "gh_api", gh)
    return gh


# --- repo search ----------------------------------------------------------
def test_repo_search_restricts_to_name_and_description(captured):
    sa.search_repos("react testing", 10)
    q = next(a for a in captured.calls[0] if a.startswith("q="))
    assert "in:name,description" in q, "must not match on readme text"
    assert "react testing" in q
    assert "sort=stars" in captured.calls[0]


def test_repo_search_shapes_results(captured):
    captured.returns(
        {
            "items": [
                {
                    "stargazers_count": 42,
                    "full_name": "u/r",
                    "description": "a thing",
                }
            ]
        }
    )
    assert sa.search_repos("x", 5) == [{"stars": 42, "repo": "u/r", "desc": "a thing"}]


def test_repo_search_tolerates_a_null_description(captured):
    captured.returns({"items": [{"stargazers_count": 1, "full_name": "u/r", "description": None}]})
    assert sa.search_repos("x", 5)[0]["desc"] == ""


def test_repo_description_is_truncated(captured):
    captured.returns({"items": [{"stargazers_count": 1, "full_name": "u/r", "description": "y" * 200}]})
    assert len(sa.search_repos("x", 5)[0]["desc"]) == 80


# --- file search ----------------------------------------------------------
def test_file_search_scopes_to_agent_markdown(captured):
    sa.search_files("security", 10)
    q = next(a for a in captured.calls[0] if a.startswith("q="))
    assert "path:agents" in q
    assert "extension:md" in q


def test_file_search_derives_name_from_path(captured):
    captured.returns({"items": [{"repository": {"full_name": "u/r"}, "path": "agents/my-agent.md"}]})
    assert sa.search_files("x", 5) == [
        {"repo": "u/r", "path": "agents/my-agent.md", "name": "my-agent"}
    ]


def test_search_handles_a_list_response(monkeypatch):
    """gh returns a list for some endpoints; that must not raise."""
    monkeypatch.setattr(sa, "gh_api", lambda args: [])
    assert sa.search_repos("x", 5) == []
    assert sa.search_files("x", 5) == []


# --- known sources --------------------------------------------------------
def test_known_sources_reads_the_registry(tmp_path, monkeypatch):
    reg = tmp_path / "registry.json"
    reg.write_text(
        json.dumps({"sources": [{"repo": "u/one"}, {"repo": "u/two"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(sa, "REGISTRY", reg)
    assert sa.known_sources() == ["u/one", "u/two"]


def test_known_sources_empty_without_a_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(sa, "REGISTRY", tmp_path / "absent.json")
    assert sa.known_sources() == []


# --- main -----------------------------------------------------------------
def test_main_marks_already_known_repos(monkeypatch, capsys):
    monkeypatch.setattr(sa, "known_sources", lambda: ["u/known"])
    monkeypatch.setattr(
        sa,
        "search_repos",
        lambda q, n: [
            {"stars": 9, "repo": "u/known", "desc": "d"},
            {"stars": 8, "repo": "u/new", "desc": "d"},
        ],
    )
    assert sa.main(["topic"]) == 0
    out = capsys.readouterr().out
    known_line = next(ln for ln in out.splitlines() if "u/known" in ln)
    new_line = next(ln for ln in out.splitlines() if "u/new" in ln)
    # `★` alone is ambiguous — it also suffixes the star count ("8★").
    assert known_line.endswith("★known")
    assert not new_line.endswith("★known")


def test_main_reports_no_results(monkeypatch, capsys):
    monkeypatch.setattr(sa, "known_sources", lambda: [])
    monkeypatch.setattr(sa, "search_repos", lambda q, n: [])
    assert sa.main(["nothing"]) == 0
    assert "no repos found" in capsys.readouterr().out


def test_main_files_mode_prints_an_install_line(monkeypatch, capsys):
    monkeypatch.setattr(sa, "known_sources", lambda: [])
    monkeypatch.setattr(
        sa, "search_files", lambda q, n: [{"repo": "u/r", "path": "agents/a.md", "name": "a"}]
    )
    assert sa.main(["topic", "--files"]) == 0
    out = capsys.readouterr().out
    assert "--repo u/r --path agents/a.md" in out


def test_main_files_mode_reports_no_results(monkeypatch, capsys):
    monkeypatch.setattr(sa, "known_sources", lambda: [])
    monkeypatch.setattr(sa, "search_files", lambda q, n: [])
    assert sa.main(["nothing", "--files"]) == 0
    assert "no agent files found" in capsys.readouterr().out
