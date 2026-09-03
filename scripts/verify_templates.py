#!/usr/bin/env python3
"""Scaffold each template for real and run its own build+test baseline.

CI smoke-tests the init *engine* with `--plan`, which writes nothing. So the
engine is covered and the **templates are not**: a dependency could break, a
ruff rule could tighten, a tsconfig option could be removed, and nothing would
notice until the next person scaffolded a project and found it red on arrival.

The ecosystem already applies a "verified green baseline" to the projects it
creates. This applies the same rule one level up, to the blueprints those
projects are made from — the check it was preaching but not running on itself.

Each template is scaffolded into a temp directory and its own verify commands
are run there. Nothing is written inside the repo.

Usage:
    uv run --no-project python scripts/verify_templates.py
    uv run --no-project python scripts/verify_templates.py --only python-project
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import init_project as ip  # the single source of each template's baseline commands

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
SCAFFOLD = REPO / "scripts" / "scaffold.py"

# The tool each template's baseline needs. Absent -> skip rather than fail, so a
# machine without node can still verify the python template.
RUNTIME = {"python-project": "uv", "typescript-project": "npm"}


def templates() -> list[str]:
    """Template names, i.e. directories with baseline commands defined."""
    if not TEMPLATES.is_dir():
        return []
    return sorted(
        d.name
        for d in TEMPLATES.iterdir()
        if d.is_dir() and not d.name.startswith("_") and ip.verify_commands(d.name)
    )


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    # resolve_exe: on Windows `npm` is `npm.CMD` and a bare name raises
    # FileNotFoundError. Shared with init_project so both paths behave alike.
    return subprocess.run(  # noqa: PLW1510 — returncode is inspected by callers
        ip.resolve_exe(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# What to ask each runtime for its version. Printed on EVERY run, pass or fail.
#
# On 2026-09-03 this step went red on ubuntu and stayed green on windows with
# the same commit, and neither run recorded the toolchain it used — so "the same
# code failed there and passed here" had nothing to attach to, and the npm
# version had to be inferred from the node version in the workflow file. A
# report that names the error but not the thing that produced it cannot be
# compared against the last green run, which is the only comparison that
# identifies an environment fault. See decisions/verification-integrity.
VERSION_PROBES: dict[str, tuple[list[str], ...]] = {
    "npm": (["node", "--version"], ["npm", "--version"]),
    "uv": (["uv", "--version"],),
}


def runtime_versions(tool: str) -> str:
    """One line naming the versions `tool`'s baseline will run on."""
    parts: list[str] = []
    for probe in VERSION_PROBES.get(tool, ()):
        try:
            r = _run(probe, cwd=REPO)
        except OSError as e:  # pragma: no cover — probe absent is reported, not raised
            parts.append(f"{probe[0]}: unavailable ({e.__class__.__name__})")
            continue
        out = (r.stdout or r.stderr).strip().splitlines()
        if not out:
            parts.append(f"{probe[0]}: no output")
            continue
        # `uv --version` answers "uv 0.11.23 (3cdf50e0 2026-06-19 x86_64-...)":
        # drop the build metadata, and don't print the tool's name twice.
        ver = out[0].split("(")[0].strip()
        parts.append(ver if ver.startswith(probe[0]) else f"{probe[0]} {ver}")
    return ", ".join(parts) or "no version probe for this runtime"


def verify(template: str, workdir: Path) -> tuple[bool, str]:
    """(ok, detail) for one template, scaffolded fresh under workdir."""
    tool = RUNTIME.get(template)
    if tool and not shutil.which(tool):
        return True, f"skipped — {tool} not on PATH"

    name = f"verify-{template}"
    r = _run(
        [
            "uv",
            "run",
            "--no-project",
            "python",
            str(SCAFFOLD),
            "--type",
            template,
            "--name",
            name,
            "--templates-root",
            str(TEMPLATES),
            "--dest-root",
            str(workdir),
        ],
        cwd=REPO,
    )
    if r.returncode != 0:
        return False, f"scaffold failed: {(r.stderr or r.stdout).strip()[:200]}"

    dest = workdir / name
    for cmd in ip.verify_commands(template):
        c = _run(cmd, cwd=dest)
        if c.returncode != 0:
            tail = "\n      ".join((c.stdout + c.stderr).strip().splitlines()[-10:])
            return False, f"`{' '.join(cmd)}` failed:\n      {tail}"
    return True, "scaffolded and its baseline is green"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--only", help="verify just this template")
    args = ap.parse_args(argv)

    names = templates()
    if args.only:
        if args.only not in names:
            print(f"[error] unknown template '{args.only}' — have: {', '.join(names)}")
            return 1
        names = [args.only]

    print(f"verifying {len(names)} template(s): {', '.join(names)}\n")
    if not names:
        print("[ok] no templates with a baseline to verify")
        return 0

    failed = 0
    with tempfile.TemporaryDirectory(prefix="eco-templates-") as tmp:
        workdir = Path(tmp)
        for template in names:
            tool = RUNTIME.get(template)
            if tool:
                print(f"  [--] {template:22s} runtime: {runtime_versions(tool)}")
            ok, detail = verify(template, workdir)
            print(f"  [{'ok' if ok else '!!'}] {template:22s} {detail}")
            failed += not ok

    print()
    if failed:
        print(f"[!] {failed} template(s) do not produce a green project.")
        return 1
    print("[ok] every template still scaffolds into a green project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
