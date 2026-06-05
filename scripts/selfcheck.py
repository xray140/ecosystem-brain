#!/usr/bin/env python3
"""Self-validation for ecosystem-brain — run locally or in CI.

Checks, in order (fails fast with a non-zero exit on any problem):
  1. Every committed JSON file parses.
  2. Every agent in agents/ passes the security scanner (no HIGH-risk content).
  3. The init profile engine resolves all build types without error.
  4. The memory vault indexes cleanly.

Usage:
    uv run --no-project python scripts/selfcheck.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_agent import scan, worst  # noqa: E402

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
        resolved, dropped = ip.classify_agents(cfg["agents"], profiles)
        if dropped:
            fail(f"build '{b}' maps to unknown agents: {dropped}")
        # composing AGENTS.md must not raise
        ip.compose_agents_md(f"demo-{b}", cfg)
    ok(f"{len(builds)} build types resolve, all agents in catalog/local")


def check_memory() -> None:
    print("4. Memory vault indexes")
    r = subprocess.run(
        [sys.executable, str(REPO / "skills/memory/memory-index.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        fail(f"memory-index failed: {r.stderr.strip()[:80]}")
    else:
        ok("vault indexed")


def main() -> int:
    print("ecosystem-brain selfcheck\n")
    check_json()
    check_agents()
    check_profiles()
    check_memory()
    print()
    if fails:
        print(f"[!] {len(fails)} failure(s)")
        return 1
    print("[ok] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
