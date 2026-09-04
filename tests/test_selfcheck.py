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


# --- the OTHER toolchain: node, npm, and the template's own dependencies ----
# The ruff lesson was learned in Python and never applied to TypeScript. On
# 2026-09-03 two commits that touched nothing but memory notes turned CI red on
# both platforms: `npm install` crashed in arborist with "Cannot read properties
# of null (reading 'edgesOut')" while the same template scaffolded green locally.
# Nothing in the repo had changed — the template carried five floating `^`
# ranges and no lockfile, and CI installed no node at all, so the build was a
# function of the date and of whatever the runner image shipped that morning.

TEMPLATES = REPO / "templates"


def _template_package_jsons() -> list[Path]:
    return sorted(TEMPLATES.glob("*/package.json"))


def test_template_dependencies_pin_exact_versions():
    """`^1.9.0` is a promise about the future from a package you do not own."""
    import json

    checked = 0
    for path in _template_package_jsons():
        pkg = json.loads(path.read_text(encoding="utf-8"))
        for field in ("dependencies", "devDependencies"):
            for name, spec in (pkg.get(field) or {}).items():
                checked += 1
                assert re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", spec), (
                    f"{path.parent.name}/{field}: {name} is {spec!r}, not an exact version"
                )
    assert checked >= 5, f"expected the template's dependency specs, scanned {checked}"


def test_ci_pins_node_to_an_exact_patch():
    """npm ships *with* node, so pinning the major would let the thing that
    actually broke keep drifting."""
    text = CI.read_text(encoding="utf-8")
    assert "actions/setup-node@" in text, "CI installs no node; the runner image decides"
    m = re.search(r"node-version:\s*'?([0-9][^\s'\"]*)'?", text)
    assert m, "no node-version pinned in CI"
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", m.group(1)), (
        f"node-version is {m.group(1)!r}, not an exact patch version"
    )


def test_every_ci_action_is_pinned_to_a_commit_sha():
    """A tag is mutable; whoever owns the action repo can repoint it at new code
    that then runs with a GITHUB_TOKEN. Same reasoning as agent-pinning."""
    # The trailing "# v7.0.0" comment is what makes the pin legible; allow it.
    uses = re.findall(r"^\s*uses:\s*(\S+)", CI.read_text(encoding="utf-8"), re.M)
    assert uses, "no actions found in CI"
    for ref in uses:
        _repo, _, rev = ref.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", rev), f"{ref} is not pinned to a commit SHA"
