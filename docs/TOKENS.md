# Token & context discipline

LLM performance degrades as the context window fills — context is the scarcest
resource, so spend it deliberately. These habits keep an ecosystem-brain session
lean. Most apply to any AGENTS.md-aware tool, not just Claude Code.

## Keep the always-loaded context small
- **Instruction files load every turn.** `CLAUDE.md` / `AGENTS.md` must stay
  short — each line should change behavior or be cut. Bloat makes the model
  *ignore* the real rules. (Grounding: `memory/decisions/claude-best-practices.md`.)
- **Lean `.mcp.json`.** Every connected MCP server's tool schemas cost context.
  Declare only servers the project genuinely needs, and let the harness defer the
  rest behind ToolSearch instead of preloading them. This repo's own `.mcp.json`
  is **empty**: the three servers it once declared were dead weight — filesystem
  pointed at a path that no longer existed, and git/github duplicated tools the
  harness already provides natively (v4.3.3). Duplicating a native tool is the
  most common way an `.mcp.json` costs context for nothing.
- **Skills/commands load on demand** — prefer them over stuffing sometimes-needed
  knowledge into the always-on instruction files.

## Push high-volume work off the main thread
- **Delegate to a subagent** for anything that reads many files or emits verbose
  output — test runs, log/diff scans, codebase exploration. The volume stays in
  the subagent's context; only the summary returns. That is the squad's whole point.
- **Scope investigations.** "Investigate X" with no bound reads hundreds of files.
  Name the files/dirs, or hand it to the read-only Explore agent.

## Reset between tasks
- **`/clear`** between unrelated tasks — a long session full of stale context is
  slower and more error-prone than a fresh one with a sharper prompt.
- **`/btw`** for a quick side question you don't want to keep in history.
- Corrected the model twice on the same point? `/clear` and restate — accumulated
  failed attempts pollute the context more than they help.

## Model routing (cost, not just tokens)
Agents are routed by **task shape** (policy: `memory/decisions/model-routing.md`):
- **Checklist / mechanical** (convention-keeper, memory-curator) → `model: haiku`
  — explicit rules, bounded output; the fast tier is enough and ~10× cheaper.
- **Spec-driven code-gen** (test-writer, script-smith) → `model: sonnet` — since
  Sonnet 5 (2026-06) the sonnet tier delivers frontier-level coding at scale, so
  committed code gets a constant quality floor without spending the session's
  frontier tokens.
- **Judgment / diagnosis** (security-auditor, bug-fixer) → `model: inherit` —
  they ride the session model, so a Fable 5 session gives them Fable 5; a missed
  verdict or misdiagnosis costs more than the tokens saved.
- Per-case override without editing files: the harness honors a per-invocation
  model param (and `CLAUDE_CODE_SUBAGENT_MODEL`) over frontmatter.
- Don't hard-pin the frontier tier in frontmatter — it defeats cheap sessions
  and goes stale as models advance.
