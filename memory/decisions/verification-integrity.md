---
type: decision
status: confirmed
date: 2026-08-02
tags: [verification, gates, observability, conventions]
---
# A gate nobody reads is not a gate

## The evidence

One audit (2026-07-31 → 08-02, v4.3.5 → v4.3.16) found the **same defect eight
times** wearing different clothes. In every case the information existed and
nothing read it back:

| what was claimed | what was true |
|---|---|
| "CI green on GitHub" | red on **every push for weeks** — 57 ruff findings, unpinned toolchain |
| `selfcheck` is the local gate | it ran pytest but **never ran ruff**, so it could not see the red |
| commands point at the repo | 58 references to a drive that no longer existed, invisible because `bootstrap` rewrote them on the way out |
| `update --check` reports status | `[!]` on 8 healthy items every run — a column that cries wolf stops being read |
| heartbeat reports honestly | a *failed* advisory check was filed under a section titled `— ok` |
| projects are registered in the vault | nothing had **ever** read those cards back; 4 pointed nowhere |
| weekly tasks are live (`State: Ready`) | **not one had ever completed a scheduled run**; catalog 40 days stale |
| "Ollama semantic search" | 24/28 notes on the offline **bag-of-words** fallback |

## The rule

**A check must be executed by the thing that claims to be checking, and its
output must be read by something that can act.** Three failure modes, all seen
here:

1. **The gate is not run.** `selfcheck` did not run ruff. Fix: the local gate
   runs the *same invocation* as CI, and a test asserts the two configs cannot
   diverge.
2. **The gate runs but nothing reads its result.** Scheduled tasks reported
   `Ready` while every run died; project cards were written and never re-read.
   Fix: judge on the **last result and its age**, never on state — and give
   every produced artefact a reader.
3. **The gate reports, but the report lies by omission.** `ok` for a failed
   advisory check; `[!]` for eight healthy items. Fix: distinct states for
   distinct outcomes, and reserve the attention marker for things that need
   attention.

## The tell

**Degraded output is plausible output.** Semantic search on a hash fallback
still returns related-looking notes. A stale catalog still lists agents. That is
why these survive: nothing looks broken. So verification cannot mean "it ran and
did not crash" — it has to mean **check the artefact**.

Twice during this audit a fix looked right and was not: the battery-guard change
alone left the heartbeat still failing, and a test comparing two code paths
passed against a live bug because both were wrong in the same way on this
platform. Both were caught by looking at the produced thing rather than the exit
code.

## Consequences

- `selfcheck` = 9 checks, including ruff and a hardcoded-path check, using the
  pinned toolchain CI uses. See [[toolchain-pinning]].
- Every artefact the ecosystem produces now has a reader: `project_doctor` for
  vault cards, `task_doctor` for the scheduler, `memory-search status` for the
  embedding index, `agent_usage` for the installed roster, and — since
  2026-09-03, four releases after this note claimed the set was complete —
  `selfcheck` check 9 for `roadmap.md`, the note a fresh session opens first.
- The heartbeat is three-state (`ok` / `warn` / `FAIL`); *advisory* means "does
  not turn the run red", never "did not happen".
- Tests assert gates go **red** when their subject breaks. A check that cannot
  fail is decoration — see `tests/test_selfcheck_checks.py`.

Related: [[toolchain-pinning]] · [[agent-pinning]] · [[claude-best-practices]] ·
[[encoding-discipline]] — the same rule pointed at what a gate *writes*
