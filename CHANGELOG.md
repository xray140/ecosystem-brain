# Changelog

All notable changes to ecosystem-brain. Dates are ISO-8601.

## [4.3.5] — 2026-07-31

Gate repair. An audit of the verification chain found the CI lint step failing,
the local gate unable to see it, and two checks blind to things they claimed to
cover. Every fix below ships with a test; the suite went 114 → 157.

- **CI lint was red and nobody could tell.** `uv run --with ruff` resolves the
  newest ruff on every run; ruff 0.16 widened its default rule set and the job
  started reporting 44 findings no commit introduced. Fixed at both ends: a
  pinned `requirements-dev.txt` (ruff + pytest, exact `==` pins) used by CI and
  `selfcheck` alike, and an explicit `select` list in a new `ruff.toml` so the
  rule set is a decision, not a default. All 44 findings resolved — `check=False`
  made explicit at 7 `subprocess.run` sites, naive `date.today()` replaced by an
  aware local-date derivation, dead `noqa` markers removed, the zero-width
  character class rewritten as escapes.
- **`selfcheck` never ran ruff**, which is precisely why the divergence lasted:
  a change could pass locally and fail remotely. It is now check 6 of 7, running
  the same invocation and the same pinned ruff as CI, over the same four paths.
  Tests assert the two cannot drift apart.
- **`doctor` was blind to skill drift.** 4.3.4 taught `bootstrap` to copy
  `skills/<name>/SKILL.md`, but the drift check still globbed a flat `*.md`, so
  an edited skill that was never re-bootstrapped stayed invisible. `drift_in`
  now takes a glob and compares repo-relative paths, covering both layouts.
- **Installing a skill produced something nothing could load.** `install-agent`
  wrote skills flat, to `~/.claude/commands/` — neither the location Claude Code
  reads nor the one `bootstrap`'s `*/SKILL.md` glob finds. Skills now land at
  `skills/<name>/SKILL.md` under both the repo and `~/.claude/skills/`, named
  from their containing directory (every skill file is literally `SKILL.md`, so
  the old stem-based naming would have called them all "SKILL"). `detect_type`
  reordered — it checked `.md` before anything skill-shaped, making `"skill"`
  unreachable for every markdown file, i.e. always.
- **`--name` was a path.** It reaches the install target *and* the quarantine
  path, so `--name ../../x` wrote outside both. Validated against an anchored
  slug at the entry point, with `Path(name).name` as a second guard at the
  quarantine sink. The slug uses `fullmatch` + `\Z` (`$` also matches before a
  trailing newline), rejects Windows device names (`nul`, `com1`, … — a skill
  named `nul` makes `mkdir` succeed and the write inside it fail with an
  unhandled traceback, and that name can come from upstream), and lowercases
  rather than rejects on case, since these become paths on a case-insensitive
  filesystem and upstream repos are inconsistent about it.
- **New `scripts/layout.py`** — one answer to "where does an item of kind K
  named N live", imported by both `install-agent` and `update-agents`. They
  answered it separately and drifted: once install moved skills to
  `<name>/SKILL.md`, update kept writing them flat, so `/ecosystem-brain:update`
  on a skill wrote vetted content to a path nothing loads and then advanced the
  registry pin — reporting the skill current while the loaded copy stayed stale.
  The HIGH-risk branch still quarantined correctly throughout, so no unsafe
  content could become active; the failure mode was stale-but-reported-updated.
  A test now asserts the two resolve identical paths for all three kinds.
- **Scan reports buried MEDIUM findings.** `format_report` sorted on the
  severity string, ordering HIGH, LOW, MEDIUM. Severity ranking is now shared
  with `worst()` and the report reads worst-first.
- `stderr` reconfigured to UTF-8 in `install-agent` (it carries the same
  accented paths as stdout); tool caches and coverage artifacts gitignored.

## [4.3.4] — 2026-07-31

Line-endings and encoding sweep — every text file the ecosystem writes was
being emitted as CRLF on Windows, against the repo's own `.gitattributes`.

- **CRLF at every write site (16 total)**: `Path.write_text()` runs in text
  mode, so on Windows each `\n` became `\r\n` — contradicting
  `* text=auto eol=lf`. Fixed with `newline="\n"` across `install-agent`,
  `update-agents`, `bootstrap`, `catalog`, `init_project`, `maintenance`,
  `new_agent`, `scaffold`, `scan_agent`, and `memory-index`. Symptom: the
  three GitHub-sourced agents (cli-developer, data-engineer, python-pro) sat
  permanently dirty in `git status`, and every scaffolded project came out
  CRLF (8 files per project, measured).
- **Upstream CRLF normalized**: `newline="\n"` alone does not strip `\r\n`
  that fetched content already carries, so `install-agent`/`update-agents`
  also `.replace("\r\n", "\n")` before writing. `scan_agent`'s quarantine
  write deliberately does not — a forensic copy should not be re-translated.
- **`UnicodeEncodeError` on non-ASCII agent metadata**: the JSON I/O on
  `installed.json` / `registry.json` ran without `encoding=`, falling back to
  the locale codec (cp1252 on Windows). A single non-ASCII character in an
  agent's frontmatter aborted `:install`. Reproduced with `✓`, fixed with
  explicit `encoding="utf-8"` on all reads and writes.
- The three affected agents are renormalized to LF in both the repo and
  `~/.claude` (content verified byte-identical to the index by hash).
- Vault: `sensor-csv-pipeline` recast as `ipe-pipeline` (ISO 50001 IPE
  tracking for the LSF Verdun plant), `plan-action-energie-environnement`
  taken in, python-pro and cli-developer re-pinned to `947b44c`.

Known-unfixed, tracked for a later pass: `skills/memory/SKILL.md` still
prints the dead canonical path `/d/claude-projects/...` in its usage line —
the same defect 4.3.2 fixed in `suggest-agents.py`, never propagated here.

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
