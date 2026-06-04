# Ecosystem-Brain (Claude Code plugin)

Bundles the claude-unified-ecosystem control tower as one installable unit: delegation subagents, secrets-safe git hooks, project scaffolding, and an Obsidian-style memory with local semantic search.

## Install (actual)

Claude Code loads commands from `~/.claude/commands/` — run this once after cloning:

```bash
mkdir -p ~/.claude/commands/ecosystem-brain
cp /d/Claude_projects/ecosystem-brain/commands/*.md ~/.claude/commands/ecosystem-brain/
```

Then restart Claude Code. Commands are immediately available in every session.

**MCP servers** (filesystem, git, github) are configured in `.mcp.json` — Claude Code picks these up automatically when you open the project folder.

**Hooks** (`hooks/hooks.json`) apply when this folder is the active project.

**GITHUB_TOKEN**: set once as a user environment variable so `.mcp.json` can resolve it:
```bash
# Windows (PowerShell)
[Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_...", "User")
```

## After editing commands

When you change a file in `commands/`, re-sync to the global commands directory:
```bash
cp /d/Claude_projects/ecosystem-brain/commands/*.md ~/.claude/commands/ecosystem-brain/
```
Then restart Claude Code to pick up the changes.

## Commands

| Command | What it does |
|---------|-------------|
| `/ecosystem-brain:scaffold <type> <name>` | Scaffold a new project from a template |
| `/ecosystem-brain:health-check` | Secrets hygiene + tool versions + active projects |
| `/ecosystem-brain:context-sync` | Brief current session on ecosystem conventions |
| `/ecosystem-brain:memory-gc` | Prune stale vault notes |

## What's inside
- **agents/** — `security-auditor`, `test-writer`, `bug-fixer`, `memory-curator` (each with a narrow toolset).
- **commands/** — slash commands (install to `~/.claude/commands/ecosystem-brain/`).
- **skills/** — `memory` (index + semantic search), `secrets` (doctor + identity).
- **hooks/** — gitleaks gate before commit/push, catastrophic-command block, ruff auto-format on write, session logging.
- **settings.json** — denies reads of `.env*`/`.identity.local.env`; asks before destructive git/rm.
- **.mcp.json** — filesystem, git, github MCP servers.
- **templates/** — `python-project` blueprint used by the scaffolder (includes `CLAUDE.md`).

## Prerequisites
- **Required:** `git`, `node`/`npx`, `uv` (installs Python + ruff)
- **Recommended:** `gitleaks` (secret scanning), `ollama` + `nomic-embed-text` (semantic memory)
- Missing tools degrade gracefully — hooks skip, search falls back to offline hash embedder.

## Windows-specific notes
- Use `uv run python` instead of bare `python` (Windows Store stub intercepts).
- `OLLAMA_MODELS` must point to an ASCII-safe path if your username has accented characters (e.g. `D:\ollama-models\models`).
- `GITHUB_TOKEN` set as a user environment variable is picked up by `.mcp.json`.
