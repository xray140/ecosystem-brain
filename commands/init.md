---
description: Guided project creation — a sharp 3-4 question interview produces a fully-configured project (tailored AGENTS.md + auto-selected, security-scanned agents).
argument-hint: [project-name]
---
Create a new, fully-configured project through a short, sharp interview.
Project name (if given): `$ARGUMENTS` — otherwise ask for it as part of step 1.

Run this flow exactly. Keep it tight — these questions are the whole UX.

## Step 1 — The interview (use the AskUserQuestion tool)

Ask Q1-Q3 in a SINGLE AskUserQuestion call (three questions at once). Then ask
Q4 only if Q1 is "Web app" or "API service".

- **Q1 "What are you building?"** (header: Build) — single select:
  Web app | API service | CLI tool | Library / SDK
  (Inference: if the project is clearly a **data/ETL/ML pipeline**, use
  `--build data-pipeline`; if it's an **MCP server**, use `--build mcp-server`
  — these aren't buttons, infer from the name/description; ask a one-line
  clarifier only if genuinely ambiguous.)
- **Q2 "How far will it go?"** (header: Rigor) — single select:
  Prototype | Product | Production
- **Q3 "What does it handle?"** (header: Handles) — **multiSelect: true**:
  API keys | User data / PII | Money | Nothing sensitive
- **Q4 "Frontend/stack?"** (header: Stack) — single select, ONLY if web/api:
  React / Next.js | Vue | Svelte | Decide for me

If no project name was provided in `$ARGUMENTS`, also ask for it (short kebab-case).

**Follow-ups (only when relevant):**
- If Q3 includes **API keys**, ask *which* services (free text, e.g. "YouTube,
  TikTok, Stripe"). These become named placeholders in the project's
  `.env.example` via `--api-keys` — names only, never values.
- Ask **"Create a private GitHub repo and push?"** (Yes/No). Yes → add `--github`
  (it only pushes if the green-baseline check passes).

## Step 2 — Map answers to flags
- Build: Web app→`web`, API service→`api`, CLI tool→`cli`, Library→`library`
- Rigor: Prototype→`prototype`, Product→`product`, Production→`production`
- Handles (comma-join the selected): API keys→`api-keys`, User data/PII→`pii`,
  Money→`money`, Nothing→`none`
- Stack: React/Next→`react`, Vue→`vue`, Svelte→`svelte`, Decide for me→`decide`
  (omit `--stack` entirely for cli/library)
- API services → `--api-keys youtube,tiktok,...` (the names from the follow-up)
- GitHub yes → `--github`

## Step 3 — Show the composed plan (no writes yet)
Run:
```
uv run python /d/claude-projects/ecosystem-brain/scripts/init_project.py --plan \
  --build <b> --rigor <r> --touches <t1,t2> [--stack <s>] --name <name>
```
Show the user the printed summary (template, stack, agent list, AGENTS.md preview).

## Step 4 — Confirm once (AskUserQuestion)
Ask **"Apply this configuration?"** (header: Apply): Apply | Adjust agents | Cancel
- **Apply** → go to Step 5.
- **Adjust agents** → ask what to add/remove, note it, then proceed to Step 5
  (you can install/remove specific agents with install-agent.py afterward).
- **Cancel** → stop; nothing was written.

## Step 5 — Apply
```
uv run python /d/claude-projects/ecosystem-brain/scripts/init_project.py --apply \
  --build <b> --rigor <r> --touches <t1,t2> [--stack <s>] --name <name> \
  [--api-keys <k1,k2>] [--github]
```
Apply does it all: scaffold + git, tailored AGENTS.md, named API keys in
`.env.example`, scanned+pinned agents, a memory card linked into `projects-moc`,
**a green-baseline check** (`uv sync`/`npm install` + tests — it must pass), and
an optional GitHub push. A red baseline returns non-zero — surface it, don't
gloss over it.

Then sync newly-installed agents to the global dir:
```
cp /d/claude-projects/ecosystem-brain/agents/*.md ~/.claude/agents/
```
Report: the created path, the green-baseline result, the repo URL (if `--github`),
and any agent that was BLOCKED by the security scan.
