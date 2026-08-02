#!/usr/bin/env python3
"""Self-validation for ecosystem-brain — run locally or in CI.

Checks, in order (fails fast with a non-zero exit on any problem):
  1. Every committed JSON file parses.
  2. Every agent in agents/ passes the security scanner (no HIGH-risk content).
  3. The init profile engine resolves all build types without error.
  4. The memory vault indexes cleanly.
  5. The pytest suite passes.
  6. No installable file hardcodes an absolute path (they use {{ECOSYSTEM_ROOT}}).
  7. Ruff is clean — the same invocation CI runs, so local and CI cannot diverge.
  8. Local agent frontmatter meets the standard (name/description/tools/model).

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


# Files bootstrap installs into ~/.claude. These are the ones where a literal
# path is load-bearing at runtime, and therefore where one silently rots.
INSTALLABLE = ("commands/*.md", "agents/*.md", "skills/*/SKILL.md", "hooks/hooks.json")

# A Git Bash drive mount (/d/foo) or a Windows drive path (D:\foo, D:/foo).
# The lookbehind excludes only a word character, so `foo/d/bar` is not a match.
# It must NOT exclude a backtick: in markdown these paths live inside inline
# code spans, so anchoring against `` would blind the check to its main case.
ABSOLUTE_PATH = re.compile(r"(?<!\w)/[a-z]/[A-Za-z0-9_.-]+|[A-Za-z]:[\\/][A-Za-z0-9_.-]+")

TOKEN = "{{ECOSYSTEM_ROOT}}"  # noqa: S105 — a path placeholder, not a credential


def _is_illustration(line: str, match: re.Match[str]) -> bool:
    """True when the path is documenting the path convention rather than using it.

    `script-smith` has to be able to say that a hardcoded `/d/...` resolves to
    `D:\\d\\...` — that is the rule it exists to teach. An ellipsis is the
    difference between naming a shape and naming a location.
    """
    return "..." in match.group(0) or line[match.end() :].startswith(("\\...", "/..."))


# An instruction to copy repo files straight into ~/.claude. Six commands
# carried one. Following it overwrites every working command with a version
# containing the literal {{ECOSYSTEM_ROOT}} token — bootstrap is what expands
# that — and cannot copy skills at all, since skills/<name>/SKILL.md does not
# match a flat *.md glob. The fix is always bootstrap.py.
RAW_COPY = re.compile(r"\bcp\s+[^\n`]*\.claude", re.I)


def check_paths() -> None:
    """No installable file may hardcode a path, or tell you to cp over ~/.claude.

    Both rules are the same lesson. These files name the repo as
    {{ECOSYSTEM_ROOT}} and bootstrap expands it on the way out; anything that
    bypasses that rewrite — a literal path baked in, or a raw copy that skips
    it — installs something that cannot work. The literal-path half went
    unnoticed for months because bootstrap kept repairing it; the cp half sat in
    six commands, documented, waiting to be followed.
    """
    print("6. Installable files use {{ECOSYSTEM_ROOT}}, and never cp over ~/.claude")
    offenders = 0
    for pattern in INSTALLABLE:
        for p in sorted(REPO.glob(pattern)):
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if RAW_COPY.search(line):
                    rel = p.relative_to(REPO).as_posix()
                    fail(f"{rel}:{i}: copies into ~/.claude — use bootstrap.py")
                    offenders += 1
    for pattern in INSTALLABLE:
        for p in sorted(REPO.glob(pattern)):
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                for m in ABSOLUTE_PATH.finditer(line):
                    if _is_illustration(line, m):
                        continue
                    rel = p.relative_to(REPO).as_posix()
                    fail(f"{rel}:{i}: hardcoded path {m.group(0)!r} — use {TOKEN}")
                    offenders += 1
    if not offenders:
        print(f"  [ok]   no hardcoded paths in {len(INSTALLABLE)} installable file groups")


def check_lint() -> None:
    """Run the same ruff invocation CI runs.

    Without this, the local gate stays green while CI goes red — which is exactly
    how 44 lint findings accumulated unnoticed once ruff's default rule set moved.
    A gate that a change can pass locally and fail remotely is not a gate.
    """
    print("7. Lint (ruff)")
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
    print("8. Local agent frontmatter meets the standard")
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
    check_paths()
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
