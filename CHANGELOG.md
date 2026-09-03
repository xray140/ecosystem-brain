# Changelog

All notable changes to ecosystem-brain. Dates are ISO-8601.

## [4.8.1] — 2026-09-03

**Eight weeks of heartbeat reports were mojibake, and every run exited 0.**
`maintenance.run()` captured its children with `text=True` and no `encoding=`,
so their UTF-8 came back decoded through the locale codepage: every em dash a
check printed (bytes E2 80 94) was written into `memory/maintenance/<date>.md`
as three cp1252 characters, and `update --check` filed its tick as `âœ“`. The
corruption grew with the report — 1 occurrence on 2026-07-15, 15 by 2026-08-31 —
while doctor, selfcheck, project-doctor and task-doctor all passed, because
nothing was broken in the sense a check measures. The run was fine. The artefact
was not. That is the failure `memory/decisions/verification-integrity.md` names,
and the line at fault was the only uncovered line in the file.

Fixed at the site, then generalised: `tests/test_subprocess_encoding.py` walks
every `.py` under `scripts/`, `hooks/`, `skills/` and `tests/` with `ast` and
requires each text-mode subprocess call to name `encoding="utf-8"` and an
explicit `errors=`. Sixteen call sites already did; eleven did not.

Fixing the capture side surfaced the other half of the boundary. With the parent
finally decoding UTF-8, `memory-search.py status` still arrived as
`memory search index � vault has 51 note(s)`: a child whose stdout is a pipe
*encodes* with the locale codepage unless it says otherwise. Seven entry points
never reconfigured stdout, and `selfcheck.py` was getting it right only by
accident — it imports `scan_agent`, which reconfigures at import time, and
reconfiguring is process-global. Both halves are now enforced, and the decision
is written down in `memory/decisions/encoding-discipline.md`.

`errors=` earned its place within the hour. Fixing the encoding alone made
`mutate_checks.py` decode strictly, and its next run died in a subprocess reader
*thread* on byte 0x97 — a cp1252 em dash from a French-locale child — reporting
all 20 mutants caught and exiting 1 anyway, with the captured output truncated
and nothing to say why. Not every child is ours: `git`, `gh`, `npm` and cmd.exe
all speak the console codepage on occasion.

**`memory/roadmap.md` had gone four releases stale, and nothing read it.** It is
the note a fresh session opens first, and it opened with *Current state
(v4.4.3)* against a repo at v4.8.0, citing 619 tests at 89% coverage against 756
at 93%, `memory-search.py` "lowest at 70%" when it is at 100%, an 8-check
selfcheck, and a CI job on ubuntu alone — the Windows runner added in v4.7.1 was
missing from the one document that orients someone to the platform this
ecosystem runs on.

`selfcheck` check 9 now reads seven derivable claims back against the repo:
version, command count, build types, first-party agent count, selfcheck's own
step count (counted from the calls in `main()`, not the definitions), heartbeat
check count, and the coverage floor. A claim that no longer *matches* fails; so
does a claim that has been *deleted*, because deleting the sentence must not be
the way to silence the gate. The volatile numbers are gone from the note on
purpose: test count and coverage percentage move with every commit, so the note
cites the floor, which moves only when a person raises it.

**`plugin.json` was still advertising "local semantic search".** v4.8.0 said
every doc that claimed semantic search now says keyword search. README did.
`plugin.json` — the marketplace description, the one line someone reads before
installing any of this — did not, for eleven days, because nothing reads it
either. Corrected, and `test_ollama_is_gone.py` now holds the shipped
descriptions, commands and skills to it. History is still free to say what
semantic search was and what removing it cost; `CHANGELOG.md` and `memory/` are
deliberately not scanned.

**CI was red on master from two commits that touched only memory notes.** The
step was `verify_templates.py`, failing on both platforms with `npm install`
crashing inside arborist — *Cannot read properties of null (reading
'edgesOut')* — while the same template scaffolded green locally on npm 11.16.0.
Nothing in the repo had changed. Two things outside it had, and both were
unpinned: `templates/typescript-project/package.json` carried five floating `^`
ranges with no lockfile, and **CI installed no node at all**, so the typescript
baseline ran on whatever the runner image shipped that morning.

This is the unpinned-ruff incident of v4.3.x in the other language, five weeks
later. Fixed the same way: exact versions in the template (biome 1.9.4,
@types/node 22.20.1, tsx 4.23.13, typescript 5.9.3, vitest 4.1.11 — the
resolution verified green locally), and `actions/setup-node` pinned by commit
SHA to node **24.20.0**. The exact patch, not the major: npm ships *with* node,
so `24` would leave the thing that actually broke free to drift.

Three tests in `test_selfcheck.py` hold it: template dependency specs must be
exact, `node-version` must be a full patch version, and every action in the
workflow must be a 40-char SHA — the last one caught nothing today and exists
because a tag is mutable and runs with a `GITHUB_TOKEN`. See
`memory/decisions/toolchain-pinning.md`, which had claimed since 2026-07-31
that the ecosystem "was pinning what it downloaded and floating what it ran".
It was right, and it was describing Python only.

**The supply-chain gate had 20 rules and no evidence that 20 of them worked.**
`scan_agent.py` sat at 100% line coverage, which proves the loop over `RULES`
ran and nothing else. It could not say that a rule matched what its label
claimed, that it still matched after someone tightened its regex, or that it was
doing any work at all — a rule whose every example was also caught by a
neighbour could be deleted with the suite still green.

`tests/test_scan_agent_rules.py` is a corpus instead of a set of examples. Each
of the 20 rules gets a probe it must flag with an exact label and severity, and
a near-miss — benign text that looks like the attack — it must not. Two tests
keep the corpus honest as the table grows: one fails when a rule is added
without a probe, the other requires probes and rules to be the same number and
every probe's label to be one a rule actually defines.

`test_no_rule_is_dead_weight` is the part that matters. It deletes each rule in
turn and requires one of that rule's own probes to stop being flagged — 20
mutations of a data table, run in the normal suite. All 20 rules survive it, so
the number is now 20 rules that each catch something nothing else catches. The
tool-grant heuristic is checked separately, since it is a function rather than a
row and the loop cannot reach it.

Verified against the corpus itself: a duplicated rule, a rule with no probe, and
a neutered regex each turn the file red. Three matching entries are registered
in `mutate_checks.py` (26 caught, 0 missed, 0 skipped), and `selfcheck` check 9
now reads the roadmap's advertised rule count back against `len(RULES)` — the
count means something now, so it gets checked like the other claims.

One characteristic is pinned as deliberate rather than fixed: prose *about* an
attack trips the same rule as the attack. A prose exemption would be a bypass —
an attacker need only phrase the payload as documentation — so the gate fails
closed and a human reads the quarantined file.

**Two mutants had been unplantable since v4.8.0.** `mutate_checks.py` anchored
on `args.offline` and on the Ollama request body, both removed with the backend,
so it skipped them and exited 1 on every run — a harness that reports its own
red is one nobody runs twice. Retargeted onto the properties that outlived the
backend: a status check that cannot report an under-covered index, and a
truncation that no longer stops a long note drowning its own topic. With three
new mutants for the fixes above, the harness is 20 caught, 0 missed, 0 skipped.

## [4.8.0] — 2026-08-22

**Ollama is out.** Not demoted — removed.

v4.7.0 made it optional and kept the capability, which was the right call for
the argument being had then. It was not the ask: the process was still the
recommended path, `nomic-embed-text` was still the default, `OLLAMA_MODELS` was
still in `.env.example`, and every health report still printed a line about it.

Removed: `OllamaEmbedder`, the `nomic-embed-text` default, `--offline` (a flag
that opts out of a backend that no longer exists is worse than no flag — it
implies a choice), `OLLAMA_MODELS`, the `OPTIONAL_TOOLS` prerequisite list and
its print branch, and the install section. `memory-search.py` imports no
networking library at all now.

`MAX_EMBED_CHARS` stays, and moves to the embedder that now enforces it. The
500s that first forced the cap are gone with the backend, but the other reason
outlived them: the head of a note — frontmatter, title, opening paragraphs —
carries its topic, which is what recall matches on.

**The cost, stated plainly.** Search matches wording, not meaning. The query
*"why is the registry split between shared and machine-local"* scored 0.805 with
Ollama, 0.545 without; re-measured after removal it returns the right note first
at 0.538. Rank survived, margin did not. Nothing was added back to compensate —
`sentence-transformers` means torch on Windows for a 42-note vault, and an API
embedder means a key, a cost, and private notes leaving the machine. The honest
upgrade, if recall ever gets bad enough to matter, is BM25 over the vault. Every
doc that said "semantic search" now says "keyword search"; see
`memory/decisions/no-ollama.md`.

**`register-scheduled-tasks.ps1` announced a removal it had not performed.** The
retire loop printed `[retired]` unconditionally, with `-ErrorAction
SilentlyContinue` hiding the failure — while the registration loop ten lines
below already handled the identical elevation failure honestly. Unregistering a
task created in an elevated shell answers `Accès refusé`, which is exactly the
state Verdun10 was in: the task retired in v4.7.0 was still registered and still
failing three weeks later, and the script kept reporting success. It now
re-queries after the removal, prints `[STUCK]` with the fix, and exits non-zero.

`tests/test_ollama_is_optional.py` → `tests/test_ollama_is_gone.py`: no backend,
no network imports, no flag, no env key, no prerequisite, and the retired task is
*still* actively unregistered — removal is not the same as never having shipped
it. Prose was tried; it lasted one release.

## [4.7.0] — 2026-08-21

**Ollama was wired in like a dependency to power one optional feature.**

It does exactly one job here — embeddings for `memory-search` — and
`memory-search` already degrades gracefully without it. Yet it had a
logon-triggered scheduled task keeping a server up, a line in the prerequisite
list, and a status check that failed whenever the index used the offline
embedder. On a machine without Ollama that check could not be satisfied except
by installing software the user had chosen not to run.

Most of its bad reputation was not its own. `OllamaServe` sat red for weeks
pointing at `D:\ecosystem-tools\start-ollama.bat`, a path the script had long
since left, and the degraded index found on 2026-08-21 came from the heartbeat
being latched red and never running the refresh. Neither was Ollama
misbehaving — but between them they made it look like the problem.

Removed: the `OllamaServe` task and `scripts/start-ollama.bat`. The registration
script now actively unregisters it, because dropping it from the list is not
enough — a machine that already has it registered keeps failing until something
removes it, and has no other way to learn the task is gone.

Prerequisites split into `REQUIRED_TOOLS` and `OPTIONAL_TOOLS`. A missing
optional tool prints `[--] ollama (optional)` rather than `MISS — install for
full functionality`.

The status check keeps its teeth where they mean something. A hash-embedded
index is a defect when Ollama is **reachable**, because then the index is worse
than the machine can do and a rebuild fixes it; it is the expected state when
Ollama is absent. Same rule the rest of this release follows: do not raise a
warning whose only remedy is unavailable.

Kept: `OllamaEmbedder`, `nomic-embed-text`, and the semantic search the plugin
description advertises — which is worth keeping. A query phrased *"why is the
registry split between shared and machine-local"* returns the right note at
0.805 against 0.545 for the runner-up, with almost no shared keywords. The
fallback matches wording; this matches meaning. Run `ollama serve` and rebuild
to use it.

## [4.6.0] — 2026-08-21

**A shared file was recording machine state, so it was wrong on every machine
but one.**

`registry/installed.json` is tracked in git, but two of its fields describe one
particular computer: `global_path`, an absolute path under a username, and
`installed_at`, when *this* machine installed the item. Every checkout rewrote
every entry it touched, so two machines conflicted line-for-line on a file
neither had meaningfully changed.

Found the concrete way. Pulling a stale checkout forward produced a conflict in
which "upstream" was the `Verdun-10` machine's install state and "local" was
`MSI`'s — neither more correct than the other. Worse, the committed file listed
`data-engineer` as installed while it was absent from this machine's disk. The
merge friction was the symptom; the registry describing a computer that is not
the one reading it was the defect.

Split by lifetime:

| file | tracked | holds |
|---|---|---|
| `registry/installed.json` | yes | `name`, `source`, `hash`, `ref`, `commit` |
| `registry/installed.local.json` | gitignored | `global_path`, `installed_at` |

The tracked half is exactly the part that is true everywhere, including the
pinned commit SHAs that are the point of having it. The local half is
regenerated by any install and is never worth a conflict.

Callers see neither. `scripts/registry_io.py` exposes `load()` returning the
merged flat shape the registry has always had, and `save()` splits it again on
the way out, so `install-agent.py`, `update-agents.py`, and `agent_usage.py`
read and write entries exactly as before. `selfcheck.py` and the SessionStart
suggester needed no change at all — they only ever read `name` and `source`.

Legacy files migrate themselves: a tracked entry still carrying the machine
fields is read as this machine's local values, and the next `save()` writes them
to the local file and drops them from the shared one. `uv run --no-project
python scripts/registry_io.py` does it as a one-shot and reports the count.

Losslessness was checked against the real 14-entry registry, not only against
fixtures: the merged view after migrating is byte-identical to the file before
it. The test that matters is `test_two_machines_do_not_conflict_in_the_tracked_half`
— the same install recorded on two machines now produces identical tracked
bytes.

`installed_at` being machine-local is the one judgement call. `agent_usage.py`
uses it to warn that an agent predates the oldest surviving transcript, so
"never invoked" cannot speak for its first weeks. That comparison is against
local transcripts, so the date has to be the local one or the warning is
computed from another computer's history.

Other checkouts should `git pull` before their next install; otherwise they
re-add the machine fields and migrate them straight back out on the following
save. Harmless, but it makes one extra diff.

## [4.5.3] — 2026-08-21

**Every hook was one space away from never running, and two tests were guarding
the wrong thing.**

`hooks.json` interpolated `{{ECOSYSTEM_ROOT}}` into each command unquoted:

    bash {{ECOSYSTEM_ROOT}}/hooks/scripts/guard-secrets.sh

That token expands to this clone's real path. On Windows the home directory
routinely carries the user's full name, so the expansion contains a space, and
the shell splits the path in half before `bash` ever sees it. The hook does not
fail in a way anyone reads — it just doesn't run. That includes
`guard-secrets.sh`, the gitleaks gate on every commit and push, and
`guard_destructive.py`, the confirmation gate on `rm` and `git push`. The
enforcement this repo prefers over prose was silently absent for anyone who
cloned into a path containing a space.

Every script path in `hooks.json` is now double-quoted, and
`_hook_script_paths` splits with `shlex` instead of `str.split` so the verifier
reads those quotes — `shlex` was already the idiom in `guard_destructive.py`.

Worth recording why CI never saw it: the GitHub runners clone to
`/home/runner/work/...`, which has no spaces. The bug was only reachable from a
real Windows checkout, and it surfaced on a fresh clone rather than from the
suite that had been green for months.

Two tests failed alongside it for unrelated reasons, both the same species —
asserting a proxy instead of the property:

- `test_a_real_change_still_rewrites` forced `drives()` to a hardcoded
  `["C:", "D:"]` to prove a changed fact rewrites the machine note. That is what
  the developing machine already reports, so before and after were byte
  identical and the test asserted its own no-op. It now derives a sentinel drive
  letter absent from the real list.
- `test_search_hint_uses_this_clones_real_path` banned the literal string
  `/d/claude-projects` as a stand-in for "the path isn't hardcoded". But a
  correctly derived hint contains that string on any machine that really does
  clone there, so the check failed the very fix it was pinning. It now moves
  `REPO_ROOT` somewhere arbitrary and asserts the hint follows.

Both new hook tests were confirmed to fail against the original source before
being accepted. The first draft of the space-in-path test passed against the
unfixed code for the wrong reason — whitespace splitting leaves a
`guard-secrets.sh"` fragment whose trailing quote fails the `.sh` suffix check,
so the hook was skipped entirely and `verify_live()` returned 0 with nothing
stale to report. It now asserts the path is actually recovered, not merely
absent from the failure list.

Anyone already bootstrapped from a path containing a space should re-run
`uv run --no-project python scripts/bootstrap.py` to rewrite the live
`settings.json`; `--verify` will now report such paths honestly instead of
skipping them.

## [4.5.2] — 2026-08-21

**A stubbed function stayed stubbed for the rest of the test session.**

Two tests in `test_memory_search.py` set `ms.pick_embedder = lambda ...` as a
bare module assignment rather than through `monkeypatch`. That survives the
test: for every test that ran afterwards in the same session, `pick_embedder`
was still the fake. Anything downstream depending on the real one was exercising
a leftover stub and passing for the wrong reason.

The suite stayed green throughout, because no test happened to notice. It was
found by the `test-writer` agent while raising coverage — flagged, correctly, as
out of scope for that task rather than fixed silently in passing.

Demonstrated before fixing: a probe asserting `ms.pick_embedder is
_real_pick_embedder` passes in isolation and fails after the file runs.

Both are now `monkeypatch.setattr`, which undoes itself. More usefully, an
autouse fixture snapshots every module-level function and class and compares
identity at teardown, so the whole class of leak fails immediately rather than
waiting for a downstream test to be quietly wrong. `monkeypatch` unwinds before
that teardown, so legitimate patching passes and only bare assignment trips it.

Verified by reintroducing the original bug: pytest exits 1. Worth noting the
summary line reads `32 passed, 1 error` — the failure surfaces as a teardown
error rather than a test failure, which looks green to a skimmer but is red to
anything reading the exit code, which is what selfcheck and CI do.

## [4.5.1] — 2026-08-21

**The lowest-covered file in the repo was the one with a history of degrading
without failing.**

`memory-search.py` sat at 70%, and `cmd_search` — the function that actually
answers a query — was **completely unexercised**. This is the module that once
ran for weeks on an offline hash embedder while the README advertised Ollama
semantic search, and once held 24 of 28 notes with nothing rebuilding it.
Degraded search returns *plausible* results, which is exactly why nobody noticed.

70% -> 99% (the one uncovered line is the `__main__` guard, which three
subprocess tests do exercise; coverage.py cannot see a spawned child without
repo-wide `COVERAGE_PROCESS_START` wiring, which was out of scope). Repo total
89% -> 91%, 637 -> 656 tests.

The tests pin behaviour rather than touching lines: `--offline` must not merely
*prefer* not to call the network but must never attempt it (asserted with a spy
that raises, not an `isinstance` check — the fallback path lands on the same
class, so `isinstance` alone would have passed with the short-circuit deleted);
a malformed Ollama response falls back rather than propagating a `KeyError`;
`--rebuild` wipes the whole table including ghost rows from another model; an
empty index fails loudly instead of reading as "no results".

**One gap survived the agent's own mutation run and was found in review.**
`cosine` returning `1.0` for zero-norm vectors passed all 31 tests. A zero
vector is what a failed or empty embedding leaves behind, and scoring it as a
perfect match would float that garbage to the top of every search — the exact
failure mode this module's history is made of. The `if na and nb` guard is doing
real work, not just dodging a `ZeroDivisionError`, and is now pinned.

Twelve mutations from the agent plus two chosen independently in review, each
proven live before its result was believed.

## [4.5.0] — 2026-08-21

**The weekly catalog refresh now has somewhere to put its output.**

`registry/catalog.json` was tracked, and `refresh-catalog.bat` rewrote it every
Sunday via `catalog.py build`. Nothing committed it. So the file on `master` sat
at its 2026-06-05 state for eleven weeks while `task_doctor` reported the task
healthy each week — and the 2026-08-16 refresh was swept into an auto-stash
during unrelated branch work and came within one `git stash drop` of being lost.

Minor bump: this changes where a file lives, which is a contract.

`catalog.json` is now **gitignored**, with `registry/catalog.seed.json` as the
committed floor. The weekly rewrite no longer touches the repo, and a fresh
clone still has a catalog.

**All three readers resolve live-then-seed**, and that mattered most in the
quietest one: `init_project.py` fell back to `{}` when the catalog was missing,
which sends every catalog agent to `dropped` as unknown. Without a seed, a fresh
clone would have scaffolded projects with their agent roster silently stripped —
the file being absent would have become a *default*, not an edge case.

The resolver is duplicated three ways on purpose — the `suggest-agents` hook must
stay importable from nothing, and `init_project.py` has no shared-module habit —
so a test asserts all three resolve to the same file. Reading the seed prints a
note naming it: a stale answer that looks authoritative is the failure mode this
whole arrangement exists to avoid.

The seed moves only when asked, via `catalog.py build --seed`. A floor that
drifts on its own is not a floor.

Two existing tests failed on the contract change and were corrected rather than
deleted. One of them exposed a test-isolation bug it had been hiding: the
`catalog_file` fixture redirected `CATALOG` but not `CATALOG_SEED`, so any test
without a temp catalog was quietly reading the real `registry/` on disk.

Five mutations, **5 of 5 caught** — seed never consulted, seed winning over a
live catalog, the seed note silenced, `init_project` dropping catalog agents
again, and the hook's resolver diverging from the other two.

## [4.4.3] — 2026-08-21

**The manifest the agent loads at session start had been wrong for 18 days, and
three checks watched it without looking at it.**

`memory/index.json` is the frontmatter manifest `SKILL.md` tells the agent to
load *instead of* reading the whole vault. On 2026-08-21 it was frozen at
2026-08-02: it listed a note that no longer existed, missed three that did, and
five more had changed underneath it. Every check reported the vault healthy.

Three independent reasons nothing noticed:

- `memory-index.py --check` built a fresh index, printed its counts, and
  returned 0 whatever it found. A check that cannot fail is decoration —
  [[decisions/verification-integrity]] says so, and this one had been decoration
  since it was written.
- `memory-search.py status` counts `.md` files against the *semantic* database
  and never opens the manifest. Two different indexes, one of them unwatched.
- The weekly heartbeat refreshed the semantic index only. Nothing rebuilt the
  manifest, so it aged a week with every run that reported `all clear`.

`--check` is now a real gate: it compares the manifest against a fresh walk and
reports **phantom** (listed, file gone), **unlisted** (on disk, never indexed)
and **stale** (indexed, but its frontmatter or links have since changed). Run
against the real vault it found 9 disagreements — five more than a path-set
comparison could see, because content drift leaves the paths intact. The
heartbeat gained the missing pair: refresh the manifest, then gate on it.

**One flag, two questions.** Making `--check` a gate silently repurposed a flag
`selfcheck` already called, and `index.json` is gitignored — so on a fresh clone
there is no manifest, and CI would have gone red on every build. The question
selfcheck was actually asking is *can the indexer parse every note?*, which has
an answer without a manifest. That is now `--dry-run`, and freshness stays with
the heartbeat, which refreshes before it gates.

Four mutations, **4 of 4 caught**. The first initially read as surviving: the
injected `return []` had landed inside `compare`'s docstring rather than its
body, so the code was never mutated. A mutation that does not apply is
indistinguishable from one that is caught, so the harness now proves the mutant
is live — by calling the function and requiring it to lie — before believing a
green suite.

## [4.4.2] — 2026-08-21

**The machine note rewrote itself for reasons that had nothing to do with the
machine.**

`memory/machines/<host>.md` is tracked, and regenerated by both bootstrap and
the weekly heartbeat. It recorded the **current git branch** — so every checkout
changed it, and it turned up as a stray modification in unrelated work. Over the
course of 2026-08-21 it went dirty four separate times and was twice nearly
committed recording a feature branch as this machine's durable state.

Its own docstring already forbade this: *only facts that stay true for weeks…
no per-session state — a note that churns is a note nobody reads.* A branch is
the definition of per-session. It is gone; `path` and `remote` stay, both stable.

**The second source was quieter.** `updated:` was stamped on every run, so
regenerating on an unchanged machine still produced a modified file — a diff
with nothing behind it. `updated` now means *the date these facts last changed*:
the note is compared on everything but that line, and left untouched when the
machine has not moved. A re-run reports `unchanged` instead of `updated`.

The existing idempotence test could not have caught either one — two runs in the
same session, on the same day, produce identical bytes. The churn only appeared
across a checkout or a date boundary, which is what the new tests pin: the date
is rewound to 1999 with the facts left intact, and a re-run must leave it there.

Four mutations, **4 of 4 caught**: restoring the branch line, always rewriting,
never rewriting (not churning by never working), and a comparison that treats
every note as identical.

## [4.4.1] — 2026-08-21

**A deleted agent kept running, under a green report.**

Minutes after 4.4.0 merged — the release that removes `cli-developer` and
`python-pro` — `doctor` printed `[ok] healthy — live config in sync with the
repo` while both agents were still in `~/.claude`, loading into every session.

The sync check only ever ran one way. `drift_in` walks the *repo* and asks "is
each file live, and does it match?", which catches a missing or edited copy and
nothing else. Deleting a file from the repo removes it from that walk entirely,
so the live copy becomes unreachable by the only check that looked — and the
report says healthy because, in the direction it looked, everything was.

A removed agent that keeps running is worse than one that never shipped: it is
advertised at SessionStart, delegated to, and invisible to the tool whose whole
job is to notice.

**Bootstrap now records what it installed** — `~/.claude/.ecosystem-brain-installed.json`,
the live paths written on the last run — and prunes its own leftovers on the
next. `doctor` gained check 3, the reverse direction: a path the manifest says
this repo installed, that the repo no longer produces, and that is still on
disk.

Scoping to the manifest is what makes it safe to gate on. A personal agent under
`~/.claude/agents`, or another plugin's commands, was never in it and can
therefore never be flagged or deleted — verified with both present. Two content
markers were tried first and rejected on evidence: only 1 of 12 agents carries
`{{ECOSYSTEM_ROOT}}`, and neither removed agent was in `registry/installed.json`
by the time it mattered.

Where there is no manifest yet — every install predating this release — check 3
reports `[--] no install manifest yet` rather than `[ok]`. Same rule as 4.3.26:
a check that could not run must not read as one that passed. It self-heals on
the next bootstrap.

Four mutations, **4 of 4 caught**: the orphan scan always returning clean (the
original bug), a missing manifest reporting clean instead of unknown, pruning
ignoring the manifest, and `--dry-run` deleting anyway.

## [4.4.0] — 2026-08-21

The three open decisions, taken. Minor bump: this closes the last items on the
roadmap rather than fixing anything.

**Pruned two agents.** `python-pro` and `cli-developer` were installed
2026-07-17, *after* the oldest surviving transcript (2026-07-08), and never
invoked since — the only two of eight whose evidence window is complete. The
other six predate the window and keep their blind spot, so they stay. Both are
reinstallable from their pinned SHA `947b44c`; the roster is 14 → 12.

**Pinned four project cards to another machine — not archived.** `betting-tracker`,
`betting-stats-analysis`, `my-first-tool` and `viral-videos-sm` describe projects
on another PC's `D:` drive. An earlier draft of this change archived them on the
reasoning that their fate was *unknowable from this machine*. It was knowable —
by asking. That PC is still in use and the projects are live, so `status:
archived` would have recorded a decision nobody took: four working projects
retired because the drive they sit on is not mounted here.

They stay `active`, each carrying a note saying where they live and what is
still missing — the `host:` pin, which needs that machine's `hostname` and is
the one fact this repo cannot derive on its own. `project_doctor` is now
**gating** in the heartbeat regardless: `elsewhere` is a recognised state that
exits 0, so a card on another machine never turns the report red. The reason it
was advisory is gone without archiving anything.

**`scripts/profile_machine.py`** — proposed 2026-07-15 and parked. What made it
worth building is what this session kept running into: the vault is shared
across machines while almost everything in it is machine-specific. A card's
drive letter, an agent's usage count, which scheduled tasks exist — every one of
those readings needs to know which machine is asking, and nothing recorded it.

It writes `memory/machines/<host>.md`: hostname, OS, **which drive roots exist**,
where this clone is, which prerequisites resolve. Deliberately a note rather than
a config — read by a human or an agent reasoning about a discrepancy, never
branched on by code. Written at bootstrap so a fresh clone knows where it is from
the first session, refreshed weekly, and never fatal: a profile is a convenience,
and failing to write one must not fail an install.

On this machine it records `drives present: C:` — which is precisely the fact
that turns "four cards point nowhere" into "four cards describe another PC".

## [4.3.26] — 2026-08-20

**The weekly heartbeat could never report itself green.**

`maintenance.py` gates on `task_doctor.py`, and `task_doctor` inspects every
`EcosystemBrain-*` task — including the one currently executing it. So it always
read the heartbeat's own in-flight run: `LastResult = 0x41301`, "still running",
which counted as a failure. That latched:

    task_doctor fails -> maintenance exits 1 -> next run reads 0x1
    ("the task's own command exited 1") -> task_doctor fails -> ...

Once red, permanently red, regardless of the ecosystem's actual health. A run in
progress is evidence the task *started*; it is not a verdict. It is now judged
OK inside a one-hour grace window — comfortably wider than the 15-minute
execution limit every task is registered with — and flagged `stuck?` beyond it.

**And selfcheck blamed the code for the network.** Both `check_tests` and
`check_lint` shell out through `uv run --with-requirements`, which resolves the
pinned toolchain from PyPI on every invocation. The 2026-08-20 scheduled run had
no DNS, so both exited non-zero with a connect error — and were reported as
`[FAIL] pytest failed` and `[FAIL] ruff found problems` while the suite was in
fact green. A false accusation about the code, from a gate that never ran.

Network failure is now told apart from a finding and reported through a new
`skip()` that deliberately does **not** print `[ok]`: a check that did not
execute must not read as a check that passed. Same reasoning as the `warn` state
in the heartbeat — *advisory means "does not turn the run red", not "did not
happen"*.

Nine tests, all mutation-checked: widening the grace window to infinity,
restoring the original `RUNNING` failure, and making the offline branch swallow
real failures each turn the relevant tests red. **3 of 3 caught.**

Verified through Task Scheduler rather than by hand — the task was triggered and
completed with `LastTaskResult = 0` and a verdict of `all clear`, the first
clean scheduled run since it was registered on 2026-07-15.

## [4.3.25] — 2026-08-03

The mutation harness now covers the gates that **predate** this session — 10
mutations to 17.

Today's tools were mutation-tested as they were written. The older ones never
had been, and they are the ones where a silent hole matters most: the security
scanner, the install gate, the quarantine on a poisoned upstream, drift
detection, the `{{ECOSYSTEM_ROOT}}` expansion, the destructive guard, the agent
frontmatter lint.

Each is now broken in the way that would matter — *nothing ever scores HIGH
again*, *let HIGH-risk content install anyway*, *stop quarantining a poisoned
upstream*, *stop noticing an edited live copy*, *stop expanding the token*,
*stop requiring `-r` so nothing is catastrophic* — and the relevant tests must
fail.

**17 of 17 caught.** The older gates were already honest; this is the first time
that has been demonstrated rather than assumed.

## [4.3.24] — 2026-08-03

**One of today's tests tested nothing, and a mutation run found it.**

`decisions/verification-integrity` says a check that cannot fail is decoration.
That applies to the tests written *for* those checks: a green suite proves
nothing unless it would go red for the defect it guards. ~130 tests were added
today and that had been verified for two of them.

`scripts/mutate_checks.py` reintroduces, one at a time, the exact defect each of
this session's tools exists to prevent — `elsewhere` collapsing back into
`gone`, judging a scheduled task on `State` instead of its last result, letting
first-party agents become removal candidates, skipping the scan on a rollback,
accepting a traversing name, ignoring a red template baseline — and asserts the
relevant tests fail.

Nine of ten were caught. The tenth:
`test_long_text_is_truncated_before_sending` subclassed `OllamaEmbedder` and
**re-implemented the truncation inside the test**, so it passed regardless of
what the source did. It now intercepts the payload the real `embed()` builds,
with a companion asserting a short note is sent whole. Both die when the
truncation is removed.

The harness is deliberately **not** in CI: it rewrites source files, and a
killed run would leave a mutation behind. Run it after adding or changing a
check.

## [4.3.23] — 2026-08-03

**The vault-hygiene agent did not check the thing that rotted.**

`memory-curator` exists for weekly vault hygiene, and its workflow refreshed
`index.json` — the frontmatter manifest — and stopped there. The embedding cache
is a separate index, and it was the one that drifted to 24-of-28 notes on the
offline hash embedder while still answering queries.

Its workflow now refreshes **both** and reports `memory-search status`, with the
distinction spelled out, since conflating the two is what let the drift last.
It also runs `project_doctor`: a vault that tracks projects should notice when a
card names a path that no longer exists — and it is told to report, never
repair, because only the user knows whether a project was deleted, moved, or
lives on another machine.

This closes the last category of the sweep. Every doc, command and agent
definition that describes something changed this session has now been checked
against the code rather than re-read.

## [4.3.22] — 2026-08-03

**Six commands documented an instruction that would break the install.**

`install`, `catalog`, `search`, `init`, `update` and `new-agent` all told the
reader to sync by copying repo files over `~/.claude`:

    cp {{ECOSYSTEM_ROOT}}/agents/*.md ~/.claude/agents/

Following that overwrites every working command with a version containing the
**literal** `{{ECOSYSTEM_ROOT}}` token — `bootstrap` is what expands it — and
cannot copy skills at all, since `skills/<name>/SKILL.md` does not match a flat
`*.md` glob. 14 of 17 commands and one agent carry the token.

It was also redundant: `install-agent.py` already writes both the repo copy and
the `~/.claude` one. So the instruction had no upside and a large downside.

All six now point at `scripts/bootstrap.py`, which is the only thing that
performs the rewrite. `selfcheck` check 6 gained the rule, so it cannot return:
no installable file may contain a `cp … ~/.claude` instruction. Tests cover that
it fires, that the bootstrap wording does not trip it, and that prose explaining
why *not* to copy is left alone.

`commands/agents.md` also learned to report `agent_usage`'s evidence window
alongside any "never invoked" count.

## [4.3.21] — 2026-08-03

Four more documents caught up with what the code does. A systematic sweep this
time — every doc that describes something changed today, checked against the
code rather than re-read.

- `INSTALL.md` described the weekly heartbeat as three checks (`doctor`,
  `selfcheck`, `update --check`). It runs **eight**. It also now records why the
  registrar disables PowerShell's battery guards, since that is the setting that
  killed every scheduled run for three weeks.
- `skills/memory/SKILL.md` and `memory/README.md` gained `memory-search status`,
  with the reason to reach for it: the offline embedder is a bag of words and a
  search backed by it still returns related-*looking* notes, which is how this
  vault spent weeks answering from a hash index nobody knew was there.
- `docs/OBSIDIAN.md` said "embeds notes (Ollama)". It now names the model and
  dimensionality, and points at the check that proves the claim.

## [4.3.20] — 2026-08-03

The README, checked against reality rather than re-read. Fifteen versions
shipped in a day and its command table had gone stale again: `project-doctor`
and `agent-usage` were missing, and `health-check` was still described as
"secrets hygiene + tool versions + active projects" when it now composes six
checks.

The scripts list gained the four doctors, named by *what each one judges* —
`doctor` the install, `project_doctor` the projects it built, `task_doctor`
whether the scheduled tasks actually complete, `agent_usage` which agents are
ever invoked — plus `verify_templates` and the shared `github_util` helper.

Checked by comparing the README's claims against the filesystem rather than by
reading it. Two of the three probes were wrong on the first pass — one regex
demanded a backtick the table does not have, another missed the `:fix-bug`
shorthand and reported a gap that was not there — which is the argument for
checking the artefact twice, made at my own expense.

## [4.3.19] — 2026-08-02

**`/ecosystem-brain:health-check` had become the least informed thing here.**

Five diagnostic tools were added this session and the command that claims to be
*the* health report knew about none of them. Worse, its "Projects" step listed
them from `memory/index.json` — the frontmatter manifest — which reports what a
card *claims*, not whether the project is still there. It would have reported
all four cards pointing at an absent drive as `active`, cheerfully.

It now composes the checks that exist: `secrets-doctor`, `doctor`,
`project_doctor`, `task_doctor`, `memory-search status`, `agent_usage`, plus
tools and MCP. Each entry says *why* the tool is the right source — in three
cases because reading the file directly gave the wrong answer, which is how the
old step 5 was written.

`commands/doctor.md` gains a "siblings" section drawing the line the split
depends on: `doctor` checks the **install**, the others check what the ecosystem
**produced**. A green `doctor` says the wiring is right and nothing more.

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
