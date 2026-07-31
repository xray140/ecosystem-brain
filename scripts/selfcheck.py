#!/usr/bin/env python3
"""Self-validation for ecosystem-brain — run locally or in CI.

Checks, in order (fails fast with a non-zero exit on any problem):
  1. Every committed JSON file parses.
  2. Every agent in agents/ passes the security scanner (no HIGH-risk content).
  3. The init profile engine resolves all build types without error.
  4. The memory vault indexes cleanly.
  5. The pytest suite passes.
  6. Ruff is clean — the same invocation CI runs, so local and CI cannot diverge.
  7. Local agent frontmatter meets the standard (name/description/tools/model).

Both pytest and ruff come from requirements-dev.txt, the pinned dev toolchain.

Usage:
    uv run --no-project python scripts/selfcheck.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_agent import scan, worst

REPO = Path(__file__).resolve().parent.parent
fails: list[str] = []


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    fails.append(msg)


def check_json() -> None:
    print("1. JSON parses")
    globs = [
        "registry/*.json",
        ".claude-plugin/*.json",
        "hooks/*.json",
        "*.json",
        "templates/**/*.json",
        "memory/.obsidian/*.json",
    ]
    seen: set[Path] = set()
    for g in globs:
        for p in REPO.glob(g):
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                fail(f"{p.relative_to(REPO)}: {e}")
    if not fails:
        ok(f"{len(seen)} JSON files valid")


def check_agents() -> None:
    print("2. Third-party agents pass security scan")
    # The scan gates UNTRUSTED (github-sourced) content. Local agents we authored
    # (e.g. security-auditor) legitimately describe risky patterns to detect them,
    # so they're trusted, not strict-failed.
    installed = json.loads((REPO / "registry" / "installed.json").read_text(encoding="utf-8"))
    local = {a["name"] for a in installed.get("agents", []) if a.get("source") == "local"}
    agents = sorted((REPO / "agents").glob("*.md"))
    checked = high = 0
    for a in agents:
        level = worst(scan(a.read_text(encoding="utf-8")))
        if a.stem in local:
            continue  # trusted, authored here
        checked += 1
        if level == "HIGH":
            high += 1
            fail(f"third-party agent {a.name} scans HIGH-risk")
    if high == 0:
        ok(f"{checked} third-party agents scanned, none HIGH "
           f"({len(agents) - checked} trusted local skipped)")


def check_profiles() -> None:
    print("3. Init profile engine resolves all build types")
    import init_project as ip

    profiles = ip.load(ip.PROFILES)
    builds = list(profiles["build_types"])
    for b in builds:
        stack = "react" if profiles["build_types"][b]["ask_stack"] else None
        cfg = ip.resolve(profiles, b, "product", ["api-keys", "money"], stack)
        _resolved, dropped = ip.classify_agents(cfg["agents"], profiles)
        if dropped:
            fail(f"build '{b}' maps to unknown agents: {dropped}")
        # composing AGENTS.md must not raise
        ip.compose_agents_md(f"demo-{b}", cfg)
    ok(f"{len(builds)} build types resolve, all agents in catalog/local")


def check_memory() -> None:
    print("4. Memory vault indexes")
    r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
        [sys.executable, str(REPO / "skills/memory/memory-index.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        fail(f"memory-index failed: {r.stderr.strip()[:80]}")
    else:
        ok("vault indexed")


DEV_REQS = REPO / "requirements-dev.txt"
LINT_PATHS = ("scripts", "tests", "hooks", "skills")


def _uv_tool() -> list[str]:
    """`uv run` prefix that installs the pinned dev toolchain, project-free."""
    return [
        "uv",
        "run",
        "--with-requirements",
        str(DEV_REQS),
        "--no-project",
    ]


def check_lint() -> None:
    """Run the same ruff invocation CI runs.

    Without this, the local gate stays green while CI goes red — which is exactly
    how 44 lint findings accumulated unnoticed once ruff's default rule set moved.
    A gate that a change can pass locally and fail remotely is not a gate.
    """
    print("6. Lint (ruff)")
    if shutil.which("uv") is None:
        ok("uv not found — ruff skipped")
        return
    r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
        [*_uv_tool(), "ruff", "check", *LINT_PATHS, "--output-format", "concise"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if r.returncode != 0:
        tail = "\n      ".join((r.stdout + r.stderr).strip().splitlines()[-12:])
        fail(f"ruff found problems:\n      {tail}")
    else:
        ok(f"ruff clean across {', '.join(LINT_PATHS)}")


def check_tests() -> None:
    print("5. Unit tests (pytest)")
    tests_dir = REPO / "tests"
    if not tests_dir.is_dir():
        ok("no tests/ dir — skipped")
        return
    if shutil.which("uv") is None:
        ok("uv not found — pytest skipped")
        return
    # Nested uv run: pulls the PINNED pytest into an ephemeral env, ignores any
    # project. Pinned via requirements-dev.txt so this gate and CI can never
    # disagree about which pytest ran.
    r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
        [*_uv_tool(), "pytest", "-q", "tests"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if r.returncode != 0:
        tail = "\n      ".join((r.stdout + r.stderr).strip().splitlines()[-12:])
        fail(f"pytest failed:\n      {tail}")
    else:
        summary = (r.stdout.strip().splitlines() or ["passed"])[-1]
        ok(f"pytest: {summary}")


KNOWN_MODELS = {"inherit", "fable", "opus", "sonnet", "haiku"}


def frontmatter_problems(text: str) -> list[str]:
    """Lint an agent definition against the first-party standard.

    Required: YAML frontmatter with name, description, tools (explicit
    least-privilege grant), and model (a known alias or a full claude-* id).
    """
    if not text.startswith("---"):
        return ["missing frontmatter"]
    end = text.find("\n---", 3)
    if end == -1:
        return ["unterminated frontmatter"]
    fm = text[3:end]
    problems = [
        f"missing '{key}:'"
        for key in ("name", "description", "tools", "model")
        if not re.search(rf"^{key}:", fm, re.M)
    ]
    m = re.search(r"^model:\s*(\S+)", fm, re.M)
    if m and m.group(1) not in KNOWN_MODELS and not m.group(1).startswith("claude-"):
        problems.append(f"unknown model '{m.group(1)}'")
    return problems


def check_frontmatter() -> None:
    print("7. Local agent frontmatter meets the standard")
    installed = json.loads((REPO / "registry" / "installed.json").read_text(encoding="utf-8"))
    local = {a["name"] for a in installed.get("agents", []) if a.get("source") == "local"}
    checked = 0
    for a in sorted((REPO / "agents").glob("*.md")):
        if a.stem not in local:
            continue  # third-party definitions are upstream-owned; not linted
        checked += 1
        for p in frontmatter_problems(a.read_text(encoding="utf-8")):
            fail(f"agents/{a.name}: {p}")
    if not any(m.startswith("agents/") for m in fails):
        ok(f"{checked} local agents conform (name/description/tools/model)")


def main() -> int:
    print("ecosystem-brain selfcheck\n")
    check_json()
    check_agents()
    check_profiles()
    check_memory()
    check_tests()
    check_lint()
    check_frontmatter()
    print()
    if fails:
        print(f"[!] {len(fails)} failure(s)")
        return 1
    print("[ok] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
