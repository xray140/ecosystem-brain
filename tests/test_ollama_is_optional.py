"""Ollama is optional: absent, nothing reports a problem.

It used to be infrastructure — a logon task keeping a server up, a line in the
prerequisite list, and a status check that failed whenever the index used the
offline embedder. On a machine without Ollama that check could not be satisfied
except by installing software the user had chosen not to run.

Worse, most of Ollama's bad reputation came from the task, not the tool: it sat
red for weeks pointing at a path the script had long since left.

The capability stays. When Ollama IS up, a hash-embedded index is still a real
defect and still reported, because then a rebuild actually fixes it.
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import bootstrap as bs

REPO = Path(__file__).resolve().parent.parent


def _load_memory_search():
    path = REPO / "skills" / "memory" / "memory-search.py"
    spec = importlib.util.spec_from_file_location("memory_search_opt", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ms = _load_memory_search()


# --- prerequisites ---------------------------------------------------------


def test_ollama_is_not_a_required_tool():
    assert "ollama" not in bs.REQUIRED_TOOLS
    assert "ollama" in bs.OPTIONAL_TOOLS


def test_the_tools_that_matter_are_still_required():
    """Demoting one tool must not quietly demote the rest."""
    for tool in ("uv", "git", "gh", "gitleaks", "ruff"):
        assert tool in bs.REQUIRED_TOOLS


def test_missing_optional_tool_does_not_print_MISS(monkeypatch, capsys):
    monkeypatch.setattr(bs.shutil, "which", lambda t: None)
    bs.check_prereqs()
    out = capsys.readouterr().out
    ollama_line = next(ln for ln in out.splitlines() if "ollama" in ln)
    assert "MISS" not in ollama_line, "an optional tool must not read as missing"
    assert "optional" in ollama_line


# --- the scheduled task is gone --------------------------------------------


def test_no_logon_task_registers_ollama():
    """Scoped to the $tasks array. Comments and the $retired list both name
    OllamaServe on purpose — the question is whether it is still REGISTERED."""
    ps1 = (REPO / "scripts" / "register-scheduled-tasks.ps1").read_text(
        encoding="utf-8", errors="replace"
    )
    block = ps1.split("$tasks = @(", 1)[1].split(")", 1)[0]
    assert "CatalogRefresh" in block, "the $tasks block was not located correctly"
    assert "OllamaServe" not in block, "the logon task is still being registered"


def test_the_retired_task_is_actively_unregistered():
    """Dropping it from the list is not enough — a machine that already has it
    registered keeps failing until something removes it."""
    ps1 = (REPO / "scripts" / "register-scheduled-tasks.ps1").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "$retired" in ps1
    assert "EcosystemBrain-OllamaServe" in ps1
    assert "Unregister-ScheduledTask -TaskName $name" in ps1


def test_the_launcher_script_is_gone():
    assert not (REPO / "scripts" / "start-ollama.bat").exists()


# --- status: only complain when the complaint is actionable ----------------


@pytest.fixture
def hash_index(tmp_path):
    db = tmp_path / "idx.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE vec (path TEXT, model TEXT, dim INT, v BLOB)")
    con.execute("INSERT INTO vec VALUES ('a.md', 'hash-256', 256, x'00')")
    con.commit()
    con.close()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("note", encoding="utf-8")
    return SimpleNamespace(db=db, vault=vault, offline=False, model="m", ollama_host="h")


def test_hash_index_is_fine_when_ollama_is_absent(hash_index, monkeypatch, capsys):
    monkeypatch.setattr(ms, "_ollama_reachable", lambda a: False)
    assert ms.cmd_status(hash_index) == 0
    assert "expected" in capsys.readouterr().out


def test_hash_index_is_a_defect_when_ollama_is_up(hash_index, monkeypatch, capsys):
    """The original signal must survive: with Ollama running, the index is
    worse than the machine can do and a rebuild fixes it."""
    monkeypatch.setattr(ms, "_ollama_reachable", lambda a: True)
    assert ms.cmd_status(hash_index) == 1
    assert "rebuild" in capsys.readouterr().out.lower()


def test_reachability_probe_is_false_in_offline_mode():
    assert ms._ollama_reachable(SimpleNamespace(offline=True, model="m", ollama_host="h")) is False
