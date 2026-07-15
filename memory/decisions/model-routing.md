---
type: decision
status: confirmed
date: 2026-06-11
updated: 2026-07-15
tags: [models, agents, tokens, cost, fable, sonnet]
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
| Spec-driven code-gen (tests from observed behavior, scripts to convention) | `sonnet` | test-writer, script-smith |
| Judgment / diagnosis (verdicts, root-causing) | `inherit` | security-auditor, bug-fixer |

- **`inherit` rides the session model** — on a Fable 5 session, judgment agents
  get Fable 5 automatically; on a cheap session they stay cheap. That IS the
  auto-switching: pick the session model for the work, and routing follows.
- **`sonnet` as a quality floor (rev. 2026-07-15)**: with Sonnet 5 delivering
  frontier-level coding at scale, agents whose output is *committed code from a
  clear spec* pin `sonnet` — constant quality regardless of session tier, and no
  frontier tokens burned on bounded work. Third-party dev agents (python-pro,
  data-engineer, …) already ship `model: sonnet` and float with the alias.
- **security-auditor and bug-fixer deliberately stay `inherit`**: a missed
  verdict or misdiagnosis costs more than the tokens saved.
- **Never hard-pin `fable`/`opus` in frontmatter without a reason** — it defeats
  cheap sessions and goes stale as models advance.

## Portability rule (all work environments)
Frontmatter carries **tier aliases only** (`haiku`/`sonnet`/`opus`/`inherit`),
never full model IDs — aliases float to the latest model of each tier, survive
model generations, and the same repo bootstraps identically on every machine.
Audit 2026-07-15: zero full model IDs anywhere in scripts/templates/agents.
`model:` frontmatter is Claude Code-specific; other tools (Gemini CLI, Codex,
Cursor) ignore it and read AGENTS.md, so nothing breaks cross-tool.

## Override order (how to switch per-case)
The harness resolves a subagent's model as:
`CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation `model` param → frontmatter →
session model. So a one-off "run the curator on the big model" is a per-invocation
override, not a file edit.

## Current model landscape (2026-07)
Claude 5 family: **Fable 5** (`claude-fable-5`, frontier, Mythos-class tier) and
**Sonnet 5** (2026-06-30 — frontier coding/agents at scale; the `sonnet` alias
now resolves here). Claude 4.x line: Opus 4.8 (fast mode via `/fast`), Haiku 4.5.
The recruiter (`new_agent.py`) accepts `fable` as an alias; aliases in
frontmatter track the latest model of each tier, so prefer aliases over full IDs.

See [[claude-best-practices]] (cost: route to cheaper models) and `docs/TOKENS.md`.
