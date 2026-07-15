# Changelog

All notable changes to ecosystem-brain. Dates are ISO-8601.

## [4.3.3] — 2026-07-15

Model-routing revision for the Sonnet 5 era (released 2026-06-30).

- **New routing tier — spec-driven code-gen → `sonnet`**: test-writer and
  script-smith move from `inherit` to `sonnet`. Sonnet 5 delivers frontier-level
  coding at scale, so committed code gets a constant quality floor on any
  session tier without burning frontier tokens on bounded work.
- security-auditor and bug-fixer deliberately stay `inherit` (verdicts and
  root-causing ride the session model); convention-keeper and memory-curator
  stay `haiku`.
- **Portability rule made explicit** in `model-routing.md`: tier aliases only in
  frontmatter, never full model IDs — audited: zero full IDs in
  scripts/templates/agents. Aliases float across model generations and the repo
  bootstraps identically on every machine; non-Claude tools read AGENTS.md and
  ignore `model:` frontmatter, so nothing breaks cross-tool.
- `docs/TOKENS.md` routing section + `new_agent.py` `--model` help updated to
  the three-tier scheme; model landscape refreshed (Claude 5 family, Sonnet 5).

## [4.3.2] — 2026-07-15

Robustness sweep — every issue found by auditing the live install, not the repo.

- **SessionStart hint fixed**: `suggest-agents.py` printed the canonical
  authoring path (`/d/claude-projects/...`) in its "Search more" hint, sending
  every session to a script that doesn't exist on this machine. The hint is now
  built from the script's own resolved location.
- **Doctor closes the hook-wiring gap**: `verify_live` only checked that hook
  *scripts* exist — a changed/added entry in `hooks/hooks.json` that was never
  re-bootstrapped stayed invisible. Doctor now diffs the live `settings.json`
  wiring against what bootstrap would write (path-rewrite aware). +4 tests.
- **Unpinned installs now warn**: when `gh` can't resolve a commit SHA (not
  authenticated, offline), `install-agent.py` said nothing and silently
  installed from the mutable branch. It now prints a loud `[warn]` with the fix.
- **Registry hygiene**: backfilled the missing commit pin on `data-engineer`
  (content at main@947b44c verified against the vetted md5 before pinning);
  repaired 9 `global_path` entries still pointing at the previous machine's
  user profile.
- Re-bootstrapped: live `memory-curator.md` had unrewritten `/d/` paths.

## [4.3.1] — 2026-06-14

Make the Obsidian graph show every connection — root-caused, not papered over.

- **Indexer resolver fixed**: `memory-index.py` matched note ids by basename
  only, so path-qualified links (`[[decisions/hook-format]]`) dangled — which
  orphaned `roadmap` (the hub linking every decision) and shattered the graph
  into **11 components**. The resolver is now path-aware (resolves
  `decisions/hook-format` → `hook-format`, like Obsidian) and **surfaces**
  dangling links under each note's `unresolved` + `counts.unresolved` instead of
  silently faking edges. Result: **1 connected component, 0 orphans, 0 dangling.**
- Vault README rebuilt as a true hub (links `roadmap` + `projects-moc` + all
  decisions by basename); removed the literal `[[wikilinks]]` phantom node.
- `docs/OBSIDIAN.md`: a "See every connection" graph-view guide (global/local
  graph, color groups by type, hiding auto-generated session/maintenance noise).
- +4 resolver tests (path-form resolves, dangling surfaced not faked, no self-edges).
- Graph view: the saved `memory/.obsidian/graph.json` now hides attachments,
  orphans, unresolved nodes, and the auto-generated `sessions/`+`maintenance/`
  logs — so opening `memory/` shows only the connected knowledge web.
  `docs/OBSIDIAN.md` warns to open `memory/` (not a parent folder, which would
  pull in screenshots, `__pycache__`, scripts, and per-project instruction files).

## [4.3.0] — 2026-06-14

`/ecosystem-brain:init` upgraded from "scaffolds fast" to "hands over a proven,
connected, publishable project." Closes the four gaps found by reviewing real usage.

### `/init` now also
- **Verifies a green baseline** — after scaffolding it runs the template's real
  build + tests (`uv sync` + `pytest` / `npm install` + `npm test`); a red
  baseline returns non-zero. No more handing over unproven scaffolds. *(proven
  end-to-end: `uv sync` + `pytest` run green on a fresh scaffold.)*
- **Names project API keys** — `--api-keys youtube,tiktok` seeds normalized
  placeholders (`YOUTUBE_API_KEY=`) into `.env.example`; names only, never values.
- **Optional GitHub publish** — `--github` creates a private repo and pushes,
  but only if the baseline passed (never pushes broken code).
- **Links memory cards into the graph** — every card links to a new
  `projects-moc` hub + stack decision notes, ending the orphan-card problem.

### Memory graph
- New `memory/projects-moc.md` hub; the four existing project cards backfilled
  (graph edges 25 → 39 — projects now connect to the decisions cluster).

### Internals
- `ECOSYSTEM_DEST_ROOT` override (testability); 10 new init-engine tests
  (env-key normalization, verify commands, gh command, card links, idempotent
  MOC append). 101 tests total.

## [4.2.0] — 2026-06-11

Informed by first real-world usage: two projects (`betting-stats-analysis`,
`viral-videos-sm`) were created via `/ecosystem-brain:init`; the pinning,
scanning, and suggester all worked unattended.

### Model routing & Fable 5
- **Agents routed by task shape** (`decisions/model-routing.md`): checklist
  agents (convention-keeper, memory-curator) → `model: haiku`; judgment agents
  stay `inherit` and ride the session model — Fable 5 on a frontier session.
  Per-invocation override documented.
- Recruiter accepts the **`fable`** alias; frontmatter lint validates model values.

### Robustness
- **selfcheck #6** — local agent frontmatter lint (name/description/tools/model).
- **Fixed**: `/init` memory cards no longer emit a literal `created: see-git`
  placeholder (root-caused after it leaked into two real project cards).

### Multi-LLM keys
- `.env.example` reserves `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `OPENAI_API_KEY`, `DEEPSEEK_API_KEY` (names only); `docs/MULTI-LLM.md` updated.

## [4.1.0] — 2026-06-06

A hardening, automation, and portability pass. All additive — no breaking
changes to existing commands or the installed-agent format.

### Security & supply chain
- **Agents pinned to commit SHAs** at install; `update` re-resolves the branch
  tip via `gh`, shows `oldsha → newsha` + a GitHub compare URL, re-scans, and
  advances the pin. Reproducible, tamper-evident installs. (`github_util.py`)
- **`quarantine/`** — HIGH-risk installs and upstream updates are stashed for
  review instead of discarded (gitignored; kept out of the repo).
- **Scanner hardened** to 20 rules — added PowerShell download cradles
  (`iwr|iex`, WebClient, `-enc`), `eval`/`exec`, and flag-first `curl -k`.
- **`update --all`** convenience flag.

### Reliability & verification
- **`/ecosystem-brain:doctor`** — live-hooks + repo↔`~/.claude` drift + prereqs.
- **Weekly maintenance heartbeat** (`maintenance.py`) — doctor + selfcheck +
  update-check → dated report. One-shot Windows registrar for all scheduled tasks.
- **pytest suite (82 tests)** across the scanner, init engine, pinning, drift,
  and path-rewrite; wired into selfcheck. **ruff lint** added to CI.
- **Portability repair** — fixed a path-rename breakage; `hooks.json` is now the
  single source of truth; `bootstrap --verify`; Linux/macOS path handling.

### Agents
- New first-party agents: **`script-smith`** (stack-correct scripts) and
  **`convention-keeper`** (read-only conventions auditor).
- **`/ecosystem-brain:new-agent`** recruiter — scaffolds agents to standard,
  scan-gates, and registers them.
- SessionStart surfaces the **first-party squad with trigger moments**.

### Conventions, docs & multi-LLM
- Aligned CLAUDE.md / AGENTS.md / agents with Anthropic's published best
  practices (Verification, plan-mode nuance, least-privilege framing).
- The repo **dogfoods AGENTS.md** — `CLAUDE.md` imports `@AGENTS.md`.
- **Multi-LLM**: scaffolds ship `GEMINI.md`; `docs/MULTI-LLM.md` rewritten with a
  per-tool support table + **DeepSeek** (model-via-host-tool) path.
- **`docs/TOKENS.md`** + a Context-discipline rule across the instruction files.

## [4.0.0] — 2026-06-05
- Baseline: 13 commands, guided `/init`, agent supply chain (search/install/
  catalog/update) with security scanning, secrets-safe git hooks, scaffolding,
  Obsidian memory with Ollama semantic search, CI (selfcheck + gitleaks).
