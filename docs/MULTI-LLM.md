# Using ecosystem-brain projects with other LLMs (Gemini, ChatGPT/Codex, Cursor)

Scaffolded projects are **portable across AI coding tools** because they use the
`AGENTS.md` standard (stewarded by the Linux Foundation, 60k+ projects).

## How it works
Each template ships two instruction files:
- **`AGENTS.md`** — the canonical, tool-neutral project rules. Read natively by
  Gemini CLI, OpenAI Codex, Cursor, GitHub Copilot, Aider, Jules, and others.
- **`CLAUDE.md`** — a one-line `@AGENTS.md` import. Claude Code reads CLAUDE.md,
  which pulls in AGENTS.md. **Single source of truth, no drift.**

Edit `AGENTS.md`. Never duplicate rules into CLAUDE.md.

## Per-tool setup in a scaffolded project

### Claude Code
Works out of the box — `CLAUDE.md` imports `AGENTS.md`.

### Gemini CLI
Reads `GEMINI.md` or `AGENTS.md`. It picks up `AGENTS.md` automatically. To be
explicit, add a `GEMINI.md` containing `@AGENTS.md` (same import trick).
```bash
gemini   # in the project dir — reads AGENTS.md
```

### OpenAI Codex / ChatGPT (codex CLI)
Reads `AGENTS.md` natively. No extra config.
```bash
codex    # in the project dir
```

### Cursor
Reads `AGENTS.md` (and `.cursor/rules`). Open the folder; rules apply.

## What does NOT transfer
- **Agents** (`~/.claude/agents/*.md`) and **slash commands** are Claude
  Code-specific. Gemini/Codex have their own extension formats.
- **Hooks** (gitleaks gate, ruff format) are Claude Code settings.json features.
- **MCP servers** — supported by Claude and some others, but configured per-tool.

The *project instructions* are shared; the *tooling/automation* is per-assistant.

## Bottom line
One project, many assistants — all reading the same `AGENTS.md` rules. The
ecosystem-brain control tower itself (agents, hooks, memory, install/update)
remains Claude Code-native.
