# Ecosystem-Brain

The control tower for your Claude Code setup: a guided project-init interview,
GitHub agent discovery/install/update with security scanning, secrets-safe git
hooks, project scaffolding, and an Obsidian-style memory with local semantic
search. Installed into `~/.claude/` from a single clone via `bootstrap.py`.

## Install

One command after cloning — see **[INSTALL.md](INSTALL.md)** for the full guide
(prerequisites, secrets, Ollama, other PCs):

```bash
git clone https://github.com/xray140/ecosystem-brain.git
cd ecosystem-brain
uv run python scripts/bootstrap.py        # wires up ~/.claude from this clone
```
Then restart Claude Code. The bootstrap derives all paths from the clone
location, so it works on any machine / any path.

## Commands

| Command | What it does |
|---------|-------------|
| `/ecosystem-brain:init [name]` | **Guided project creation** — 3-4 sharp questions → tailored AGENTS.md + auto-selected, scanned agents |
| `/ecosystem-brain:scaffold <type> <name>` | Raw scaffold (no interview, no agents) — the manual path |
| `/ecosystem-brain:search <topic> [--files]` | Search GitHub live for agents, by stars |
| `/ecosystem-brain:install` | Install an agent from GitHub (auto security-scanned) |
| `/ecosystem-brain:catalog [build\|categories\|install]` | Browse / batch-install from cached catalog |
| `/ecosystem-brain:update` | Update installed agents — re-resolves the tip, re-scans, advances the commit pin |
| `/ecosystem-brain:agents` | List installed agents/skills/commands |
| `/ecosystem-brain:new-agent` | Recruit a first-party agent, scaffolded to standard and self-scanned |
| `/ecosystem-brain:doctor` | Drift check — are the live hooks/commands/agents/skills in sync with this clone? |
| `/ecosystem-brain:project-doctor` | Do the registered projects still exist, and are they healthy? |
| `/ecosystem-brain:agent-usage` | Which installed agents ever get invoked — and which never have |
| `/ecosystem-brain:health-check` | Everything above at once: secrets, wiring, projects, tasks, memory, agents |
| `/ecosystem-brain:security-audit` | Run the security-auditor on staged changes |
| `/ecosystem-brain:write-tests` / `:fix-bug` | Invoke test-writer / bug-fixer agents |
| `/ecosystem-brain:context-sync` | Brief current session on ecosystem conventions |
| `/ecosystem-brain:memory-gc` | Prune stale vault notes via memory-curator |

## Agent install / discovery / update loop
```
/ecosystem-brain:search "react testing" --files   # discover (GitHub, by stars)
/ecosystem-brain:install --repo X --path Y         # install (auto security scan)
  ↓ next session in a project
SessionStart hook suggests relevant installed + uninstalled agents
/ecosystem-brain:update --check                    # keep current
```

## What's inside
- **agents/** — six first-party: `security-auditor`, `test-writer`, `bug-fixer`,
  `memory-curator`, `script-smith`, `convention-keeper` — plus installed third-party agents.
- **commands/** — slash commands (synced to `~/.claude/commands/ecosystem-brain/` by bootstrap).
  They refer to this repo as `{{ECOSYSTEM_ROOT}}`; bootstrap expands it to the clone's path.
- **scripts/** — `bootstrap`, `selfcheck`, `init_project`, `scaffold`,
  `install-agent`, `update-agents`, `search_agents`, `catalog`, `scan_agent`,
  `new_agent`, `maintenance`, `verify_templates`, plus the shared helpers
  `layout` (where an installed item lives) and `github_util` (fetch + SHA pinning).
  Four doctors, split by what they judge: `doctor` (the install), `project_doctor`
  (the projects it built), `task_doctor` (whether the scheduled tasks actually
  complete), `agent_usage` (which agents are ever invoked).
- **skills/** — `memory` (index + semantic search), `secrets` (doctor + identity).
- **hooks/** — gitleaks gate, catastrophic-command block, ruff auto-format, SessionStart agent-suggester, session logging.
- **tests/** — the suite `selfcheck` and CI both run; see *Verification* below.
- **registry/** — `registry.json` (curated sources), `installed.json` (what is installed and the commit each item is pinned at — tracked, identical on every machine), `installed.local.json` (where it landed on *this* machine — gitignored), `catalog.json` (cached agent catalog).
- **templates/** — `python-project` + `typescript-project` blueprints (each with `AGENTS.md` + `CLAUDE.md` + `GEMINI.md`).
- **docs/** — [OBSIDIAN.md](docs/OBSIDIAN.md) (vault usage), [MULTI-LLM.md](docs/MULTI-LLM.md) (Gemini/Codex/Cursor/Copilot/DeepSeek), [TOKENS.md](docs/TOKENS.md) (context discipline).

## Verification

The repo holds itself to the rule it ships: every change is paired with a check
that returns pass/fail.

```bash
uv run --no-project python scripts/selfcheck.py   # 8 checks, the same ones CI runs
uv run --no-project python scripts/doctor.py      # is ~/.claude actually in sync with this clone?
```

`selfcheck` covers JSON validity, the agent security scan, the init engine, the
memory index, pytest, hardcoded paths, ruff, and agent frontmatter. Its lint and
test steps use the *same invocation and the same pinned binaries* as
`.github/workflows/ci.yml`, so a green run locally and a green run in CI are the
same claim — tests assert the two configs cannot drift apart. The toolchain is
pinned in `requirements-dev.txt` and the rule set in `ruff.toml`; see
[toolchain-pinning](memory/decisions/toolchain-pinning.md) for why both.

## Prerequisites
- **Required:** `git`, `node`/`npx`, `uv` (installs Python + ruff)
- **Recommended:** `gitleaks` (secret scanning), `gh` (GitHub CLI, for search/install), `ollama` + `nomic-embed-text` (semantic memory)
- Missing tools degrade gracefully — hooks skip, search falls back to offline hash embedder.

## Windows-specific notes
- Use `uv run python` instead of bare `python` (Windows Store stub intercepts).
- `OLLAMA_MODELS` must point to an ASCII-safe path if your username has accented characters (e.g. `D:\ollama-models\models`).
- GitHub access comes from `gh auth login` (the CLI's own keyring), which is what
  `install`/`update`/`search` use to resolve commit SHAs. `.mcp.json` ships empty
  — the servers it once declared were dead weight (v4.3.3).
