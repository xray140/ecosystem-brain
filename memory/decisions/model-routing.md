---
type: decision
status: confirmed
date: 2026-06-11
tags: [models, agents, tokens, cost, fable]
---
# Model routing: route agents by task shape, not by default

## Problem
All first-party agents used `model: inherit`, so every delegation — including
mechanical checklist work — ran on the session's (frontier) model. That wastes
the costliest tier on pattern-matching, and there was no recorded policy for
when a cheaper tier is appropriate.

## Decision
Route by **task shape**, set in each agent's `model:` frontmatter:

| Shape | Tier | Agents |
|-------|------|--------|
| Checklist / mechanical (explicit rules, bounded output) | `haiku` | convention-keeper, memory-curator |
| Judgment / code-gen (verdicts, isolation, test design, scripts) | `inherit` | security-auditor, bug-fixer, test-writer, script-smith |

- **`inherit` rides the session model** — on a Fable 5 session, judgment agents
  get Fable 5 automatically; on a cheap session they stay cheap. That IS the
  auto-switching: pick the session model for the work, and routing follows.
- **security-auditor deliberately stays `inherit`**: a missed verdict costs more
  than the tokens saved.
- **Never hard-pin `fable`/`opus` in frontmatter without a reason** — it defeats
  cheap sessions and goes stale as models advance.

## Override order (how to switch per-case)
The harness resolves a subagent's model as:
`CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation `model` param → frontmatter →
session model. So a one-off "run the curator on the big model" is a per-invocation
override, not a file edit.

## Current model landscape (2026-06)
Frontier: **Fable 5** (`claude-fable-5`). Claude 4.x line: Opus 4.8, Sonnet 4.6,
Haiku 4.5. The recruiter (`new_agent.py`) accepts `fable` as an alias; aliases in
frontmatter track the latest model of each tier, so prefer aliases over full IDs.

See [[claude-best-practices]] (cost: route to cheaper models) and `docs/TOKENS.md`.
