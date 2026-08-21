---
type: decision
status: confirmed
date: 2026-08-21
tags: [supply-chain, install, idempotence, drift]
---
# Bootstrap records what it installed — not inferred from markers

## Problem

Before v4.4.1, there was no record of what `bootstrap.py` had installed to `~/.claude`. When an agent was later removed from the repo, there was no way to know it had ever been installed there — so `doctor` could not detect it or warn about it.

The original approach tried two content markers, both rejected:

1. **`{{ECOSYSTEM_ROOT}}` token** — appeared in only 1 of 12 agents. Not a reliable way to mark ecosystem-installed content.
2. **`registry/installed.json`** — the registry entry would be deleted in the same commit that removed the agent file, so the entry vanished before it could be used to trigger cleanup.

A removed agent that keeps running is worse than one that never shipped: it is advertised at SessionStart, delegated to, and invisible to the tool whose whole job is to notice.

## Decision

**Bootstrap records what it installed** to `~/.claude/.ecosystem-brain-installed.json`, the live paths written on the last run. On the next run, it prunes its own leftovers by comparing the new install plan against this manifest.

- `doctor` gained check 3: a path the manifest says this repo installed, that the repo no longer produces, and that is still on disk → report as orphaned, never repair.
- Scoping to the manifest is what makes the check safe to gate on. A personal agent under `~/.claude/agents` or another plugin's commands was never recorded and can therefore never be flagged or deleted.

## State before manifest

Where there is no manifest yet — every install predating this release — check 3 reports `[--] no install manifest yet` rather than `[ok]`. Same rule as the skip state: **a check that could not run must not read as one that passed.** It self-heals on the next bootstrap.

## Shape

- `~/.claude/.ecosystem-brain-installed.json` is written by `bootstrap.py` after each install
- `doctor` reads it to detect orphaned installed content
- The check exits `[--]` (did not run) rather than `[ok]` (passed) if the manifest does not exist yet
- Tests verify: orphan detection with a manifest present; `[--] unknown` rather than a pass when there is none (`test_no_manifest_reports_unknown_rather_than_clean`); and no false positives for a personal agent or another plugin's commands

## Related

- [[decisions/verification-integrity]] — a check that did not run must be visibly different from a check that passed
- [[decisions/agent-pinning]] — agents are pinned at install; the manifest records which ones were installed
