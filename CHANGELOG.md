# Changelog

All notable changes to ecosystem-brain. Dates are ISO-8601.

## [4.3.12] — 2026-08-02

**`project_doctor.py` — the ecosystem finally looks at what it built.**

`doctor.py` answers "is my install wired up correctly". Nothing answered "are
the projects I registered still there". The vault's project cards were written
once at init and **never read back by anything** — the only file that mentions
`memory/projects/` is `commands/scaffold.md`, the one that writes them.

They had drifted accordingly: four of seven cards still said `status: active`
while pointing at `D:\claude-projects\…`, a drive path that does not exist on
this machine. The control tower created projects and then went blind.

- Per card: does the recorded path resolve, last-commit age, uncommitted
  changes, `AGENTS.md` present, keys the `.env.example` names but the `.env`
  lacks, and — advisory only — the latest CI conclusion when the project has a
  GitHub remote. No network, no `gh`, or a timeout must never turn this red.
- **"Elsewhere" is not "gone".** The vault is shared across machines; project
  locations are not. `D:\claude-projects\x` is a *correct* path — on the PC that
  has a `D:` drive. When the whole root is absent, the project is not lost, and
  reporting a missing path would send you hunting for nothing. Such cards report
  `[->] elsewhere` and do not fail the run; `host: <machine>` in the frontmatter
  pins it explicitly. A path whose root **does** exist but whose directory does
  not is still a real problem.
- **It reports; it does not repair.** Only the user knows whether a project was
  deleted, moved, or lives on another machine, and the right fix differs. Three
  one-line escape hatches: add `host:`, update the `- Project: ` line, or set
  `status: archived` (archived cards are listed and never fail the run, so a
  recorded decision stops nagging while an unexamined one keeps surfacing).
- Wired into the maintenance heartbeat as **non-gating for now**: until those
  four cards are triaged, a gating check would leave the weekly report
  permanently red, which is how a report stops being read. Flip once clear.
- New `/ecosystem-brain:project-doctor`.

**The heartbeat was mislabelling failed advisory checks as `ok`.** Its status
was two-state (`FAIL` if gating-and-failed, else `ok`), so the project doctor's
four dead paths were filed under a section titled `— ok`, where nobody skimming
the headings would open it. Now three-state — `ok` / `warn` / `FAIL` — and the
verdict line distinguishes "all clear" from "all gates green, advisory
warnings". *Advisory* means "does not turn the run red", not "did not happen".
This is the same defect as the `[!]` fallback fixed in 4.3.11, reintroduced two
hours later by the change that added the first advisory check able to fail
meaningfully.

Also: `load_cards()` resolves the vault at call time. A default argument of
`vault: Path = VAULT_PROJECTS` binds at import, so tests pointed at a temp vault
silently audited the real one. (`init_project.append_to_moc` still has that
shape; it takes an explicit `moc=` instead.)

## [4.3.11] — 2026-08-02

- **`update --check` cried wolf on every run.** The status→symbol cascade used
  `!` as its fallback, which swept in two perfectly ordinary outcomes: `local`
  (a first-party agent with no upstream to query — six of them, every single
  run) and `synced` (a local agent re-copied to `~/.claude`, i.e. success). The
  weekly maintenance report therefore carried eight `[!]` markers with nothing
  wrong, and a column that cries wolf eight times a run stops being read.
  `local` is now `·` and `synced` is `→`; `!` is reserved for `error:` and
  `missing-in-repo`.
  - `synced` was the one nobody had noticed: it only fires after a first-party
    agent actually changes, so it had never shown up in a report yet.
  - Extracted to a named `status_symbol()` and covered against **all nine**
    status strings the code can emit — enumerated from the source rather than
    from memory. Plus the safety property: an unrecognised status falls back to
    `!`, so a status added later without updating the table is loud rather than
    quietly mislabelled as fine.

## [4.3.10] — 2026-08-01

A Linux bug the Windows test suite could not see, and the documentation drift
left by five releases.

- **The SessionStart suggester mangled real posix paths off Windows.**
  `normalize_path` translated a leading `/<letter>/` to a drive form
  unconditionally, so on Linux and macOS a project at `/d/projects/app` — an
  ordinary posix path — became `D:/projects/app`. The hook then found no marker
  files, detected no project type, and silently suggested nothing. `bootstrap.py`
  has carried the `WINDOWS` guard for exactly this since 2026-06-06; the second
  copy of the function never got it. Same shape as every other defect this audit
  found: a fix applied to one copy of duplicated logic.
  - The test that pins it **forces the non-Windows branch** rather than comparing
    the two copies, because on Windows both translate and therefore agreed —
    a comparison would have passed against the bug. Verified by reverting the
    guard: the new tests fail, and pass again once restored.
- **Docs caught up with the code**:
  - `README` — added `doctor` and `new-agent` to the command table (the repo
    ships 15, the table listed 12); corrected `update` from "hash-based" to what
    it does (re-resolves the tip, re-scans, advances the commit pin); listed the
    six first-party agents rather than four; added a **Verification** section;
    dropped the claim that `GITHUB_TOKEN` feeds `.mcp.json`, which has shipped
    empty since 4.3.3 — `gh auth login` is what the supply chain actually uses.
  - `INSTALL.md` — the maintenance heartbeat runs `doctor`, not
    `bootstrap --verify`; verified against `maintenance.CHECKS`.
  - `docs/TOKENS.md` — stopped recommending the exact three MCP servers this
    repo removed as dead weight, and says why they were removed.
  - `memory/README.md` — the destructive guard is `guard_destructive.py` now.

CI was also run step-by-step locally (gitleaks over full history, ruff, pytest,
selfcheck, both init smoke plans): all five exit 0 with no side effects. The
ubuntu run itself stays unverified until this branch is pushed.

## [4.3.9] — 2026-08-01

The last coverage gap. Suite 395 → 418; coverage 86% → **90%**, every script at
81% or above. No production code changed.

- **`init_project.py` 54% → 83%.** The uncovered half was `apply()` — the part
  that scaffolds, installs agents, writes the memory card, and optionally
  pushes. Every subprocess is stubbed, so nothing scaffolds or publishes for
  real. What is pinned:
  - **A red baseline never reaches GitHub.** `--github` publishing broken code
    is the one outcome in this script that other people can see, and the
    ordering that prevents it (verify, *then* publish) was previously untested.
  - `.env.example` gets key *names* only — the test asserts every non-comment
    line ends in `=`, so a value can never ride along.
  - A blocked agent is reported and excluded from the ready count without
    failing the whole init; an install error is distinguished from a block.
  - A failed scaffold aborts before anything else runs.
  - `append_to_moc` is idempotent, so re-running init cannot duplicate a
    project in the graph hub.

One note for the next person writing tests here: the `cfg` dict is built from
the real profile engine (`resolve()`), not hand-rolled. The first draft of these
tests hand-rolled it, and it failed immediately on a key the engine actually
produces — a fixture that duplicates a shape drifts from it.

## [4.3.8] — 2026-08-01

Coverage on the remaining gaps. Suite 312 → 395; coverage 64% → **86%**. No
production code changed — these are tests for behaviour that already worked and
now cannot silently stop working.

- **`selfcheck.py` 34% → 85%.** The gate itself was the least-verified thing in
  the repo, which is precisely the condition that let a red CI go unnoticed for
  weeks. Each check is now tested for the property that matters: that it goes
  **red when its subject is broken**. A check that cannot fail is decoration.
  Also pinned: `main()` runs all 8 checks even after one fails (stopping early
  would mean N runs to see N problems), and local agents stay exempt from the
  scanner while third-party ones do not.
- **`bootstrap.py` 44% → 99%.** This is the code that edits the live
  `~/.claude`, so the tests cover what a user only discovers once it is already
  broken: merging hooks preserves their other settings (`model`, `mcpServers`),
  `--dry-run` writes nothing at all, and an existing `.env` is never overwritten
  by the example. Plus: no installed file carries an unexpanded token.
- **`doctor.py` 52% → 98%** — that it *exits non-zero* on what it detects, not
  just prints it. The heartbeat consumes that exit code.
- **`catalog.py` 30% → 98%** — chiefly that a batch install reports the
  scanner's verdict honestly: exit 2 is counted as blocked, never folded into
  the error bucket or the success count. It is the one command that installs
  many agents at once, and the summary line is all anyone reads.
- **`new_agent.py` 49% → 99%** — preview is the default and `--register` routes
  through the same scanning installer as any third-party agent. A recruiter that
  could install unscanned content would be a hole through the supply chain it
  belongs to.
- **`update-agents.py` 48% → 81%** — that every status which mutates a registry
  entry is actually persisted. The failure mode otherwise is the pin falling
  behind the content, which is how an agent reports "current" while stale.

Still uncovered: `init_project.py` at 54% — its `apply()` path scaffolds a real
project on disk. CI smoke-tests `--plan` on all six build types.

## [4.3.7] — 2026-08-01

Coverage on the scripts that had none, and the end of the hardcoded authoring
path. Suite 246 → 312; coverage 47% → 64%.

- **`{{ECOSYSTEM_ROOT}}` replaces the literal authoring path.** Committed files
  named `/d/claude-projects/ecosystem-brain` — the machine this was written on
  — and it worked only because `bootstrap.rewrite_paths` substituted the string
  on the way out. So when the repo moved to `~/ecosystem-brain`, **58 references
  across 16 files pointed at a directory that existed nowhere**, and nothing
  noticed, because the rewrite kept repairing them. Files now use a token, which
  cannot rot: it is never a valid path to begin with. Legacy literals and
  `${CLAUDE_PLUGIN_ROOT}` are still rewritten, so an older clone migrates on its
  next bootstrap.
- **selfcheck fails on any hardcoded path** in an installable file (check 6 of
  8) — the half the old scheme was missing. It distinguishes a path that names a
  location from one documenting the path convention (`script-smith` has to be
  able to say that `/d/...` resolves to `D:\d\...`).
  - This closed the defect logged as known-unfixed in 4.3.4:
    `skills/memory/SKILL.md` was still printing the dead path. Verified after
    re-bootstrap: 16 live files now point at this clone, zero dead paths, zero
    unexpanded tokens.
  - `commands/scaffold.md` no longer hardcodes `--dest-root`; `scaffold.py` has
    defaulted it to the clone's parent since 4.3.4, so the flag was both dead
    and wrong on any other machine.
- **Tests for the three scripts that had none**: `suggest-agents.py` 0 → 94%
  (it runs on *every* session start and was the least-tested code in the repo),
  `search_agents.py` 0 → 87%, `maintenance.py` 0 → 95%. `install-agent.py`'s
  `main()` is now covered too, 32% → 91% — including that HIGH-risk content is
  absent from the repo, from `~/.claude` *and* from the registry, not merely
  that the exit code was 2.

## [4.3.6] — 2026-08-01

Supply-chain and blast-radius hardening — the second half of the same audit.
Suite 174 → 246; coverage 40% → 47%, with `scaffold`, `github_util` and the
destructive guard going from untested to 85-87%.

- **`fetch_url` accepted any URL scheme**, so `--url file:///…/.env` read a
  local secret and handed it to the installer as content to install. The fetch
  sits upstream of every other control — the scanner and the SHA pinning are
  both irrelevant if the fetch itself can be aimed at the filesystem. Now
  https-only, against a host allowlist, re-checked on every redirect hop, with
  a 1 MB cap and a strict UTF-8 decode.
- **The destructive guard is rewritten in Python** (`guard_destructive.py`,
  replacing the shell `case`), because substring matching failed in both
  directions. False negatives: `rm  -rf /`, `rm -r -f /` and
  `rm --recursive --force /` all passed. False positives: the home patterns
  were prefixes, so `rm -rf ~/.claude/skills/one-thing` was refused as a
  catastrophic delete — and a guard that blocks ordinary work gets worked
  around, which costs more than it protects. It now tokenizes, normalizes the
  flags, splits on `&&`/`;`/`|`, and compares each *target* against the
  catastrophic set exactly, never as a prefix. Also catches `git push origin
  +main` (forced via refspec, no `--force` flag) while allowing
  `--force-with-lease`. 43 tests, both directions.
- **`scaffold.py --force` ran `shutil.rmtree` on an unvalidated `--name`**, so
  `--name .` aimed that delete at the root holding every scaffolded project.
  `resolve_dest` now applies two independent checks — a slug pattern, and a
  containment check on the resolved paths.
- **GitHub Actions pinned to commit SHAs** (was `@v4`/`@v2`/`@v3`). A tag is
  mutable; whoever controls the action repo can repoint it at new code that
  then runs here with a `GITHUB_TOKEN`. Same reasoning as `agent-pinning`,
  which the repo already applied to what it downloads but not to what it runs.
  `dependabot.yml` added so pinned no longer means stale — the actions and the
  dev toolchain both get monthly PRs.

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
*(Closed in 4.3.7, along with the 57 other occurrences it turned out to have
company in.)*

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
