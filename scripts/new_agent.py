#!/usr/bin/env python3
"""Recruiter: scaffold a new first-party agent to the ecosystem's standard.

Composes a convention-compliant agent definition (focused frontmatter, a
least-privilege `tools` allowlist, an explicit `model`, a description that says
when to delegate, and a numbered When-invoked workflow), then runs it through the
real gate — scan_agent.py blocks HIGH-risk content, install-agent.py registers it.

So new agents are born to standard instead of hand-rolled and drifting.

Usage:
    # preview only (compose + scan, no write)
    uv run --no-project python scripts/new_agent.py --name doc-linter \\
        --description "Lints docs for broken links. Use proactively before a docs PR." \\
        --role "You are a documentation linter." --tools Read,Grep,Glob \\
        --step "Find changed docs" --step "Check links" --returns "a list of broken links"

    # compose, scan, and register (writes agents/<name>.md + ~/.claude, tracks it)
    uv run --no-project python scripts/new_agent.py ... --register
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_agent import format_report, scan, worst  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "scripts" / "install-agent.py"

KNOWN_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "Bash", "WebFetch", "WebSearch"}
KNOWN_MODELS = {"inherit", "fable", "opus", "sonnet", "haiku"}
NAME_RE = re.compile(r"[a-z][a-z0-9-]*$")


def validate(name: str, tools: list[str], model: str) -> list[str]:
    """Return convention warnings/errors (empty = clean)."""
    problems: list[str] = []
    if not NAME_RE.fullmatch(name):
        problems.append(f"name '{name}' must be kebab-case (lowercase, hyphens)")
    if not tools:
        problems.append("grant at least one tool (least-privilege, but non-empty)")
    for t in tools:
        if t not in KNOWN_TOOLS:
            problems.append(
                f"unknown tool '{t}' (known: {', '.join(sorted(KNOWN_TOOLS))})"
            )
    if model not in KNOWN_MODELS:
        problems.append(f"model '{model}' not in {sorted(KNOWN_MODELS)}")
    return problems


def compose_agent(
    name: str,
    description: str,
    role: str,
    tools: list[str],
    model: str = "inherit",
    steps: list[str] | None = None,
    returns: str | None = None,
) -> str:
    steps = steps or ["...", "...", "..."]
    lines = ["---", f"name: {name}", f"description: {description}", "tools:"]
    lines += [f"  - {t}" for t in tools]
    lines += [f"model: {model}", "---", role, "", "When invoked:"]
    lines += [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    lines += ["", f"Return: {returns or '...'}."]
    return "\n".join(lines) + "\n"


def register(content: str, name: str) -> int:
    """Write to a temp file and hand to install-agent (scan-gates + registers)."""
    tmp = Path(tempfile.gettempdir()) / f"{name}.md"
    tmp.write_text(content, encoding="utf-8", newline="\n")
    try:
        r = subprocess.run(
            [
                "uv",
                "run",
                "--no-project",
                "python",
                str(INSTALLER),
                "--file",
                str(tmp),
                "--type",
                "agent",
                "--name",
                name,
            ],
            text=True,
        )
        return r.returncode
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--name", required=True)
    ap.add_argument(
        "--description",
        required=True,
        help="say WHEN to delegate ('use proactively …')",
    )
    ap.add_argument("--role", default="You are a focused, single-purpose agent.")
    ap.add_argument(
        "--tools",
        required=True,
        help="comma list, least-privilege (e.g. Read,Grep,Glob)",
    )
    ap.add_argument(
        "--model", default="inherit", choices=sorted(KNOWN_MODELS),
        help="route by task shape: haiku for checklist/mechanical work, sonnet "
             "for spec-driven code-gen, inherit (rides the session model) for "
             "judgment/diagnosis; fable/opus only with a clear reason "
             "(see memory/decisions/model-routing.md)",
    )
    ap.add_argument(
        "--step", action="append", dest="steps", help="a When-invoked step (repeatable)"
    )
    ap.add_argument("--returns", help="what the agent returns")
    ap.add_argument("--register", action="store_true", help="scan-gate and install it")
    args = ap.parse_args(argv)

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    problems = validate(args.name, tools, args.model)
    if problems:
        print("convention problems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    if "use " not in args.description.lower():
        print(
            "  [warn] description should say when to delegate (e.g. 'Use proactively …')"
        )

    content = compose_agent(
        args.name,
        args.description,
        args.role,
        tools,
        args.model,
        args.steps,
        args.returns,
    )
    print(f"--- composed agents/{args.name}.md ---\n{content}")

    findings = scan(content)
    level = worst(findings)
    if findings:
        print(f"self-scan ({level}):\n{format_report(findings)}")
    if level == "HIGH":
        print(
            "\n[BLOCKED] composed agent scans HIGH — refine it (this should not happen for a skeleton)."
        )
        return 2

    if args.register:
        print("\nregistering ...")
        return register(content, args.name)
    print("\n[ok] preview only — re-run with --register to scan-gate and install.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
