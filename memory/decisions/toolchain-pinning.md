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

## Consequences

- Bumping a tool is a deliberate commit: change the pin, run `selfcheck.py`,
  fix the fallout in the same change. The upgrade and its cost stay together.
- A green `selfcheck` is now a real predictor of a green CI. Before, it was a
  weaker claim than it appeared — see the Verification rule in `AGENTS.md`.
- Deliberate exceptions live as `# noqa` with a reason, and `RUF100` fails the
  build when one goes stale, so the exception list cannot rot.

Related: [[agent-pinning]] · [[claude-best-practices]] ·
[[text-file-write-conventions]]
