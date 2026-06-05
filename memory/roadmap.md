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
- **14 commands** (global): init, scaffold, search, install, catalog, update,
  agents, health-check, doctor, security-audit, write-tests, fix-bug,
  context-sync, memory-gc
- **Project init**: `/ecosystem-brain:init` — sharp 3-4 question interview →
  tailored AGENTS.md + auto-selected, security-scanned agents. Engine =
  `registry/project-profiles.json` + `scripts/init_project.py` (--plan/--apply).
- **6 build types**: web, api, cli, library, data-pipeline, mcp-server.
- **Agent supply chain**: search (GitHub by stars) → install (scanned by
  `scan_agent.py`; **pinned to commit SHA**) → SessionStart suggests
  installed+catalog → update (re-resolves tip via `gh`, shows oldsha→newsha +
  compare URL, re-scans, quarantines HIGH, advances pin). Shared helpers in
  `github_util.py`. Catalog = 154 agents, cached. See [[decisions/agent-pinning]].
- **CI**: `.github/workflows/ci.yml` runs ruff lint + `pytest -q tests` (74
  tests) + `scripts/selfcheck.py` (JSON, agent scan, init-engine, memory index,
  pytest) + gitleaks. Green on GitHub.
- **Tests**: `tests/` (74) covers scan_agent, init_project, bootstrap,
  github_util, update-agents (pinning), doctor (drift), catalog. selfcheck runs
  them via nested `uv run --with pytest`.
- **Scanner**: `scan_agent.py` (20 rules) — prompt-injection, secret/SSH reads,
  curl|bash, PowerShell cradles (iwr|iex, WebClient, -enc), base64-exec,
  eval/exec, rm -rf, TLS-off (incl. flag-first `curl -k`), exfil, hidden chars.
- **Dogfood**: the repo's own `CLAUDE.md` imports `@AGENTS.md` — same cross-tool
  pattern it ships in templates.
- **Doctor**: `/ecosystem-brain:doctor` (`doctor.py`) = live-hooks + repo↔~/.claude
  drift + prereqs. Wired into health-check and the weekly maintenance heartbeat.
- **Hooks** (global settings.json): gitleaks gate, destructive guard (root/home
  only — fixed false positive), ruff-on-write, SessionStart suggester, SessionEnd log.
- **Portability**: `bootstrap.py` rewrites hardcoded paths to the clone location;
  works on any PC / any path. `ECOSYSTEM_CLAUDE_DIR` overrides for testing.
- **Memory**: Obsidian vault, Ollama semantic search (nomic-embed-text, GPU).
- **Scheduled tasks**: Ollama-at-logon, weekly catalog refresh, weekly
  maintenance heartbeat (`maintenance.py`: doctor + selfcheck + update --check →
  `memory/maintenance/<date>.md`). One-shot registrar:
  `scripts/register-scheduled-tasks.ps1` (idempotent, path-derived).
- **Templates**: python-project + typescript-project, each with AGENTS.md
  (cross-tool) + CLAUDE.md (imports AGENTS.md) + per-language CI. _common = .vscode.

## Candidate next steps
- [x] **Official Claude best practices** (2026-06-05) — aligned CLAUDE.md,
  template AGENTS.md, and the 4 first-party agents with Anthropic's published
  guidance: added Verification discipline, nuanced plan-mode, focused/isolated/
  least-privilege subagent framing, explicit `model:` grants. Grounding +
  source links in [[decisions/claude-best-practices]].
- [x] **Author original first-party agents** (2026-06-06) — added `script-smith`
  (writes scripts honoring the Windows/uv/path conventions) and `convention-keeper`
  (read-only auditor for CLAUDE.md/AGENTS.md/agents/scripts vs official + ecosystem
  best practices). Both scanned CLEAN and registered local. Now 6 first-party agents.
- [x] **`update --all` + `quarantine/`** (2026-06-06) — explicit --all flag; a
  HIGH-risk install or upstream update is stashed in `quarantine/` for review.
- [x] **Supply-chain hardening** (2026-06-06) — agents pinned to commit SHAs +
  provenance; update shows oldsha→newsha + compare URL. See [[decisions/agent-pinning]].
- [x] **Linux/Mac path handling in bootstrap** (2026-06-06) — drive-letter <->
  Git-Bash-mount translation (`to_bash_path`, `_normalize`) now guarded by a
  `WINDOWS` flag, so `/d/foo` is left as a real posix path off Windows. The
  canonical-path rewrite already worked cross-platform. Platform-aware tests
  cover both branches.
- [x] **Tests for the python scripts** (2026-06-05) — `tests/` with 43 pytest
  tests across scan_agent / init_project / bootstrap; wired into selfcheck
  (`check_tests`) + a dedicated CI step. Covers the security gate, init engine,
  and the portability path-rewrite.

## Key decisions (see decisions/)
- [[decisions/hook-format]] · [[decisions/windows-python-invocation]] ·
  [[decisions/windows-path-translation]] · [[decisions/ollama-accented-path]] ·
  [[decisions/powershell-utf8-bom]] · [[decisions/claude-best-practices]] ·
  [[decisions/agent-pinning]]
