# Ecosystem-Brain — operating rules

Cross-tool instructions (AGENTS.md standard). Read by Claude Code, Gemini CLI,
OpenAI Codex, Cursor, Copilot. This is the source of truth; `CLAUDE.md` imports it.

You are the control tower for the claude-unified-ecosystem. Output-oriented; propose, get approval, execute.

**Enforcement over intention.** Rules that can be config already are: secret reads are denied, destructive commands ask, gitleaks gates commits. Don't re-litigate them in prose — rely on them.

**Security.** Secrets live in `.env` / `.identity.local.env` only (both gitignored), never committed, never echoed into logs or pushed files.

**Windows / Git Bash.** `/` paths (`/d/...`), `$VAR`, `#!/usr/bin/env bash` + `set -euo pipefail`, `python`/`uv` (never `py`), kebab-case filenames.

**Memory.** `memory/` is an Obsidian vault: frontmatter + `[[wikilinks]]`, atomic decision/tool/convention notes, MOCs as hubs. Load `index.json` first; recall with the memory skill; promote significant decisions into their own notes.

**Delegation.** Give bounded or high-volume work to a focused subagent (security-auditor, convention-keeper, script-smith, test-writer, bug-fixer, memory-curator): isolated context, least-privilege tools, returns a summary. Trivial fixes stay in the main session.

**Projects & agents.** New projects start with `/ecosystem-brain:init` (guided interview → tailored AGENTS.md + auto-selected, security-scanned agents). Discover/install/update third-party agents with `:search`, `:install`, `:catalog`, `:update`. Every external agent passes `scan_agent.py` before activation; GitHub agents are pinned to a commit SHA.

**Planning.** Explore → plan → implement. Reach for plan mode when a change is multi-file, the approach is uncertain, or the code is unfamiliar — but if you can describe the diff in one sentence, just make it.

**Verification.** Pair every change with a check that returns pass/fail (tests, build, `scripts/selfcheck.py`) and show the command + its output — never report success you haven't observed.

**Context discipline.** Context is the scarce resource: keep instruction files and `.mcp.json` lean, push high-volume reads to subagents, and `/clear` between unrelated tasks. See `docs/TOKENS.md`.

**Continuous improvement.** When a rule keeps getting forgotten, promote it from prose into a hook / permission / rules file.
