---
type: decision
status: confirmed
date: 2026-09-03
tags: [encoding, windows, verification, conventions, artefacts]
---
# Every process boundary names UTF-8, in both directions

## The evidence

The weekly heartbeat wrote eight consecutive corrupted reports and reported
`all clear` every time.

`maintenance.run()` captured its children with `text=True` and no `encoding=`.
`text=True` decodes with the **locale** encoding, which is cp1252 on Verdun10,
while every child writes UTF-8 — so each em dash a check printed (bytes
`E2 80 94`) landed in `memory/maintenance/<date>.md` as three cp1252
characters, and `update --check` filed its tick as `âœ“`. The damage grew with
the report: 1 occurrence on 2026-07-15, 15 by 2026-08-31.

Nothing caught it, and nothing could have. Every exit code was 0. Doctor,
selfcheck, project-doctor and task-doctor all passed. **The run was fine and
only the artefact was degraded** — see [[decisions/verification-integrity]],
which names exactly this and still did not prevent it, because its rule was
about gates being read and this was about what a gate *writes*.

Fixing the capture side surfaced the other half within the hour. With the
parent finally decoding UTF-8, `memory-search.py status` still arrived as
`memory search index � vault has 51 note(s)`: a child whose stdout is a pipe
**encodes** with the locale codepage unless it says otherwise, so its em dash
left as the single byte `0x97`. Same corruption, opposite direction.

And `selfcheck.py` was getting it right by accident — it imports `scan_agent`,
which reconfigures stdout at import time, and reconfiguring is process-global.
An import moved or dropped would have taken the encoding with it.

## The rule

**A process boundary has two ends, and both must name UTF-8.**

- **Reading**: every text-mode `subprocess` call names `encoding="utf-8"` and an
  explicit `errors=`. Not belt-and-braces — with strict UTF-8 and no `errors=`,
  `mutate_checks.py` died in a subprocess reader *thread* on a cp1252 em dash
  from a French-locale child, caught all 20 mutants, and exited 1 with the
  output truncated and nothing saying why. `git`, `gh`, `npm` and cmd.exe all
  speak the console codepage on occasion; one replacement character in one line
  is the cheap outcome.
- **Writing**: every entry point reconfigures `sys.stdout` to UTF-8 explicitly,
  never by inheriting it from an import.

Both halves are enforced by `tests/test_subprocess_encoding.py`, which walks the
sources with `ast` rather than trusting a convention — and each half asserts its
own walk still finds call sites, because a source scan that matches nothing
passes for free.

## Why a rule and not six patched lines

The six sites were the ones that existed on 2026-09-03. The defect is a
*default*: `text=True` is the obvious thing to write, it is correct on the
Linux CI runner, and it is wrong on the platform this ecosystem runs on. A
convention in prose loses to a default that works in the place people test.

This is the [[decisions/verification-integrity]] rule pointed at output:
**check the artefact, not the exit code.** A green run says the process
finished, not that what it wrote is readable.

See also [[decisions/windows-python-invocation]] — the same platform, the same
shape of surprise.
