#!/usr/bin/env python3
"""Compose and apply a tailored project config from interview answers.

The /ecosystem-brain:init command runs a sharp 3-4 question interview, then calls
this script. From minimal answers it resolves the best template, the right agent
set (validated against catalog.json), and composes a tailored AGENTS.md whose
every section reflects an answer — no generic boilerplate.

Two modes:
    --plan   resolve + print a summary and the composed AGENTS.md. No writes.
    --apply  scaffold the project, write the tailored AGENTS.md, install the
             resolved agents (each security-scanned), write a memory card.

Usage:
    uv run python scripts/init_project.py --plan  --build web --rigor product \\
        --touches api-keys,money --stack react --name betting-tracker
    uv run python scripts/init_project.py --apply --build cli --rigor product \\
        --touches none --name my-tool
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES = REPO_ROOT / "registry" / "project-profiles.json"
CATALOG = REPO_ROOT / "registry" / "catalog.json"
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"
INSTALLER = REPO_ROOT / "scripts" / "install-agent.py"
INDEXER = REPO_ROOT / "skills" / "memory" / "memory-index.py"
DEST_ROOT = REPO_ROOT.parent  # sibling of the repo, e.g. D:\Claude_projects

# Per-template fragments used to compose AGENTS.md.
TEMPLATE_BITS = {
    "python-project": {
        "runtime": "Python 3.12+ via `uv`",
        "test": "`pytest` — `uv run pytest -q`",
        "lint": "`ruff` (auto-applied on Write by the ecosystem hook)",
        "key_files": [
            ("src/{pkg}/core.py", "Business logic — keep pure, no I/O"),
            ("src/{pkg}/cli.py", "Entry point — thin wrapper over core"),
            ("tests/test_core.py", "Unit tests"),
            ("pyproject.toml", "Deps, tool config, entry points"),
        ],
        "setup": "uv sync\npre-commit install\ncp .env.example .env\nuv run pytest -q",
        "base_conventions": [
            "Core stays pure (no subprocess, network, or file I/O).",
            "Never `print()` in core — return a value or raise.",
        ],
    },
    "typescript-project": {
        "runtime": "Node.js / TypeScript 5, ESM",
        "test": "vitest — `npm test`",
        "lint": "Biome — `npm run lint` / `npm run format`",
        "key_files": [
            ("src/core.ts", "Pure business logic — no I/O"),
            ("src/index.ts", "Entry point — thin wrapper over core"),
            ("tests/core.test.ts", "Unit tests"),
            ("tsconfig.json", "Strict TypeScript config"),
        ],
        "setup": "npm install\ncp .env.example .env\nnpm test",
        "base_conventions": [
            "Core stays pure — no `process`, `fetch`, or `fs`.",
            "Use `.js` extensions in imports (ESM NodeNext). No `any` without a comment.",
        ],
    },
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def to_package(name: str) -> str:
    pkg = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not pkg:
        return "pkg"
    return pkg if pkg[0].isalpha() else f"pkg_{pkg}"


def resolve(
    profiles: dict, build: str, rigor: str, touches: list[str], stack: str | None
) -> dict:
    """Resolve answers -> {template, stack_note, agents, security, conventions}."""
    bt = profiles["build_types"][build]
    template = bt["template"]
    agents: list[str] = list(bt["agents"])
    conventions: list[str] = []
    security: list[str] = []

    rg = profiles["rigor"][rigor]
    agents += rg["agents_add"]
    conventions += rg["conventions"]

    for t in touches:
        s = profiles["sensitivity"].get(t)
        if s:
            agents += s["agents_add"]
            security += s["security_rules"]

    stack_note = ""
    if bt["ask_stack"] and stack:
        st = profiles["stacks"].get(stack)
        if st:
            agents += st["agents_add"]
            stack_note = st["note"]

    # dedupe, preserve order
    seen: set[str] = set()
    agents = [a for a in agents if not (a in seen or seen.add(a))]
    return {
        "template": template,
        "stack_blurb": bt["stack_blurb"],
        "stack_note": stack_note,
        "agents": agents,
        "security": security,
        "conventions": conventions,
    }


def classify_agents(names: list[str], profiles: dict) -> tuple[list[dict], list[str]]:
    """Split into installable (catalog github) + local + dropped(unknown)."""
    local = set(profiles.get("local_agents", []))
    catalog = (
        {a["name"]: a for a in load(CATALOG)["agents"]} if CATALOG.exists() else {}
    )
    resolved: list[dict] = []
    dropped: list[str] = []
    for n in names:
        if n in local:
            resolved.append({"name": n, "source": "local"})
        elif n in catalog:
            resolved.append(
                {
                    "name": n,
                    "source": "github",
                    "repo": catalog[n]["repo"],
                    "path": catalog[n]["path"],
                }
            )
        else:
            dropped.append(n)
    return resolved, dropped


def compose_agents_md(name: str, cfg: dict) -> str:
    pkg = to_package(name)
    bits = TEMPLATE_BITS[cfg["template"]]
    L = [
        f"# {name} — agent operating rules",
        "",
        "Cross-tool instructions (AGENTS.md standard). Read by Claude Code, Gemini",
        "CLI, OpenAI Codex, Cursor, Copilot. Part of the claude-unified-ecosystem.",
        "",
        "## Stack",
        f"- {cfg['stack_blurb']}",
    ]
    if cfg["stack_note"]:
        L.append(f"- **Stack:** {cfg['stack_note']}")
    L += [
        f"- **Runtime:** {bits['runtime']}",
        f"- **Tests:** {bits['test']}",
        f"- **Lint/format:** {bits['lint']}",
        "- **Secrets:** `.env` only (gitignored); never committed, never echoed",
    ]
    if cfg["security"]:
        L += ["", "## Security"]
        L += [f"- {r}" for r in cfg["security"]]
    L += ["", "## Workflow & rigor"]
    L += [f"- {c}" for c in cfg["conventions"]]
    L += ["", "## Key files", "| File | Purpose |", "|------|---------|"]
    L += [f"| `{p.format(pkg=pkg)}` | {d} |" for p, d in bits["key_files"]]
    L += [
        "",
        "## First-time setup",
        "```bash",
        bits["setup"],
        "```",
        "",
        "## Conventions",
    ]
    L += [f"- {c}" for c in bits["base_conventions"]]
    return "\n".join(L) + "\n"


def memory_card(name: str, cfg: dict, agents: list[dict]) -> str:
    stack = "typescript" if cfg["template"] == "typescript-project" else "python"
    agent_names = ", ".join(a["name"] for a in agents) or "none"
    return (
        f"---\ntype: project\nstatus: active\ncreated: see-git\n"
        f"stack: [{stack}]\ntags: [project, {stack}]\n---\n"
        f"# {name}\n\nConfigured via /ecosystem-brain:init.\n\n"
        f"## Stack\n{cfg['stack_blurb']}\n"
        f"{cfg['stack_note']}\n\n"
        f"## Agents installed\n{agent_names}\n\n"
        f"## Paths\n- Project: `{(DEST_ROOT / name)}`\n"
    )


def print_summary(
    name: str, cfg: dict, resolved: list[dict], dropped: list[str]
) -> None:
    print(f"\n=== init plan: {name} ===")
    print(f"  template : {cfg['template']}")
    if cfg["stack_note"]:
        print(f"  stack    : {cfg['stack_note']}")
    print(f"  agents   : {len(resolved)} resolved")
    for a in resolved:
        src = a["source"] if a["source"] == "local" else f"github:{a['repo']}"
        print(f"             - {a['name']:24s} ({src})")
    if dropped:
        print(f"  dropped  : {', '.join(dropped)} (not in catalog — skipped)")
    print(f"  dest     : {DEST_ROOT / name}")
    print("\n--- composed AGENTS.md preview ---")
    print(compose_agents_md(name, cfg))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def apply(name: str, cfg: dict, resolved: list[dict]) -> int:
    dest = DEST_ROOT / name
    print(f"scaffolding {cfg['template']} -> {dest} ...")
    r = run(
        [
            "uv",
            "run",
            "python",
            str(SCAFFOLD),
            "--type",
            cfg["template"],
            "--name",
            name,
            "--templates-root",
            str(REPO_ROOT / "templates"),
            "--dest-root",
            str(DEST_ROOT),
            "--git",
        ]
    )
    if r.returncode != 0:
        print(f"[error] scaffold failed: {r.stderr.strip() or r.stdout.strip()}")
        return 1
    print("  [ok] scaffolded")

    (dest / "AGENTS.md").write_text(compose_agents_md(name, cfg), encoding="utf-8")
    print("  [ok] wrote tailored AGENTS.md")

    installed = 0
    for a in resolved:
        if a["source"] == "local":
            print(f"  [ok]      {a['name']} (local, already available)")
            installed += 1
            continue
        ir = run(
            [
                "uv",
                "run",
                "python",
                str(INSTALLER),
                "--repo",
                a["repo"],
                "--path",
                a["path"],
            ]
        )
        if ir.returncode == 0:
            installed += 1
            print(f"  [ok]      {a['name']} (installed + scanned)")
        elif ir.returncode == 2:
            print(f"  [BLOCKED] {a['name']} (security scan)")
        else:
            print(f"  [error]   {a['name']}: {ir.stderr.strip()[:60]}")

    card = REPO_ROOT / "memory" / "projects" / f"{name}.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(memory_card(name, cfg, resolved), encoding="utf-8")
    run(["uv", "run", "python", str(INDEXER)])
    print("  [ok] memory card + index refreshed")
    print(f"\ndone. {installed}/{len(resolved)} agents ready. cd {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--build", required=True, choices=["web", "api", "cli", "library"])
    ap.add_argument(
        "--rigor", required=True, choices=["prototype", "product", "production"]
    )
    ap.add_argument(
        "--touches", default="none", help="comma list: api-keys,pii,money,none"
    )
    ap.add_argument("--stack", choices=["react", "vue", "svelte", "decide"])
    ap.add_argument("--name", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    profiles = load(PROFILES)
    touches = [t.strip() for t in args.touches.split(",") if t.strip()]
    cfg = resolve(profiles, args.build, args.rigor, touches, args.stack)
    resolved, dropped = classify_agents(cfg["agents"], profiles)

    if args.plan:
        print_summary(args.name, cfg, resolved, dropped)
        return 0
    return apply(args.name, cfg, resolved)


if __name__ == "__main__":
    raise SystemExit(main())
