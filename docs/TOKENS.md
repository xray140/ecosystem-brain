# Token & context discipline

LLM performance degrades as the context window fills — context is the scarcest
resource, so spend it deliberately. These habits keep an ecosystem-brain session
lean. Most apply to any AGENTS.md-aware tool, not just Claude Code.

## Keep the always-loaded context small
- **Instruction files load every turn.** `CLAUDE.md` / `AGENTS.md` must stay
  short — each line should change behavior or be cut. Bloat makes the model
  *ignore* the real rules. (Grounding: `memory/decisions/claude-best-practices.md`.)
- **Lean `.mcp.json`.** Every connected MCP server's tool schemas cost context.
  Keep the repo's `.mcp.json` to what the project needs (filesystem / git / github)
  and let the harness defer the rest behind ToolSearch instead of preloading them.
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

## Model tiers (cost, not just tokens)
- First-party agents use `model: inherit`, so they ride your session's model
  choice rather than hard-coding an expensive tier.
- Run a cheap mechanical pass (or a subagent) on a smaller/faster model; reserve
  the largest model for design and debugging judgment.
