---
type: moc
status: active
updated: 2026-06-05
tags: [moc, roadmap, state]
---
# Ecosystem-Brain — state & roadmap

Read this first in a fresh session (after CLAUDE.md). Run
`/ecosystem-brain:context-sync` to pull the decisions below.

## Current state (v4.0.0)
- **13 commands** (global): init, scaffold, search, install, catalog, update,
  agents, health-check, security-audit, write-tests, fix-bug, context-sync, memory-gc
- **Project init**: `/ecosystem-brain:init` — sharp 3-4 question interview →
  tailored AGENTS.md + auto-selected, security-scanned agents. Engine =
  `registry/project-profiles.json` + `scripts/init_project.py` (--plan/--apply).
- **6 build types**: web, api, cli, library, data-pipeline, mcp-server.
- **Agent supply chain**: search (GitHub by stars) → install (scanned by
  `scan_agent.py`, 16 rules) → SessionStart suggests installed+catalog →
  update (re-scans upstream, blocks HIGH-risk). Catalog = 154 agents, cached.
- **CI**: `.github/workflows/ci.yml` runs `scripts/selfcheck.py` (JSON, agent
  scan, init-engine, memory index) + gitleaks. Green on GitHub.
- **Hooks** (global settings.json): gitleaks gate, destructive guard (root/home
  only — fixed false positive), ruff-on-write, SessionStart suggester, SessionEnd log.
- **Portability**: `bootstrap.py` rewrites hardcoded paths to the clone location;
  works on any PC / any path. `ECOSYSTEM_CLAUDE_DIR` overrides for testing.
- **Memory**: Obsidian vault, Ollama semantic search (nomic-embed-text, GPU).
- **Scheduled tasks**: Ollama-at-logon, weekly catalog refresh.
- **Templates**: python-project + typescript-project, each with AGENTS.md
  (cross-tool) + CLAUDE.md (imports AGENTS.md) + per-language CI. _common = .vscode.

## Candidate next steps
- [ ] **Official Claude best practices** — distill Anthropic's Claude Code +
  subagent guidance (anthropic.com/engineering/claude-code-best-practices, the
  docs, and the subagent design guide) into: the ecosystem CLAUDE.md, the
  template AGENTS.md files, and the agent definitions. Make the conventions
  match official advice (concise CLAUDE.md, context-isolated subagents, explicit
  tool grants, plan-mode discipline).
- [ ] Author original first-party agents (not just VoltAgent installs) tuned to
  this stack, scanned and tracked.
- [ ] `update --all` convenience + a `quarantine/` dir for BLOCKED upstream agents.
- [ ] Linux/Mac path handling in bootstrap (currently Windows/Git-Bash tuned).
- [ ] Tests for the python scripts (pytest) so selfcheck can run them in CI.

## Key decisions (see decisions/)
- [[decisions/hook-format]] · [[decisions/windows-python-invocation]] ·
  [[decisions/windows-path-translation]] · [[decisions/ollama-accented-path]] ·
  [[decisions/powershell-utf8-bom]]
