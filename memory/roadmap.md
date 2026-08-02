---
type: moc
status: active
updated: 2026-08-02
tags: [moc, roadmap, state]
---
# Ecosystem-Brain — state & roadmap

Read this first in a fresh session (after CLAUDE.md). Run
`/ecosystem-brain:context-sync` to pull the decisions below.

## Current state (v4.3.16)
- **17 commands** (global): init, scaffold, search, install, catalog, update,
  agents, new-agent, health-check, doctor, **project-doctor**, **agent-usage**,
  security-audit, write-tests, fix-bug, context-sync, memory-gc
- **Project init**: `/ecosystem-brain:init` — sharp 3-4 question interview →
  tailored AGENTS.md + scanned/pinned agents + named API keys in .env.example +
  a **verified green baseline** (build+test must pass) + memory card linked into
  `projects-moc` + optional `--github` push (only if baseline passes). Engine =
  `registry/project-profiles.json` + `scripts/init_project.py` (--plan/--apply).
- **6 build types**: web, api, cli, library, data-pipeline, mcp-server.
- **Agent supply chain**: search (GitHub by stars) → install (scanned by
  `scan_agent.py`; **pinned to commit SHA**) → SessionStart suggests
  installed+catalog → update (re-resolves tip via `gh`, shows oldsha→newsha +
  compare URL, re-scans, quarantines HIGH, advances pin) -> **rollback**
  (`--rollback <name>` re-fetches at the previous SHA, re-scans, swaps pins;
  itself undoable). Shared helpers in `github_util.py`. Catalog = 154 agents, cached. See [[decisions/agent-pinning]].
- **CI**: `.github/workflows/ci.yml` runs ruff lint + `pytest -q tests` (549
  tests, ~6s) + `scripts/selfcheck.py` + `verify_templates.py` (scaffolds each
  blueprint for real and runs its baseline) + gitleaks. **Green on the ubuntu
  runner** since 2026-08-01 (it had been red on every push for weeks on an
  unpinned ruff — 57 findings no commit introduced). Toolchain pinned in
  `requirements-dev.txt`, rule set in `ruff.toml`, Actions pinned to commit
  SHAs with Dependabot — see [[decisions/toolchain-pinning]].
- **Gates**: `selfcheck.py` = 8 checks (JSON, agent scan, init-engine, memory
  index, pytest, **hardcoded-path check**, **ruff**, agent frontmatter). Lint
  runs the *same* invocation and the same pinned binary as CI, so local-green
  and CI-green are the same claim; tests assert the two configs can't drift.
- **Tests**: `tests/` (549, **90%** coverage, every script >=81%) covers scan_agent, init_project,
  bootstrap, github_util (fetch allowlist), update-agents (pinning), doctor
  (drift + hook wiring + skills), catalog, install-agent (naming, target
  paths, traversal, the security gate end-to-end), scaffold (rmtree guard),
  the destructive guard, suggest-agents, search_agents, maintenance, and the
  {{ECOSYSTEM_ROOT}} substitution.
- **Scanner**: `scan_agent.py` (20 rules) — prompt-injection, secret/SSH reads,
  curl|bash, PowerShell cradles (iwr|iex, WebClient, -enc), base64-exec,
  eval/exec, rm -rf, TLS-off (incl. flag-first `curl -k`), exfil, hidden chars.
- **Dogfood**: the repo's own `CLAUDE.md` imports `@AGENTS.md` — same cross-tool
  pattern it ships in templates.
- **Doctor**: `/ecosystem-brain:doctor` (`doctor.py`) = live-hooks + repo↔~/.claude
  drift (commands + agents + **skills**) + prereqs.
- **Project doctor**: `/ecosystem-brain:project-doctor` (`project_doctor.py`) —
  the feedback loop on what the ecosystem *built*: does each registered card's
  path still resolve, commit age, dirty tree, AGENTS.md, .env vs .env.example,
  CI conclusion (advisory). Reports, never repairs: fix the card's
  `- Project: ` line, or set `status: archived`. Non-gating in the heartbeat
  until the current backlog is triaged.
- Both are wired into health-check and the weekly maintenance heartbeat, whose
  status is three-state: `ok` / `warn` (advisory check failed) / `FAIL`.
- **First-party squad** (6): security-auditor, convention-keeper, script-smith,
  test-writer, bug-fixer, memory-curator. The SessionStart suggester surfaces them
  every session *with trigger moments* so they actually get delegated to.
  **Model-routed by task shape** (3 tiers since v4.3.3): checklist agents
  (convention-keeper, memory-curator) on haiku; spec-driven code-gen
  (test-writer, script-smith) on sonnet; judgment agents (security-auditor,
  bug-fixer) inherit the session model. See [[decisions/model-routing]].
  selfcheck lints local agent frontmatter (name/description/tools/model).
- **Recruiter**: `/ecosystem-brain:new-agent` (`new_agent.py`) scaffolds a new
  agent to standard (frontmatter, least-privilege tools, model, "use proactively"
  description, numbered workflow), self-scans, and registers via install-agent.
- **Hooks** (global settings.json): gitleaks gate, destructive guard
  (`guard_destructive.py` — tokenizes and normalizes flags, matches targets
  exactly rather than by prefix, 43 tests both directions), ruff-on-write,
  SessionStart suggester, SessionEnd log.
- **Portability**: committed files refer to the repo as `{{ECOSYSTEM_ROOT}}`;
  `bootstrap.py` expands it to the clone's location, so any PC / any path
  works. selfcheck fails on any literal path that creeps back in.
  `ECOSYSTEM_CLAUDE_DIR` overrides for testing.
- **Memory**: Obsidian vault (project cards linked into `projects-moc` hub +
  stack decisions — no orphans). Semantic search really is on Ollama
  `nomic-embed-text` (768d) since 2026-08-02 — before that the index held
  24/28 notes on the offline hash fallback, because a 500 on the vault's
  largest note aborted every build and nothing rebuilt it. Input is capped at
  6000 chars, per-note failures are survivable, and `memory-search.py status`
  gates coverage + embedder in the heartbeat.
- **Scheduled tasks**: Ollama-at-logon, weekly catalog refresh, weekly
  maintenance heartbeat (`maintenance.py`: doctor + selfcheck + project-doctor +
  task-doctor + memory index refresh/status + agent-usage + update --check →
  `memory/maintenance/<date>.md`).
  Registrar `scripts/register-scheduled-tasks.ps1` (idempotent, path-derived)
  disables both battery guards — PowerShell defaults them ON, which killed
  every weekly run from 2026-07-15 to 2026-08-02. The `.bat` wrappers `exit /b`
  the child's real code and tee to `memory/maintenance/*.log`.
- **Task doctor**: `task_doctor.py` judges each scheduled task on its last
  RESULT and that result's age, never on `State` — a task sits at Ready
  forever while every run dies. Gating in the heartbeat; Windows-only.
- **Templates**: python-project + typescript-project, each with AGENTS.md
  (cross-tool) + CLAUDE.md + GEMINI.md (both `@AGENTS.md` importers) + per-language
  CI. `_common` = .vscode + GEMINI.md.
- **Multi-LLM**: AGENTS.md is the single source; Codex/Cursor/Copilot/Windsurf
  read it natively, Gemini via the GEMINI.md stub, Claude via CLAUDE.md. DeepSeek
  (a model, not a reader) runs through an AGENTS.md-aware host tool via its
  OpenAI-compatible endpoint. See `docs/MULTI-LLM.md`.
- **Token discipline**: `docs/TOKENS.md` + a Context-discipline rule in AGENTS.md
  and the template/`init` AGENTS.md — lean instruction files + `.mcp.json`,
  subagents for high-volume reads, `/clear` between tasks. (SessionStart suggester
  output is already lean at ~700 chars.)

## Shipped

Release history lives in `CHANGELOG.md` — this note orients a fresh session, so
it keeps the open questions rather than the closed ones.

**2026-07-31 → 08-02, v4.3.5 → v4.3.16.** One audit, one defect found eight
times: information existed and nothing read it back. CI had been red on every
push for weeks; the local gate never ran the linter that was failing; 58
committed paths pointed at a drive that no longer existed; the weekly scheduled
tasks had *never once* completed a run while reporting `Ready`; "semantic"
search ran on a bag-of-words fallback; nothing had ever re-read the project
cards. Tests 114 → 549, coverage 40% → 90%, selfcheck 6 → 8 checks, and every
artefact the ecosystem produces now has a reader.

The rule that came out of it: [[decisions/verification-integrity]].

Earlier milestones (project init engine, agent SHA pinning, model routing,
cross-tool AGENTS.md, the memory vault) are in `CHANGELOG.md` under v4.0–v4.3.4.

## Open questions

- [ ] **Triage the 4 dead project cards** (opened 2026-08-02) — betting-tracker,
  betting-stats-analysis, my-first-tool, viral-videos-sm all point at
  `D:\claude-projects\…`, which does not exist on this machine. Deleted, on
  another machine, or an unmounted drive? Each needs either a corrected
  `- Project: ` line or `status: archived`. Flip project_doctor to gating in
  `maintenance.CHECKS` once done.

- [ ] **Prune the 8 unused third-party agents** (opened 2026-08-02) — evidence
  is local-only, so confirm against the other PC before removing anything.
  Four first-party agents also show zero: that is a delegation habit to change,
  not a cleanup.

- [ ] **profile_machine.py** (proposed 2026-07-15, parked) — per-machine vault
  note (OS, tools, apps, drives/shares, project dirs) generated at bootstrap and
  injected at SessionStart, so any PC is known from the first second.
