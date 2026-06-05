---
type: decision
status: confirmed
date: 2026-06-06
tags: [security, supply-chain, agents, github]
---
# Agent supply-chain: pin to commit SHA, not a mutable branch

## Problem
Installing an agent from `…/main/…` fetches whatever the branch tip points at
*now*. A branch is mutable: it can be force-pushed or advanced after you vetted
the content. Recording only a content hash detects drift but can't reproduce the
exact version you trusted, and there's no record of *which* commit was vetted.

## Decision
Pin every GitHub-sourced agent to the **commit SHA** the content was fetched at.

- **Install** (`install-agent.py --repo/--path`): resolve the branch tip to a SHA
  via `gh api repos/{repo}/commits/{ref}`, then fetch the file at
  `raw.githubusercontent.com/{repo}/{SHA}/{path}` (immutable). Store `ref` (branch)
  + `commit` (SHA) in `installed.json`.
- **Update** (`update-agents.py`): re-resolve the tip, fetch at the new SHA,
  compare content hash. Identical → advance the pin (provenance; also migrates
  legacy unpinned entries). Changed → show `oldsha -> newsha` + a GitHub compare
  URL, re-scan, and quarantine on HIGH before advancing.

## Why `gh` for SHA resolution
Consistent with `catalog.py`; reuses the user's `gh auth login` token, so **no
secret handling lives in the scripts**. Raw content still comes over plain https
(public repos, unauthenticated). If `gh` is unavailable, both paths fall back to
the mutable `ref` — degraded but functional.

## Shape
- Shared helpers in `scripts/github_util.py` (`resolve_commit`, `parse_source`,
  `raw_url`, `compare_url`, `md5`, `fetch_url`) — DRYs install + update; pure
  helpers are unit-tested, the update decision logic is tested monkeypatched.
- `installed.json` github entries gain optional `ref` + `commit`. Local agents
  and the `--url`/`--file` install paths are unaffected (best-effort, no pin).

See [[claude-best-practices]] for the agent conventions, [[hook-format]] for the
enforcement layer.
