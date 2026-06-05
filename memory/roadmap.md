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
- **CI**: `.github/workflows/ci.yml` runs `pytest -q tests` (43 tests) +
  `scripts/selfcheck.py` (JSON, agent scan, init-engine, memory index, pytest)
  + gitleaks. Green on GitHub.
- **Tests**: `tests/` covers `scan_agent` (security gate), `init_project`
  (resolve/classify/compose), `bootstrap` (path rewrite + verify). selfcheck
  runs them via nested `uv run --with pytest`.
- **Hooks** (global settings.json): gitleaks gate, destructive guard (root/home
  only — fixed false positive), ruff-on-write, SessionStart suggester, SessionEnd log.
- **Portability**: `bootstrap.py` rewrites hardcoded paths to the clone location;
  works on any PC / any path. `ECOSYSTEM_CLAUDE_DIR` overrides for testing.
- **Memory**: Obsidian vault, Ollama semantic search (nomic-embed-text, GPU).
- **Scheduled tasks**: Ollama-at-logon, weekly catalog refresh.
- **Templates**: python-project + typescript-project, each with AGENTS.md
  (cross-tool) + CLAUDE.md (imports AGENTS.md) + per-language CI. _common = .vscode.

## Candidate next steps
- [x] **Official Claude best practices** (2026-06-05) — aligned CLAUDE.md,
  template AGENTS.md, and the 4 first-party agents with Anthropic's published
  guidance: added Verification discipline, nuanced plan-mode, focused/isolated/
  least-privilege subagent framing, explicit `model:` grants. Grounding +
  source links in [[decisions/claude-best-practices]].
- [ ] Author original first-party agents (not just VoltAgent installs) tuned to
  this stack, scanned and tracked.
- [ ] `update --all` convenience + a `quarantine/` dir for BLOCKED upstream agents.
- [ ] Linux/Mac path handling in bootstrap (currently Windows/Git-Bash tuned).
- [x] **Tests for the python scripts** (2026-06-05) — `tests/` with 43 pytest
  tests across scan_agent / init_project / bootstrap; wired into selfcheck
  (`check_tests`) + a dedicated CI step. Covers the security gate, init engine,
  and the portability path-rewrite.

## Key decisions (see decisions/)
- [[decisions/hook-format]] · [[decisions/windows-python-invocation]] ·
  [[decisions/windows-path-translation]] · [[decisions/ollama-accented-path]] ·
  [[decisions/powershell-utf8-bom]] · [[decisions/claude-best-practices]]
