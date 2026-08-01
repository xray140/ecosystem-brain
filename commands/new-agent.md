---
description: Recruit a new first-party agent — scaffolded to the ecosystem standard, security-scanned, and registered.
argument-hint: [what the agent should do]
---
Create a new first-party agent to standard. Idea (if given): `$ARGUMENTS`.

Keep agents focused and least-privilege (see [[claude-best-practices]]).

## Step 1 — Interview (AskUserQuestion, one call)
- **Name** (kebab-case) and one-line **purpose**.
- **Does it act or just read?** read-only (Read/Grep/Glob) | edits files (+Edit/Write) | runs commands (+Bash).
- Confirm the **trigger** — the description must say *when to delegate* ("Use proactively …").

## Step 2 — Map to flags
- read-only → `--tools Read,Grep,Glob`
- edits → add `Edit,Write`; runs commands → add `Bash`
- Grant the **fewest** tools the job needs. `--model inherit` unless there's a clear reason.
- Draft 2–4 `--step` actions (the When-invoked workflow) and a `--returns` line.

## Step 3 — Preview (no writes)
```
uv run python {{ECOSYSTEM_ROOT}}/scripts/new_agent.py \
  --name <name> --description "<purpose>. Use proactively when <trigger>." \
  --role "<one-line role>" --tools <T1,T2,...> \
  --step "<step 1>" --step "<step 2>" --returns "<what it returns>"
```
Show the composed agent + self-scan. Refine wording if needed.

## Step 4 — Register (after confirmation)
Append `--register` to the same command. It scan-gates (`scan_agent.py`) and
installs via `install-agent.py` (HIGH-risk content is refused + quarantined).
Then sync to the global dir:
```
cp {{ECOSYSTEM_ROOT}}/agents/<name>.md ~/.claude/agents/
```
Report the registered agent and remind the user to flesh out its body if the
workflow steps are still placeholders.
