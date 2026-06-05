---
type: decision
status: confirmed
date: 2026-06-05
tags: [claude-code, conventions, agents, claude-md]
---
# Conventions grounded in Anthropic's official best practices

Our CLAUDE.md, template AGENTS.md, and first-party agent definitions are
deliberately aligned with Anthropic's published guidance. Source of truth:
- Best practices: https://code.claude.com/docs/en/best-practices
- Subagents: https://code.claude.com/docs/en/sub-agents
- CLAUDE.md / memory: https://code.claude.com/docs/en/memory

Recheck these pages before re-litigating a convention — don't argue from memory.

## Principles we adopt

**CLAUDE.md = short and load-bearing.** It loads every session, so every line
must earn its place: "would removing this make Claude make a mistake? If not,
cut it." Include non-guessable bash commands, project-specific style/arch
decisions, env quirks, gotchas. Exclude anything inferable from code, standard
conventions, frequently-changing info, tutorials. A bloated CLAUDE.md makes
Claude ignore the real rules. Sometimes-relevant knowledge → a skill, not here.

**Verification over assertion.** Pair every change with a check that returns
pass/fail (tests, build, `scripts/selfcheck.py`) and show the command + output.
"Looks done" is not done. This is Anthropic's top principle and the reason
`selfcheck.py` + the gitleaks/ruff hooks exist.

**Plan mode is nuanced, not absolute.** Explore → plan → implement. Plan when a
change is multi-file, the approach is uncertain, or the code is unfamiliar — but
if you can describe the diff in one sentence, skip the plan and just do it.

**Subagents: focused, isolated, least-privilege.** One job each; their own
context window (keeps verbose output out of the main thread); an explicit
allowlisted `tools:` set and `model:` field; a `description` that says when to
delegate ("use proactively…"). See our four first-party agents for the shape.

## How this maps to the repo
| Artifact | Principle applied |
|----------|-------------------|
| `CLAUDE.md` | concise; Planning + Verification + Delegation rules |
| `templates/*/AGENTS.md` | plan-mode nuance + "show the check output" workflow line |
| `agents/*.md` (local) | focused single task, least-privilege `tools`, explicit `model: inherit` |

See [[hook-format]] for the enforcement layer (hooks beat prose for must-happen rules).
