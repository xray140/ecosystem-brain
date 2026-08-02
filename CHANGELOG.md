# Changelog

All notable changes to ecosystem-brain. Dates are ISO-8601.

## [4.3.18] — 2026-08-02

**`agent_usage` was overstating its own evidence.**

It reported "35 local transcripts scanned" and, per agent, "never invoked here"
— which reads as *never since it was installed*. It can only ever mean *never in
the transcripts still on disk*, and measuring that gap turned out to matter:
transcripts here span **26 days** (2026-07-08 →) while six third-party agents
were installed as far back as **2026-06-04**. A 34-day blind spot the report
said nothing about.

That is the same defect this session kept finding, in the tool built to find it:
a number presented without the thing that qualifies it. Left alone it invites
deleting an agent that was used, on evidence that could not have seen the use.

The report now prints its evidence window and names the agents installed before
it starts. Local first-party agents are excluded from that warning — they are
versioned in this repo rather than fetched, so the window argument does not
apply to them.

## [4.3.17] — 2026-08-02

Vault curation and the rule the audit earned. No behaviour change.

- **`decisions/verification-integrity.md`** — the audit found the *same defect
  eight times* in different clothes, and the pattern was recorded nowhere. It is
  now: a gate nobody reads is not a gate, in three failure modes (not run; run
  but unread; run and reported dishonestly), with the eight instances as
  evidence and the tell that makes them survive — **degraded output is plausible
  output**, so verification has to mean *check the artefact*, not *it exited 0*.
- **`AGENTS.md`** gains that as a rule rather than leaving it in prose. The
  repo's own principle: when a rule keeps getting forgotten, promote it into a
  rules file.
- **`memory/roadmap.md` 216 → 144 lines.** It had accumulated 21 completed
  entries and become a changelog. Release history belongs in `CHANGELOG.md`; a
  note whose job is to orient a fresh session should carry the *open* questions.
  The three open items are preserved verbatim; everything closed is now one
  paragraph pointing at the changelog.

## [4.3.16] — 2026-08-02

**`init --apply` could not be run once without dirtying this repo — so it never
was, and it is now in CI.**

The flagship command writes a project card, a MOC line, a manifest refresh and a
registry mutation. Only the *destination* honoured an override
(`ECOSYSTEM_DEST_ROOT`); everything else went into the ecosystem's own vault and
registry unconditionally. A command you cannot run is a command you cannot test,
which is exactly how the Windows crash fixed in 4.3.13 — bare `npm` raising
`FileNotFoundError` inside its own green-baseline step — survived unnoticed.

- **`ECOSYSTEM_VAULT`** redirects the card, the MOC and the manifest refresh, for
  the same reason `ECOSYSTEM_DEST_ROOT` exists.
- **`--skip-agents`** excludes the half that cannot be redirected by env: agent
  installs mutate `registry/installed.json` and `~/.claude`.
- CI now runs `--apply` end to end and asserts `git diff --exit-code` — the
  checkout must be untouched afterwards.
- `append_to_moc` resolves its target at call time. A default argument binds the
  constant at import, the same trap that made `project_doctor.load_cards` audit
  the real vault from a test pointed at a temp one.

Verified by running it: scaffold, tailored AGENTS.md, card and MOC into the
sandbox, green baseline (`uv sync`, `pytest -q`), and `git status` clean.

**The new CI step found a real bug on its first run**, which is the point of it.
`scaffold.py --git` used `check=True` on its initial commit, so a machine with
no configured git identity got a raw `CalledProcessError` traceback reported as
"scaffold failed" — when the project had in fact been created correctly and was
perfectly usable. Every fresh runner and every developer who has never run
`git config user.name` hits this. `git_init()` now reports failure instead of
raising, and the scaffold succeeds with a warning naming the one-line fix.

Two notes on what this exercise did *not* establish. A `--build web` run
exceeded a 10-minute ceiling, but no component reproduced slowly in isolation
(`npm install` 38s, `npm test` 12s, one agent install 3.1s) — the likely cause is
a cold npm cache on first run, and I am not claiming a defect I could not
reproduce. And the first draft of the test for the new override used
`importlib.reload`, which mutates the shared module in place and leaked a
`demo.md` into the real vault; it now asserts the resolution rule directly.

## [4.3.15] — 2026-08-02

**Semantic search had never run on real embeddings.**

The README and the roadmap both advertise "Ollama semantic search
(nomic-embed-text, GPU)". What was actually in `memory/.search-index.db`:
**24 of 28 notes, every one embedded with the offline hash fallback** — a
bag-of-words stand-in meant for machines without Ollama. Ollama was running the
whole time and the model was pulled.

It went unnoticed for the reason degraded search always does: it returns
*plausible* results. You get notes back, they look related, and nothing says the
ranking came from word overlap rather than meaning.

Three compounding causes, all fixed:

- **No truncation.** `nomic-embed-text` answers HTTP 500 past roughly 2k tokens
  instead of truncating. Measured here: 4k chars fine, 20k fails — and
  `roadmap.md` (14k), the largest and most-read note in the vault, failed. Input
  is now capped at 6000 chars. Embedding a note's head is also the right
  semantics: frontmatter, title and opening paragraphs carry its topic.
- **One bad note aborted everything.** The 500 propagated as an unhandled
  traceback, so the build died and left the previous index untouched — which is
  how a hand-built offline cache survived for weeks. Failures are now per-note:
  the note is skipped, named, and reported as not searchable.
- **Nothing ever rebuilt it.** `memory-index.py` (what selfcheck and the
  heartbeat run) builds `index.json`, a frontmatter manifest — it has nothing to
  do with embeddings. `memory-search.py index` was only ever a manual command.

**`memory-search.py status`**, gating in the heartbeat, asserts what the index
actually contains: full vault coverage, the intended embedder, and a single
embedder (cosine scores from two models are not comparable, so a mixed index
ranks nonsense). The heartbeat also refreshes the index each run, so it cannot
rot again.

Verified end to end: 28/28 notes on `nomic-embed-text` at 768 dimensions, and a
query sharing no keywords with its target — *"why do we freeze dependency
versions instead of taking the newest"* — now ranks `decisions/toolchain-pinning`
first. That is a match a bag of words cannot make.

## [4.3.14] — 2026-08-02

**The weekly heartbeat had never completed a single scheduled run.**

Registered 2026-07-15, `State: Ready` ever since, and failing every week:
`SCHED_S_TASK_TERMINATED` for the catalog refresh, `STATUS_CONTROL_C_EXIT` for
the heartbeat. The catalog went **40 days** without a refresh. The only three
maintenance reports on disk were all produced by hand. Nothing noticed, because
everything that ever looked at those tasks looked at their **state** — and Ready
is not the same as working.

Two independent causes, both fixed and both verified by triggering the tasks and
reading the artefact rather than the exit code:

- `New-ScheduledTaskSettingsSet` defaults **both** battery guards to true, so on
  a laptop the task refused to start on battery and was killed if the machine
  switched to it mid-run. The registrar now passes `-AllowStartIfOnBatteries
  -DontStopIfGoingOnBatteries`.
- The `.bat` wrappers ran off their end with no `exit /b`, so Task Scheduler
  reported the console teardown instead of the script's real exit code. Fixing
  the battery guards alone left the heartbeat still reporting `0xC000013A`;
  adding an explicit `exit /b %ERRORLEVEL%` is what actually flipped it to 0.
- Both wrappers now tee to `memory/maintenance/*.log`. A scheduled task that
  dies used to leave nothing behind but an exit code — which is precisely why
  this went unexplained for weeks.

**`scripts/task_doctor.py`, gating in the heartbeat.** It judges each task on
its last *result* and the *age* of that result, never on its state, so a task
that is Ready-but-dead is loud. A stale success counts as a failure too: a
weekly task whose last green run is a month old is not running either.

- Windows-only by nature; elsewhere it reports "not applicable" and passes.
- Its first version returned "no tasks registered" **on a machine with three
  registered and two failing**: `ConvertTo-Json -AsArray` does not exist in
  Windows PowerShell 5.1, so the query failed and the empty result read as
  "nothing to check". Both that and 5.1's bare-object-for-one-row shape are now
  handled, and pinned by tests.

## [4.3.13] — 2026-08-02

The three remaining gaps from the capability audit. Suite 458 → 504.

**`update-agents --rollback <name>`.** Pinning exists so you control *when* an
agent moves; without the previous SHA there was no way to move back, and an
update that degraded an agent left only GitHub archaeology. The registry now
records `previous_commit` when a pin advances, and rollback re-fetches the old
content **at that SHA**, re-scans it, rewrites the file and swaps the pins — so
the rollback is itself undoable. The way back is gated too: the content passed
the scanner once, but no path into an active agent file skips it, not even this
one. A `↓` symbol distinguishes it in the report.

**`scripts/verify_templates.py`, wired into CI.** CI smoke-tested the init
*engine* with `--plan`, which writes nothing — so the engine was covered and the
templates were not. A dependency could break and nobody would learn of it until
the next person scaffolded a project and found it red on arrival. Each template
is now scaffolded for real into a temp dir and its own build+test run there: the
"verified green baseline" rule the ecosystem applies to projects it creates,
applied to the blueprints those projects are made from.

- Doing this surfaced a **pre-existing bug**: `verify_baseline` ran
  `subprocess.run(["npm", …])`, and on Windows `npm` is `npm.CMD` — a bare name
  raises `FileNotFoundError`. So `/ecosystem-brain:init` on a typescript project
  crashed with a traceback at the green-baseline step instead of reporting a
  failed check. Both call sites now share `resolve_exe()`, and an unlaunchable
  tool is a red baseline rather than a crash. Both templates verified green for
  the first time.

**`scripts/agent_usage.py` + `/ecosystem-brain:agent-usage`.** Every installed
agent costs SessionStart context, and nothing measured whether any were ever
used, so the roster only ever grew. Claude Code records each delegation as a
`subagent_type` in its session transcripts, which makes it answerable from data
already on disk. Current reading: **12 of 14 agents have never been invoked**
here; only `security-auditor` (7×) and `memory-curator` (1×) have.

- It reports and ranks; it never removes. Transcripts are local and rotatable,
  so "never invoked" means "not in what is on this machine" — an agent used
  daily on another PC reads as unused here. The output says so.
- First-party agents are listed separately and are never removal candidates.
  They are the squad the hook advertises on purpose: a zero there means *start
  delegating to it*, not *delete it*.

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
