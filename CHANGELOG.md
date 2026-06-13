# Changelog

All notable changes to ecosystem-brain. Dates are ISO-8601.

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
