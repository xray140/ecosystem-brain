"""Tests for selfcheck's agent-frontmatter lint and the pinned dev toolchain.

The toolchain tests exist because an unpinned `--with ruff` once resolved a
newer ruff whose default rule set had widened, turning CI red with 44 findings
no commit introduced — while the local gate stayed green because it never ran
ruff at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import selfcheck as sc

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"
DEV_REQS = REPO / "requirements-dev.txt"


# --- pinned toolchain -----------------------------------------------------
def test_dev_requirements_pin_exact_versions():
    lines = [
        ln.strip()
        for ln in DEV_REQS.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert lines, "requirements-dev.txt has no pins"
    for ln in lines:
        assert re.match(r"^[A-Za-z0-9._-]+==[0-9]", ln), f"not an exact pin: {ln}"
    assert any(ln.startswith("ruff==") for ln in lines)
    assert any(ln.startswith("pytest==") for ln in lines)


def _ci_commands() -> list[str]:
    """The shell CI actually runs — comments explaining the pins don't count."""
    return [
        ln.strip()
        for ln in CI.read_text(encoding="utf-8").splitlines()
        if "uv run" in ln and not ln.strip().startswith("#")
    ]


def test_ci_installs_the_pinned_toolchain():
    """CI must not resolve ruff/pytest freshly on every run."""
    cmds = _ci_commands()
    assert cmds, "no uv run commands found in CI"
    for cmd in cmds:
        for tool in ("ruff", "pytest"):
            assert f"--with {tool}" not in cmd, f"CI resolves {tool} unpinned: {cmd}"
    assert any("--with-requirements requirements-dev.txt" in c for c in cmds)


def test_selfcheck_and_ci_lint_the_same_paths():
    """A path linted by one and not the other is a blind spot by construction."""
    ci_lint = next(c for c in _ci_commands() if "ruff check" in c)
    for path in sc.LINT_PATHS:
        assert f" {path}" in ci_lint, f"CI does not lint {path}"


def test_selfcheck_uses_the_pinned_toolchain():
    assert "--with-requirements" in sc._uv_tool()
    assert str(sc.DEV_REQS) in sc._uv_tool()


# --- frontmatter lint -----------------------------------------------------

GOOD = """---
name: demo
description: Does a thing. Use proactively when needed.
tools:
  - Read
model: haiku
---
Body.
"""


def test_conformant_agent_has_no_problems():
    assert sc.frontmatter_problems(GOOD) == []


def test_full_model_id_is_accepted():
    assert (
        sc.frontmatter_problems(GOOD.replace("model: haiku", "model: claude-fable-5"))
        == []
    )


def test_missing_frontmatter_flagged():
    assert sc.frontmatter_problems("no frontmatter here") == ["missing frontmatter"]


def test_missing_keys_flagged():
    text = "---\nname: x\n---\nBody.\n"
    problems = sc.frontmatter_problems(text)
    assert "missing 'description:'" in problems
    assert "missing 'tools:'" in problems
    assert "missing 'model:'" in problems


def test_unknown_model_flagged():
    problems = sc.frontmatter_problems(GOOD.replace("model: haiku", "model: gpt-5"))
    assert any("unknown model" in p for p in problems)


def test_fable_alias_accepted():
    assert sc.frontmatter_problems(GOOD.replace("model: haiku", "model: fable")) == []
