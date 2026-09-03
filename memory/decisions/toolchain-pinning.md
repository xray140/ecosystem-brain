---
type: decision
status: confirmed
date: 2026-07-31
tags: [ci, tooling, supply-chain, verification]
---
# Pin the dev toolchain, and pin the rule set too

## Context

CI ran `uv run --with ruff --no-project ruff check scripts tests`. `--with ruff`
has no version, so every run resolved the newest release. Ruff 0.16 widened its
*default* rule set, and the lint job started reporting **44 findings that no
commit introduced**. The repo's roadmap still described CI as green.

The local gate could not catch it: `selfcheck.py` ran pytest but never ran ruff.
A change could pass every local check and fail remotely — the two gates were
measuring different things.

## Decision

Two pins, because there are two moving parts.

1. **Version** — `requirements-dev.txt` holds exact `==` pins for ruff and
   pytest. CI and `selfcheck` both install from it via
   `uv run --with-requirements requirements-dev.txt --no-project`.
2. **Rule set** — `ruff.toml` sets `select` explicitly. A linter's defaults are
   not a stable contract; the rules this repo is held to should be a decision
   someone made, visible in a file.

And one structural rule: **`selfcheck` runs exactly what CI runs.** Lint is
check 6 of 7, same invocation, same paths, same pinned binary. Tests in
`tests/test_selfcheck.py` assert the two cannot drift apart — they parse the
CI workflow and compare it against `selfcheck.LINT_PATHS`.

## Why this shape

This is the same reasoning as [[agent-pinning]], applied inward. That note pins
third-party *agents* to a commit SHA because a mutable `main` can swap vetted
content underneath us. An unpinned `ruff` is the identical failure mode with a
friendlier name: an external artifact, resolved fresh, changing what "passing"
means without anyone deciding it should.

The ecosystem was pinning what it downloaded and floating what it ran.

## The same lesson, unlearned in the other language (2026-09-03)

Two commits that touched nothing but memory notes turned CI red on both
platforms. `verify_templates.py` failed with `npm install` crashing inside
arborist — *Cannot read properties of null (reading 'edgesOut')* — while the
same template scaffolded green locally. Nothing in the repo had changed. Two
things outside it had, and both were unpinned:

1. `templates/typescript-project/package.json` carried five floating `^` ranges
   and shipped no lockfile, so `npm install` re-resolved to whatever was newest
   that morning.
2. **CI installed no node at all.** The typescript baseline ran on whatever the
   runner image happened to ship, and runner images are replaced without notice.

Fixed the same way as ruff: exact `==`-equivalent pins in the template, and
`actions/setup-node` pinned to node **24.20.0** — the exact patch, not the
major, because npm ships *with* node and pinning `24` would leave the thing that
actually broke free to drift. Enforced by `tests/test_selfcheck.py`: template
dependency specs must be exact, `node-version` must be a full patch version, and
every action must be a 40-char commit SHA.

This note claimed in 2026-07-31 that the ecosystem "was pinning what it
downloaded and floating what it ran". That was true of Python and stayed true of
TypeScript for five more weeks. The pin belongs at every toolchain the repo has,
not the one that broke first.

## Consequences

- Bumping a tool is a deliberate commit: change the pin, run `selfcheck.py`,
  fix the fallout in the same change. The upgrade and its cost stay together.
- A green `selfcheck` is now a real predictor of a green CI. Before, it was a
  weaker claim than it appeared — see the Verification rule in `AGENTS.md`.
- Deliberate exceptions live as `# noqa` with a reason, and `RUF100` fails the
  build when one goes stale, so the exception list cannot rot.

Related: [[agent-pinning]] · [[claude-best-practices]] ·
[[text-file-write-conventions]] · [[encoding-discipline]]
