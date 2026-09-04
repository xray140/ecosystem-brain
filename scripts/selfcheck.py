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
  9. memory/roadmap.md still describes this repo.

Both pytest and ruff come from requirements-dev.txt, the pinned dev toolchain.

Usage:
    uv run --no-project python scripts/selfcheck.py
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_agent import RULES, scan, worst

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO = Path(__file__).resolve().parent.parent
fails: list[str] = []


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    fails.append(msg)


def skip(msg: str) -> None:
    """The gate could not run — neither a pass nor a finding.

    Deliberately not `ok`: printing [ok] for a check that never executed is
    how a green run stops meaning anything.
    """
    print(f"  [skip] {msg}")


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
        # --dry-run, not --check: this asserts the indexer can parse every note.
        # --check judges whether memory/index.json is CURRENT, which is a
        # different question and unanswerable here — the manifest is gitignored,
        # so on a fresh clone (CI) there is none, and gating on it would fail
        # every build. Freshness is the heartbeat's job: it refreshes, then gates.
        [sys.executable, str(REPO / "skills/memory/memory-index.py"), "--dry-run"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        fail(f"memory-index failed: {r.stderr.strip()[:80]}")
    else:
        ok("vault parses — every note walked by the indexer")


DEV_REQS = REPO / "requirements-dev.txt"
LINT_PATHS = ("scripts", "tests", "hooks", "skills")


# `uv run --with-requirements` resolves the pinned dev toolchain from PyPI, so
# with no network BOTH gates below exit non-zero with a DNS error rather than a
# finding. Reporting that as "pytest failed" / "ruff found problems" is a false
# accusation about the code, and it is what turned the offline weekly heartbeat
# red on 2026-08-20 while the suite was in fact green. Name it for what it is.
NETWORK_ERRORS = ("Failed to fetch", "dns error", "error sending request", "Request failed after")


# Evidence the tool actually RAN. The network signatures alone cannot separate
# "uv could not fetch the toolchain" from "the toolchain ran and the suite went
# red quoting a network error" — and the second is not hypothetical: the phrases
# live in this repo's own corpus (tests/test_selfcheck_checks.py, DNS_ERROR), so
# a failure in the very test guarding this branch would silence the branch. A
# red run reported as "did NOT run" exits 0, and the git pre-push hook, CI and
# the weekly heartbeat all gate on that exit code.
PYTEST_RAN = re.compile(r"\b\d+ (?:passed|failed|error|errors|xfailed|deselected)\b")
RUFF_RAN = re.compile(r"(?m)^(?:.+:\d+:\d+: \w+|All checks passed|Found \d+ error)")


def _toolchain_unreachable(output: str, ran: re.Pattern[str] | None = None) -> bool:
    """True only when the toolchain could not be fetched AND the tool never ran.

    `ran` is the proof-of-execution pattern for the tool in question. Passing
    None keeps the old, weaker meaning and is only for callers that have no such
    proof — there are none today.
    """
    if ran is not None and ran.search(output):
        return False
    return any(sig in output for sig in NETWORK_ERRORS)


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
        text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO),
    )
    if r.returncode != 0:
        out = r.stdout + r.stderr
        if _toolchain_unreachable(out, RUFF_RAN):
            skip("pinned toolchain unreachable (offline) — ruff did NOT run")
            return
        tail = "\n      ".join(out.strip().splitlines()[-12:])
        fail(f"ruff found problems:\n      {tail}")
    else:
        ok(f"ruff clean across {', '.join(LINT_PATHS)}")


#: Coverage floor, as a ratchet rather than a target. Measured 93% when set, so
#: ~50 uncovered statements of headroom: ordinary churn passes, a new untested
#: module of any size does not. A floor above reality gets bypassed within a
#: week; one far below it is decoration. Raise it when the real figure moves up
#: and stays there — never lower it to make a red run green.
COVERAGE_FLOOR = 91
COVERED = ("scripts", "hooks/scripts", "skills")


def check_tests() -> None:
    print(f"5. Unit tests (pytest) + coverage floor {COVERAGE_FLOOR}%")
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
    cov_args = [f"--cov={target}" for target in COVERED]
    r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
        [
            *_uv_tool(),
            "pytest",
            "-q",
            "tests",
            *cov_args,
            "--cov-report=term",
            f"--cov-fail-under={COVERAGE_FLOOR}",
        ],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO),
    )
    out = r.stdout + r.stderr
    if r.returncode != 0:
        if _toolchain_unreachable(out, PYTEST_RAN):
            skip("pinned toolchain unreachable (offline) — pytest did NOT run")
            return
        # A coverage dip and a failing test are different problems with different
        # fixes, and pytest-cov reports both as exit 1. Calling a coverage dip
        # "pytest failed" is the same false accusation the offline case above
        # exists to avoid: it sends you reading a green suite for a broken test.
        floor_hit = next((ln for ln in out.splitlines() if "Required test coverage" in ln), None)
        if floor_hit and "failed" not in _pytest_summary(out):
            fail(
                f"coverage below the floor — the suite passed:\n      {floor_hit.strip()}\n"
                f"      Cover the new code, or justify an omit in .coveragerc."
            )
            return
        fail(f"pytest failed:\n      {_failure_detail(out)}")
    else:
        total = next(
            (ln.split()[-1] for ln in out.splitlines() if ln.startswith("TOTAL")), "?"
        )
        ok(f"pytest: {_pytest_summary(out)} — coverage {total}")


def _pytest_summary(out: str) -> str:
    """The `N passed, M skipped in Xs` line, wherever it landed in the output."""
    for line in reversed(out.strip().splitlines()):
        if " passed" in line or " failed" in line or " error" in line:
            return line.strip()
    return "passed"


def _failure_detail(out: str) -> str:
    """The lines naming what failed.

    Not a plain tail any more: with --cov the coverage table prints AFTER the
    failures, so the last dozen lines became table rows and the report said
    "pytest failed" while showing nothing about which test did. pytest's own
    "short test summary info" section is the part worth surfacing.
    """
    lines = out.strip().splitlines()
    for i, line in enumerate(lines):
        if "short test summary info" in line:
            return "\n      ".join(x for x in lines[i + 1 :] if x.strip())[:1200]
    return "\n      ".join(lines[-12:])


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



# --- 9. the note a fresh session reads first --------------------------------

ROADMAP = REPO / "memory" / "roadmap.md"


def _selfcheck_step_count() -> int:
    """How many checks main() CALLS — not how many are defined.

    A check that exists but is never called is exactly the sort of thing this
    file is supposed to notice.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    return sum(
        1
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id.startswith("check_")
    )


def roadmap_claims() -> list[tuple[str, str, str]]:
    """(label, pattern capturing the claim, what the repo actually says).

    Only facts that change DELIBERATELY are listed. Test count and coverage
    percentage move with almost every commit, so a gate on those would cry wolf
    until someone deleted it — which is why the note cites the coverage floor,
    a number that only moves when a person raises it.
    """
    # Imported here, not at module scope: the heartbeat is a consumer of this
    # file, and a top-level import would make the two mutually dependent.
    import maintenance

    profiles = json.loads((REPO / "registry" / "project-profiles.json").read_text(encoding="utf-8"))
    installed = json.loads((REPO / "registry" / "installed.json").read_text(encoding="utf-8"))
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    local = [a for a in installed.get("agents", []) if a.get("source") == "local"]
    return [
        ("version", r"^## Current state \(v([0-9]+\.[0-9]+\.[0-9]+)\)", plugin["version"]),
        ("commands", r"- \*\*(\d+) commands\*\*", str(len(list((REPO / "commands").glob("*.md"))))),
        ("build types", r"- \*\*(\d+) build types\*\*", str(len(profiles["build_types"]))),
        ("first-party agents", r"\*\*First-party squad\*\* \((\d+)\)", str(len(local))),
        ("selfcheck checks", r"`selfcheck\.py` = (\d+) checks", str(_selfcheck_step_count())),
        ("heartbeat checks", r"heartbeat = (\d+) checks", str(len(maintenance.CHECKS))),
        ("coverage floor", r"coverage floor \*\*(\d+)%\*\*", str(COVERAGE_FLOOR)),
        # The note has advertised a rule count since v4.3.x. Now that every rule
        # has a probe and a mutant (tests/test_scan_agent_rules.py), the number
        # means something — so it gets read back like the rest.
        ("scanner rules", r"`scan_agent\.py` \((\d+) rules\)", str(len(RULES))),
    ]


def check_roadmap() -> None:
    """The orientation note is an artefact like any other, and until now it was
    the only one with no reader.

    On 2026-09-03 it opened with "Current state (v4.4.3)" and cited 619 tests at
    89% coverage; the repo was at v4.8.0 with 756 at 93%. Nothing was broken —
    it had simply been written once and believed ever since, which is what every
    other check in this file exists to prevent.
    """
    print(f"9. {ROADMAP.name} describes this repo")
    text = ROADMAP.read_text(encoding="utf-8")
    checked = 0
    for label, pattern, actual in roadmap_claims():
        m = re.search(pattern, text, re.M)
        if m is None:
            # A vanished claim is worse than a wrong one: the gate goes quiet
            # and the note is free to drift again with nothing to say so.
            fail(f"roadmap: the '{label}' claim is gone — nothing left to check")
        elif m.group(1) != actual:
            fail(f"roadmap says {label} = {m.group(1)}, the repo says {actual}")
        else:
            checked += 1
    if not any(m.startswith("roadmap") for m in fails):
        ok(f"{checked} claims in memory/roadmap.md match the repo")


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
    check_roadmap()
    print()
    if fails:
        print(f"[!] {len(fails)} failure(s)")
        return 1
    print("[ok] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
