# Ecosystem-Brain (Claude Code plugin)

Bundles the claude-unified-ecosystem control tower as one installable unit: delegation subagents, secrets-safe git hooks, project scaffolding, and an Obsidian-style memory with local semantic search.

## Install

**Local (development):**
```bash
claude --plugin-dir /path/to/ecosystem-brain
```

**Via marketplace (this repo self-references):**
```
/plugin marketplace add <your-git-remote-or-path>
/plugin install ecosystem-brain@ecosystem-brain-marketplace
```
Run `/reload-plugins` after changing hooks, `.mcp.json`, or agents.

## What's inside
- **agents/** — `security-auditor`, `test-writer`, `bug-fixer`, `memory-curator` (each with a narrow toolset).
- **commands/** — `/ecosystem-brain:scaffold`, `:health-check`, `:context-sync`, `:memory-gc`.
- **skills/** — `memory` (index + semantic search), `secrets` (doctor + identity).
- **hooks/** — gitleaks gate before commit/push, catastrophic-command block, ruff auto-format on write, session logging.
- **settings.json** — denies reads of `.env*`/`.identity.local.env`; asks before destructive git/rm.
- **.mcp.json** — filesystem, git, github servers.
- **templates/** — `python-project` blueprint used by the scaffolder.

## Prerequisites
Recommended on PATH: `uv`, `ruff`, `gitleaks`, `git`, `python3`, `node`/`npx`, and `ollama` (with `ollama pull nomic-embed-text`) for semantic memory. Missing tools degrade gracefully (hooks skip, search falls back to offline).

## After install, in an ecosystem repo
Add to `.gitignore`: `.identity.local.env`, `*.local.env`, `memory/.search-index.db`, `memory/index.json`.

## Notes
- The GitHub MCP entry uses `$GITHUB_TOKEN`; swap for the hosted GitHub MCP if you prefer.
- Hooks execute shell commands and require workspace-trust acceptance.
