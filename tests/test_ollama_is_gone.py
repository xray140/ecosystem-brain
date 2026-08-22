"""Ollama is gone, and has to stay gone.

It was demoted to optional in v4.7.0 and removed outright in v4.8.0 — see
[[decisions/no-ollama]]. The demotion is the reason this file is an enforcement
test rather than a changelog entry: "optional" survived exactly one release
before the operator asked for it to be gone entirely, and the pieces that make
it creep back are cheap to reintroduce one at a time (a prereq line here, a
model default there, an env var in the template).

What is deliberately NOT asserted: that the string "ollama" appears nowhere.
The history is load-bearing — the truncation cap, the mixed-embedder check and
the retired scheduled task all only make sense with it written down.
"""

from __future__ import annotations

import re
from pathlib import Path

import bootstrap as bs

REPO = Path(__file__).resolve().parent.parent
SEARCH = (REPO / "skills" / "memory" / "memory-search.py").read_text(
    encoding="utf-8", errors="replace"
)


# --- prerequisites ---------------------------------------------------------


def test_ollama_is_not_a_prerequisite_of_any_kind():
    assert "ollama" not in bs.REQUIRED_TOOLS
    assert not hasattr(bs, "OPTIONAL_TOOLS"), (
        "the optional list held one entry, ollama; an empty list would keep a "
        "print branch nothing exercises"
    )


def test_the_tools_that_matter_are_still_required():
    """Removing one tool must not quietly remove the rest."""
    for tool in ("uv", "git", "gh", "gitleaks", "ruff"):
        assert tool in bs.REQUIRED_TOOLS


def test_the_machine_profile_does_not_probe_for_it():
    import profile_machine

    assert "ollama" not in profile_machine.PREREQS


def test_no_ollama_env_var_in_the_template():
    """`.env.example` is what every scaffolded project and every fresh clone
    starts from, and selfcheck diffs `.env` against it — a stray key here is
    reported as a gap on machines that will never fill it."""
    example = (REPO / ".env.example").read_text(encoding="utf-8", errors="replace")
    assert "OLLAMA" not in example.upper()


# --- the backend itself ----------------------------------------------------


def test_memory_search_has_no_ollama_backend():
    assert "class OllamaEmbedder" not in SEARCH
    assert "api/embeddings" not in SEARCH
    assert "11434" not in SEARCH


def test_memory_search_makes_no_network_calls_at_all():
    """The point of removing the backend is that search is local and offline.
    An import of urllib is the cheapest early warning that something reached
    back out."""
    for module in ("urllib", "requests", "httpx", "socket"):
        assert not re.search(rf"^import {module}", SEARCH, re.M), f"{module} is back"
        assert not re.search(rf"^from {module}", SEARCH, re.M), f"{module} is back"


def test_the_offline_flag_is_gone_with_the_thing_it_opted_out_of():
    """`--offline` meant "do not use Ollama". With one backend it would be a
    flag that does nothing, which is worse than no flag: it implies a choice."""
    assert "--offline" not in SEARCH


def test_the_launcher_script_is_gone():
    assert not (REPO / "scripts" / "start-ollama.bat").exists()


# --- the scheduled task ----------------------------------------------------


def _ps1() -> str:
    return (REPO / "scripts" / "register-scheduled-tasks.ps1").read_text(
        encoding="utf-8", errors="replace"
    )


def test_no_task_registers_ollama():
    """Scoped to the $tasks array. The $retired list names OllamaServe on
    purpose — the question is whether it is still REGISTERED."""
    block = _ps1().split("$tasks = @(", 1)[1].split(")", 1)[0]
    assert "CatalogRefresh" in block, "the $tasks block was not located correctly"
    assert "OllamaServe" not in block, "the logon task is still being registered"


def test_the_retired_task_is_still_actively_unregistered():
    """This must outlive the removal. A machine that already has the task keeps
    failing until something removes it, and Verdun10 still did on 2026-08-22 —
    three weeks after the task stopped being shipped."""
    ps1 = _ps1()
    assert "$retired" in ps1
    assert "EcosystemBrain-OllamaServe" in ps1
    assert "Unregister-ScheduledTask -TaskName $name" in ps1


def test_the_removal_is_verified_before_it_is_announced():
    """It printed `[retired]` unconditionally while `Unregister` failed with
    "Access denied" under `-ErrorAction SilentlyContinue`, so the one machine
    that needed the retire list was told it had worked. Announce the removal
    only once a re-query says the task is actually gone."""
    ps1 = _ps1()
    retire = ps1.split("foreach ($name in $retired)", 1)[1].split("$settings =", 1)[0]
    assert "[STUCK]" in retire, "a failed removal must be reported as failed"
    assert retire.count("Get-ScheduledTask -TaskName $name") >= 2, (
        "the removal has to be re-queried, not assumed"
    )
    assert "exit 1" in ps1, "a stuck task must make the script exit non-zero"
