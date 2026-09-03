---
type: moc
status: active
updated: 2026-08-02
tags: [moc, roadmap, state]
---
# Ecosystem-Brain — state & roadmap

Read this first in a fresh session (after CLAUDE.md). Run
`/ecosystem-brain:context-sync` to pull the decisions below.

## Current state (v4.8.1)
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
  itself undoable). Shared helpers in `github_util.py`. The catalog is cached and refreshed
  weekly, with `catalog.seed.json` as the committed floor. See
  [[decisions/agent-pinning]].
- **CI**: `.github/workflows/ci.yml` runs ruff lint + `pytest -q tests` +
  `scripts/selfcheck.py` + `verify_templates.py` (scaffolds each blueprint for
  real and runs its baseline) + gitleaks, on an **ubuntu + windows matrix**
  since v4.7.1 — Windows is the platform this ecosystem actually runs on, and
  three defects had shipped green through a Linux-only job. Green on ubuntu
  since 2026-08-01 (it had been red on every push for weeks on an unpinned
  ruff — 57 findings no commit introduced). **Both** toolchains are pinned:
  ruff/pytest in `requirements-dev.txt`, the rule set in `ruff.toml`, the
  template's npm dependencies to exact versions, node to an exact patch via
  `actions/setup-node`, and every Action to a commit SHA with Dependabot. The
  TypeScript half was added 2026-09-03, after an unpinned npm turned master red
  on two docs-only commits — see [[decisions/toolchain-pinning]].
- **Gates**: `selfcheck.py` = 9 checks (JSON, agent scan, init-engine, memory
  index, pytest, **hardcoded-path check**, **ruff**, agent frontmatter,
  **this note**). Lint runs the *same* invocation and the same pinned binary
  as CI, so local-green and CI-green are the same claim; tests assert the two
  configs can't drift. Check 9 reads the numbers below back against the repo:
  the section had gone four releases out of date, and an orientation note
  nobody verifies is the one artefact that misleads every fresh session.
- **Tests**: `tests/`, held above a coverage floor **91%** by selfcheck — a
  floor rather than a headline number, because the headline moves with every
  commit and would make a gate on it noise. Covers scan_agent, init_project,
  bootstrap, github_util (fetch allowlist), update-agents (pinning), doctor
  (drift + hook wiring + skills), catalog, install-agent (naming, target
  paths, traversal, the security gate end-to-end), scaffold (rmtree guard),
  the destructive guard, suggest-agents, search_agents, maintenance, the
  subprocess-encoding rule, and the {{ECOSYSTEM_ROOT}} substitution.
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
- Both are wired into health-check and the weekly maintenance
  heartbeat = 11 checks, whose status is three-state: `ok` / `warn`
  (advisory check failed) / `FAIL`. It captures each child as UTF-8. For eight
  weeks it captured them in the locale encoding instead: every report on disk
  was mojibake, and every exit code was 0. See [[decisions/encoding-discipline]].
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
  stack decisions — no orphans). Search is **keyword only** since 2026-08-22
  ([[no-ollama]]): one hashed bag-of-words embedder, no server, no network. It
  ran on Ollama `nomic-embed-text` (768d) from 2026-08-02 and matched meaning
  rather than wording; that is the capability the removal cost. Input is capped
  at 6000 chars, per-note failures are survivable, and `memory-search.py status`
  gates coverage + embedder in the heartbeat.
- **Scheduled tasks**: weekly catalog refresh, weekly
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
search ran on a bag-of-words fallback (and, since [[no-ollama]], the honest
name for it is keyword search); nothing had ever re-read the project
cards. Tests 114 → 549, coverage 40% → 90%, selfcheck 6 → 8 checks, and every
artefact the ecosystem produces now has a reader.

The rule that came out of it: [[decisions/verification-integrity]].

**2026-08-20 → 08-21, v4.3.26 → v4.4.3.** The same defect as the audit before
it, one layer further in: last time the finding was *information existed and
nothing read it back*. This time every reader existed, ran, and reported green —
while unable to fail in the way that mattered.

The weekly heartbeat had been structurally incapable of reporting itself
healthy: `task_doctor` inspected every `EcosystemBrain-*` task including the one
executing it, read its own in-flight run as a failure, and latched red for ever.
Nothing else surfaced for three weeks because that heartbeat is what surfaces
things. Underneath it: `doctor` compared repo → `~/.claude` and never the
reverse, so an agent deleted from the repo kept loading into every session under
`[ok] healthy`; `memory-index.py --check` printed counts and returned 0 whatever
it found, so the manifest the agent loads at session start went 18 days stale
unnoticed; `selfcheck` reported "pytest failed" when the real fault was no DNS;
a tracked machine note rewrote itself on every checkout; and four *live* projects
were nearly archived for sitting on a drive that is not mounted here.

Tests 549 → 619, heartbeat 8 → 11 checks, and every check that reports success
now has a way to fail. Four of five fixes were mutation-tested; one mutation
initially read as *caught* when it had simply never applied — the harness now
proves a mutant is live before believing a green suite.

Earlier milestones (project init engine, agent SHA pinning, model routing,
cross-tool AGENTS.md, the memory vault) are in `CHANGELOG.md` under v4.0–v4.3.4.

## Open questions

- [x] **Triage the 4 dead project cards** (opened 2026-08-02, closed 2026-08-21)
  — not dead. `betting-tracker`, `betting-stats-analysis`, `my-first-tool` and
  `viral-videos-sm` live on another PC that is still in use. An earlier draft
  archived them on the reasoning that this was *unknowable from this machine*;
  it was knowable by asking. They stay `active`, each with a note saying where
  it lives. `project_doctor` is gating in `maintenance.CHECKS` — safe because
  `elsewhere` exits 0, so a card on another machine never turns the report red.
  **Left over:** the `host:` pin needs that machine's `hostname`, the one fact
  this repo cannot derive on its own.

- [ ] **Prune the 6 unused third-party agents** (opened 2026-08-02, partly done
  2026-08-21) — `python-pro` and `cli-developer` are gone: the only two whose
  evidence window was complete. The other six predate the oldest transcript, so
  "never invoked" cannot speak for their first weeks. Transcripts are local, so
  confirm against the other PC before removing anything — parked behind the same
  hostname as above. Four *first-party* agents also show zero: that is a
  delegation habit to change, not a cleanup.

- [x] **profile_machine.py** (proposed 2026-07-15, shipped 2026-08-21) — writes
  `memory/machines/<host>.md`: hostname, OS, which drive roots exist, where this
  clone is, which prerequisites resolve. It is what turns "four cards point
  nowhere" into "four cards describe another PC". It recorded the current git
  branch at first, so the note rewrote itself on every checkout and kept turning
  up in unrelated diffs; `updated` now means the date these facts last *changed*.

- [x] **The weekly catalog refresh has nowhere to put its output** (opened and
  closed 2026-08-21) — `refresh-catalog.bat` rewrote the **tracked**
  `registry/catalog.json` every Sunday and nothing committed it: the file sat at
  its 2026-06-05 state for eleven weeks while the task reported success, and one
  refresh was nearly lost to an auto-stash.

  Resolved by gitignoring `catalog.json` and committing
  `registry/catalog.seed.json` as the floor. All three readers — `catalog.py`,
  `init_project.py` and the `suggest-agents` hook — prefer the live file and
  fall back to the seed, and a test asserts the three resolvers agree, since the
  hook must stay importable from nothing and cannot share a module. Reading the
  seed says so out loud: a stale answer that looks authoritative is the failure
  mode the whole arrangement exists to avoid.

  The seed is refreshed deliberately with `catalog.py build --seed`, not by the
  weekly task — a floor that moves on its own is not a floor.
