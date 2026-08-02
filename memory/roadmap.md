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
- **CI**: `.github/workflows/ci.yml` runs ruff lint + `pytest -q tests` (545
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
- **Tests**: `tests/` (545, **90%** coverage, every script >=81%) covers scan_agent, init_project,
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

## Candidate next steps
- [x] **Gate repair → v4.3.5** (2026-07-31) — CI lint was red on an unpinned
  ruff and the local gate couldn't see it; skills were invisible to `doctor` and
  unloadable when installed; `--name` was a path; scan reports buried MEDIUM
  findings. All fixed with tests (114 → 157). See [[decisions/toolchain-pinning]].
- [x] **P1 hardening → v4.3.6** (2026-08-01) — `fetch_url` https+allowlist+cap
  (it was upstream of every other control); destructive guard rewritten in
  Python after it proved bypassable *and* prone to false positives; `scaffold
  --force` rmtree guarded; Actions pinned to SHAs + Dependabot. 174 → 246 tests.
- [x] **Coverage + de-hardcoded paths → v4.3.7** (2026-08-01) — the three 0%
  scripts covered (`suggest-agents` 94%, `search_agents` 87%, `maintenance` 95%),
  `install-agent` 32→91%; overall 47→64%. `{{ECOSYSTEM_ROOT}}` replaces the dead
  authoring path (58 refs / 16 files), enforced by selfcheck check 6.
- [x] **Remaining coverage → v4.3.8** (2026-08-01) — `selfcheck` 34→85%,
  `bootstrap` 44→99%, `doctor` 52→98%, `catalog` 30→98%, `new_agent` 49→99%,
  `update-agents` 48→81%. Overall 64→**86%**, 395 tests. Each gate is now tested
  for going *red* when its subject breaks, not merely for passing on a healthy
  repo. No production code changed.
- [x] **Linux path bug + doc drift -> v4.3.10** (2026-08-01) — the SessionStart
  suggester rewrote real posix paths (`/d/projects/app` -> `D:/projects/app`)
  off Windows, so it detected no project type and silently suggested nothing;
  `bootstrap` had the guard since 2026-06-06, the second copy never got it.
  Test forces the non-Windows branch, since on Windows both copies agreed.
  Docs: README command table (12->15), `update` description, six first-party
  agents, new Verification section, dead `.mcp.json`/`GITHUB_TOKEN` claim;
  INSTALL heartbeat contents; TOKENS.md MCP guidance.
- [x] **`init_project.apply()` covered -> v4.3.9** (2026-08-01) — 54->83%, all
  subprocesses stubbed. Pins the ordering that keeps a red baseline off GitHub,
  that `.env.example` carries key names and never values, and that a blocked
  agent does not fail the whole init. Overall 86->**90%**, 418 tests.
- [x] **Live-install audit → v4.3.2** (2026-07-15) — fixed the hardcoded /d/
  SessionStart hint, added doctor's hook-wiring drift check, unpinned-install
  warning, registry repair (stale global_path, backfilled data-engineer pin).
- [x] **Model routing rev. for Sonnet 5 → v4.3.3** (2026-07-15) — sonnet tier
  for spec-driven code-gen; aliases-only portability rule made explicit.
- [x] **Heartbeat live** (2026-07-15) — all 3 scheduled tasks registered on this
  machine; first maintenance run verified end-to-end (report all-green).
- [x] **.mcp.json emptied** (2026-07-15) — filesystem server pointed at a dead
  path; git/github duplicated native tools.
- [ ] **Triage the 4 dead project cards** (opened 2026-08-02) — betting-tracker,
  betting-stats-analysis, my-first-tool, viral-videos-sm all point at
  `D:\claude-projects\…`, which does not exist on this machine. Deleted, on
  another machine, or an unmounted drive? Each needs either a corrected
  `- Project: ` line or `status: archived`. Flip project_doctor to gating in
  `maintenance.CHECKS` once done.
- [x] **Project feedback loop → v4.3.12** (2026-08-02) — nothing had ever read
  `memory/projects/*.md` back; four cards had rotted unnoticed. Also fixed the
  heartbeat labelling a failed advisory check as `ok`.
- [x] **Capability gaps 2/3/4 -> v4.3.13** (2026-08-02) — agent rollback
  (`previous_commit` + `--rollback`, re-scanned on the way back); templates
  verified for real in CI (which surfaced a pre-existing Windows crash: bare
  `npm` raises FileNotFoundError, so init on a typescript project died at the
  baseline step); agent-usage from session transcripts — 12 of 14 agents have
  never been invoked here.
- [ ] **Prune the 8 unused third-party agents** (opened 2026-08-02) — evidence
  is local-only, so confirm against the other PC before removing anything.
  Four first-party agents also show zero: that is a delegation habit to change,
  not a cleanup.
- [x] **The scheduler that never ran -> v4.3.14** (2026-08-02) — the weekly
  heartbeat and catalog refresh had failed EVERY scheduled run since being
  registered, at `State: Ready` the whole time; catalog 40 days stale, every
  maintenance report on disk written by hand. Two causes: PowerShell's battery
  guards default ON, and the `.bat` wrappers had no `exit /b` so the console
  teardown was reported instead of the real code. `task_doctor.py` now gates on
  last-result + staleness so this cannot be silently true again.
- [x] **Semantic search was never semantic -> v4.3.15** (2026-08-02) — the
  index held 24/28 notes on the offline hash fallback while the README
  advertised Ollama. No truncation (nomic-embed-text 500s past ~2k tokens, and
  roadmap.md is 14k), one bad note aborted the build, and nothing rebuilt it.
  Now 28/28 at 768d, with a gating status check.
- [x] **init --apply made testable -> v4.3.16** (2026-08-02) — it wrote a card,
  a MOC line and a registry mutation into THIS repo regardless of
  ECOSYSTEM_DEST_ROOT, so running the flagship command once dirtied the repo and
  it was never in CI. ECOSYSTEM_VAULT + --skip-agents fix that; CI now runs it
  end to end and asserts `git diff --exit-code`.
- [ ] **profile_machine.py** (proposed 2026-07-15, parked) — per-machine vault
  note (OS, tools, apps, drives/shares, project dirs) generated at bootstrap and
  injected at SessionStart, so any PC is known from the first second.
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
  [[decisions/agent-pinning]] · [[decisions/betting-tracker-stack]] ·
  [[decisions/model-routing]] · [[decisions/toolchain-pinning]] ·
  [[decisions/text-file-write-conventions]]
