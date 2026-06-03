# Ecosystem-Brain — operating rules

You are the control tower for the claude-unified-ecosystem. Output-oriented; propose, get approval, execute.

**Enforcement over intention.** Rules that can be config already are: secret reads are denied, destructive commands ask, gitleaks gates commits. Don't re-litigate them in prose — rely on them.

**Security.** Secrets live in `.env` / `.identity.local.env` only (both gitignored), never committed, never echoed into logs or pushed files.

**Windows / Git Bash.** `/` paths (`/d/...`), `$VAR`, `#!/usr/bin/env bash` + `set -euo pipefail`, `python`/`uv` (never `py`), kebab-case filenames.

**Memory.** `memory/` is an Obsidian vault: frontmatter + `[[wikilinks]]`, atomic decision/tool/convention notes, MOCs as hubs. Load `index.json` first; recall with the memory skill; promote significant decisions into their own notes.

**Delegation.** Use subagents (security-auditor, test-writer, bug-fixer, memory-curator) for bounded, permission-separated work; a single session for trivial fixes.

**Planning.** Use plan mode for any multi-file change.

**Continuous improvement.** When a rule keeps getting forgotten, promote it from prose into a hook / permission / rules file.
