# Ecosystem-Brain (Claude Code plugin)

Bundles the claude-unified-ecosystem control tower as one installable unit: delegation subagents, secrets-safe git hooks, project scaffolding, and an Obsidian-style memory with local semantic search.

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
| `/ecosystem-brain:scaffold <type> <name>` | Scaffold a new project (python or typescript) |
| `/ecosystem-brain:search <topic> [--files]` | Search GitHub live for agents, by stars |
| `/ecosystem-brain:install` | Install an agent from GitHub (auto security-scanned) |
| `/ecosystem-brain:catalog [build\|categories\|install]` | Browse / batch-install from cached catalog |
| `/ecosystem-brain:update` | Update installed agents (hash-based) |
| `/ecosystem-brain:agents` | List installed agents/skills/commands |
| `/ecosystem-brain:health-check` | Secrets hygiene + tool versions + active projects |
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
- **agents/** — `security-auditor`, `test-writer`, `bug-fixer`, `memory-curator` + installed third-party agents.
- **commands/** — slash commands (synced to `~/.claude/commands/ecosystem-brain/` by bootstrap).
- **scripts/** — `bootstrap`, `scaffold`, `install-agent`, `update-agents`, `search_agents`, `catalog`, `scan_agent`.
- **skills/** — `memory` (index + semantic search), `secrets` (doctor + identity).
- **hooks/** — gitleaks gate, catastrophic-command block, ruff auto-format, SessionStart agent-suggester, session logging.
- **registry/** — `registry.json` (curated sources), `installed.json`, `catalog.json` (cached agent catalog).
- **templates/** — `python-project` + `typescript-project` blueprints (each with `AGENTS.md` + `CLAUDE.md`).
- **docs/** — [OBSIDIAN.md](docs/OBSIDIAN.md) (vault usage), [MULTI-LLM.md](docs/MULTI-LLM.md) (Gemini/Codex/Cursor).

## Prerequisites
- **Required:** `git`, `node`/`npx`, `uv` (installs Python + ruff)
- **Recommended:** `gitleaks` (secret scanning), `gh` (GitHub CLI, for search/install), `ollama` + `nomic-embed-text` (semantic memory)
- Missing tools degrade gracefully — hooks skip, search falls back to offline hash embedder.

## Windows-specific notes
- Use `uv run python` instead of bare `python` (Windows Store stub intercepts).
- `OLLAMA_MODELS` must point to an ASCII-safe path if your username has accented characters (e.g. `D:\ollama-models\models`).
- `GITHUB_TOKEN` set as a user environment variable is picked up by `.mcp.json`.
