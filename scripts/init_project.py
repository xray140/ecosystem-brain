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
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES = REPO_ROOT / "registry" / "project-profiles.json"
CATALOG = REPO_ROOT / "registry" / "catalog.json"
CATALOG_SEED = REPO_ROOT / "registry" / "catalog.seed.json"


def catalog_path():
    """The live catalog, else the committed seed, else None.

    catalog.json is gitignored (a scheduled task rewrites it weekly). Kept in
    step with catalog.py and the suggest-agents hook by a test that asserts all
    three resolve to the same file.
    """
    if CATALOG.exists():
        return CATALOG
    if CATALOG_SEED.exists():
        return CATALOG_SEED
    return None
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"
INSTALLER = REPO_ROOT / "scripts" / "install-agent.py"
INDEXER = REPO_ROOT / "skills" / "memory" / "memory-index.py"
# The vault `--apply` writes its project card and MOC entry into. Overridable
# for the same reason DEST_ROOT is: without it, running the flagship command even
# once dirties this repo — a memory card, a MOC line, a registry mutation — so it
# was never exercised end to end, and a Windows crash in its own baseline step
# survived unnoticed until 2026-08-02. A command you cannot run is a command you
# cannot test.
VAULT = Path(os.environ.get("ECOSYSTEM_VAULT") or REPO_ROOT / "memory")
PROJECTS_MOC = VAULT / "projects-moc.md"
# Sibling of the repo by default (e.g. D:\claude-projects); overridable for tests.
DEST_ROOT = Path(os.environ.get("ECOSYSTEM_DEST_ROOT") or REPO_ROOT.parent)


def _today() -> str:
    """Today's date, local, as an aware computation.

    Vault cards are read by a human in their own timezone, so the local date is
    the right one — but it is derived from an aware UTC instant rather than a
    naive `date.today()`, so the value can never depend on an ambient clock the
    process didn't declare.
    """
    return datetime.now(UTC).astimezone().date().isoformat()


# Stack -> decision notes a project card should link into (de-orphans the graph).
STACK_DECISIONS = {
    "python": ["windows-python-invocation", "powershell-utf8-bom"],
    "typescript": [],
}
# Per-template "green baseline" — build + test commands run after scaffolding to
# prove the scaffold actually works before handing it over.
VERIFY = {
    "python-project": [["uv", "sync"], ["uv", "run", "pytest", "-q"]],
    "typescript-project": [["npm", "install"], ["npm", "test"]],
}

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
    # Falling back to {} here is not harmless: every catalog agent then lands in
    # `dropped` as unknown, so a fresh clone would quietly scaffold projects with
    # their agent roster stripped. The seed keeps that from being the default.
    path = catalog_path()
    catalog = {a["name"]: a for a in load(path)["agents"]} if path else {}
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
    L += ["- Context discipline: keep this file lean; delegate high-volume reads to subagents; `/clear` between unrelated tasks."]
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
    stack = card_stack(cfg)
    agent_names = ", ".join(a["name"] for a in agents) or "none"
    # Links de-orphan the card in the graph: the projects hub + stack decisions.
    links = ["[[projects-moc]]"] + [f"[[{d}]]" for d in STACK_DECISIONS.get(stack, [])]
    return (
        f"---\ntype: project\nstatus: active\ncreated: {_today()}\n"
        f"stack: [{stack}]\ntags: [project, {stack}]\n---\n"
        f"# {name}\n\nConfigured via /ecosystem-brain:init.\n\n"
        f"## Stack\n{cfg['stack_blurb']}\n"
        f"{cfg['stack_note']}\n\n"
        f"## Agents installed\n{agent_names}\n\n"
        f"## Paths\n- Project: `{(DEST_ROOT / name)}`\n\n"
        f"## Links\n" + "\n".join(f"- {link}" for link in links) + "\n"
    )


def card_stack(cfg: dict) -> str:
    return "typescript" if cfg["template"] == "typescript-project" else "python"


def env_key(name: str) -> str:
    """Normalize a free-text API name into an env-var key. 'youtube' -> YOUTUBE_API_KEY."""
    key = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    if not key:
        return ""
    if not key.endswith(("_KEY", "_TOKEN", "_SECRET")):
        key += "_API_KEY"
    return key


def env_block(names: list[str]) -> str:
    """Compose `.env.example` lines (placeholders only) for named API keys."""
    keys = [k for k in (env_key(n) for n in names) if k]
    if not keys:
        return ""
    lines = ["", "# --- Project API keys (names only; real values go in .env) ---"]
    lines += [f"{k}=" for k in dict.fromkeys(keys)]  # dedupe, preserve order
    return "\n".join(lines) + "\n"


def verify_commands(template: str) -> list[list[str]]:
    return VERIFY.get(template, [])


def gh_create_cmd(name: str, dest: Path, private: bool = True) -> list[str]:
    return [
        "gh", "repo", "create", name,
        "--private" if private else "--public",
        "--source", str(dest), "--push",
    ]


def moc_line(name: str, blurb: str) -> str:
    return f"- [[{name}]] — {blurb}"


def append_to_moc(name: str, blurb: str, moc: Path | None = None) -> bool:
    """Idempotently register a project in the projects MOC. Returns True if added.

    `moc=None` resolves PROJECTS_MOC at call time. A default argument would bind
    the module constant at import, which is the trap that made `load_cards` in
    project_doctor silently audit the real vault from a test pointed at a temp one.
    """
    moc = moc or PROJECTS_MOC
    header = (
        "---\ntype: moc\nstatus: active\ntags: [moc, projects]\n---\n"
        "# Projects\n\nEvery project scaffolded via `/ecosystem-brain:init`. "
        "Each card also links back here.\n\n"
    )
    text = moc.read_text(encoding="utf-8") if moc.exists() else header
    if f"[[{name}]]" in text:
        return False
    if not text.endswith("\n"):
        text += "\n"
    moc.parent.mkdir(parents=True, exist_ok=True)
    moc.write_text(text + moc_line(name, blurb) + "\n", encoding="utf-8", newline="\n")
    return True


def resolve_exe(cmd: list[str]) -> list[str]:
    """argv with argv[0] resolved to a real executable path.

    On Windows `npm` is `npm.CMD`. `subprocess.run` without a shell will not find
    it by bare name and raises FileNotFoundError — so the typescript template's
    baseline crashed the whole `init --apply` with a traceback instead of
    reporting a failed check. `shutil.which` does find it, so resolve up front.

    Returns cmd unchanged when the tool is absent, letting the caller's own
    error path report a missing tool rather than raising here.
    """
    exe = shutil.which(cmd[0])
    return [exe, *cmd[1:]] if exe else cmd


def verify_baseline(dest: Path, template: str) -> bool:
    """Run the template's build + test commands in `dest`. The verification loop
    the ecosystem preaches: prove the scaffold is green before handing it over.
    """
    cmds = verify_commands(template)
    if not cmds:
        print("  [skip] no baseline check for this template")
        return True
    print("  verifying green baseline ...")
    for cmd in cmds:
        label = " ".join(cmd)
        try:
            r = subprocess.run(  # noqa: PLW1510 — returncode is inspected below
                resolve_exe(cmd), cwd=str(dest), capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
        except OSError as e:
            # A missing or unlaunchable tool is a red baseline, not a crash.
            print(f"  [FAIL] {label}\n      cannot run: {e}")
            return False
        if r.returncode != 0:
            tail = "\n      ".join((r.stdout + r.stderr).strip().splitlines()[-8:])
            print(f"  [FAIL] {label}\n      {tail}")
            return False
        print(f"  [ok]   {label}")
    return True


def gh_publish(name: str, dest: Path, private: bool = True) -> bool:
    if not shutil.which("gh"):
        print("  [skip] github — gh CLI not found")
        return False
    r = run(gh_create_cmd(name, dest, private))
    if r.returncode != 0:
        print(f"  [error] github: {(r.stderr or r.stdout).strip()[:120]}")
        return False
    print(f"  [ok] pushed to GitHub ({'private' if private else 'public'})")
    return True


def print_summary(
    name: str, cfg: dict, resolved: list[dict], dropped: list[str],
    api_keys: list[str] | None = None,
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
    if api_keys:
        print(f"  env keys : {', '.join(env_key(k) for k in api_keys)}")
    print(f"  dest     : {DEST_ROOT / name}")
    print("  on apply : scaffold + agents + linked memory card + green-baseline check")
    print("\n--- composed AGENTS.md preview ---")
    print(compose_agents_md(name, cfg))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    # check=False: every caller reads .returncode and reports it itself.
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)


def apply(
    name: str,
    cfg: dict,
    resolved: list[dict],
    *,
    build: str,
    api_keys: list[str],
    do_verify: bool,
    do_github: bool,
    skip_agents: bool = False,
) -> int:
    dest = DEST_ROOT / name
    print(f"scaffolding {cfg['template']} -> {dest} ...")
    r = run(
        ["uv", "run", "python", str(SCAFFOLD), "--type", cfg["template"], "--name", name,
         "--templates-root", str(REPO_ROOT / "templates"), "--dest-root", str(DEST_ROOT), "--git"]
    )
    if r.returncode != 0:
        print(f"[error] scaffold failed: {r.stderr.strip() or r.stdout.strip()}")
        return 1
    print("  [ok] scaffolded")

    (dest / "AGENTS.md").write_text(
        compose_agents_md(name, cfg), encoding="utf-8", newline="\n"
    )
    print("  [ok] wrote tailored AGENTS.md")

    # Name the project's API keys in .env.example (placeholders only, never values).
    if api_keys:
        envf = dest / ".env.example"
        prior = envf.read_text(encoding="utf-8") if envf.exists() else ""
        envf.write_text(prior + env_block(api_keys), encoding="utf-8", newline="\n")
        print(f"  [ok] named {len(api_keys)} API key(s) in .env.example")

    installed = 0
    if skip_agents:
        print(f"  [skip] {len(resolved)} agent(s) — --skip-agents")
        resolved = []
    for a in resolved:
        if a["source"] == "local":
            print(f"  [ok]      {a['name']} (local, already available)")
            installed += 1
            continue
        ir = run(["uv", "run", "python", str(INSTALLER), "--repo", a["repo"], "--path", a["path"]])
        if ir.returncode == 0:
            installed += 1
            print(f"  [ok]      {a['name']} (installed + scanned)")
        elif ir.returncode == 2:
            print(f"  [BLOCKED] {a['name']} (security scan)")
        else:
            print(f"  [error]   {a['name']}: {ir.stderr.strip()[:60]}")

    # Memory card (linked into the graph) + register in the projects MOC.
    card = VAULT / "projects" / f"{name}.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(memory_card(name, cfg, resolved), encoding="utf-8", newline="\n")
    if append_to_moc(name, f"{build} · {card_stack(cfg)}"):
        print("  [ok] registered in projects-moc")
    run(["uv", "run", "python", str(INDEXER), "--vault", str(VAULT),
         "--out", str(VAULT / "index.json")])
    print("  [ok] memory card + index refreshed")

    # Verification loop: prove the scaffold is green before handing it over.
    baseline_ok = True
    if do_verify:
        baseline_ok = verify_baseline(dest, cfg["template"])

    # Publish only a verified-green scaffold — never push broken code.
    if do_github:
        if baseline_ok:
            gh_publish(name, dest)
        else:
            print("  [skip] github push — baseline is red; not pushing broken code")

    print(f"\ndone. {installed}/{len(resolved)} agents ready. cd {dest}")
    if not baseline_ok:
        print("[!] green baseline FAILED — fix the scaffold before building on it.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--build", required=True,
                    choices=["web", "api", "cli", "library", "data-pipeline", "mcp-server"])
    ap.add_argument("--rigor", required=True, choices=["prototype", "product", "production"])
    ap.add_argument("--touches", default="none", help="comma list: api-keys,pii,money,none")
    ap.add_argument("--stack", choices=["react", "vue", "svelte", "decide"])
    ap.add_argument("--name", required=True)
    ap.add_argument("--api-keys", default="",
                    help="comma list of API names to seed into .env.example (e.g. youtube,tiktok)")
    ap.add_argument("--github", action="store_true",
                    help="create a private GitHub repo and push (requires gh; only if baseline passes)")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the green-baseline build+test check after scaffolding")
    ap.add_argument("--skip-agents", action="store_true",
                    help="scaffold without installing agents — leaves registry/installed.json "
                         "and ~/.claude untouched, so --apply can be exercised end to end")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    profiles = load(PROFILES)
    touches = [t.strip() for t in args.touches.split(",") if t.strip()]
    api_keys = [k.strip() for k in args.api_keys.split(",") if k.strip()]
    cfg = resolve(profiles, args.build, args.rigor, touches, args.stack)
    resolved, dropped = classify_agents(cfg["agents"], profiles)

    if args.plan:
        print_summary(args.name, cfg, resolved, dropped, api_keys=api_keys)
        return 0
    return apply(
        args.name, cfg, resolved,
        build=args.build, api_keys=api_keys,
        do_verify=not args.no_verify, do_github=args.github,
        skip_agents=args.skip_agents,
    )


if __name__ == "__main__":
    raise SystemExit(main())
