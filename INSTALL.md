# Installing ecosystem-brain on a new PC

The whole control tower is portable. On any machine:

## 1. Prerequisites
Install these (the bootstrap reports which are missing):
- **Required:** `git`, `node`/`npx`, `uv` (provides Python + ruff)
- **Recommended:** `gitleaks`, `gh` (GitHub CLI), `ollama` + `nomic-embed-text`

Windows (winget):
```powershell
winget install Git.Git OpenJS.NodeJS GitHub.cli Gitleaks.Gitleaks Ollama.Ollama
irm https://astral.sh/uv/install.ps1 | iex
uv tool install ruff
```

## 2. Clone
```bash
git clone https://github.com/xray140/ecosystem-brain.git
cd ecosystem-brain
```
Clone anywhere — the bootstrap derives all paths from the clone location.

## 3. Bootstrap
```bash
uv run python scripts/bootstrap.py --dry-run   # preview
uv run python scripts/bootstrap.py             # apply
```
This:
- Merges hooks + permissions into `~/.claude/settings.json` (keeps your MCPs),
  with hook paths generated from this clone's location
- Copies commands → `~/.claude/commands/ecosystem-brain/` **and rewrites their
  hardcoded repo paths to this clone** (so a clone at any location works)
- Copies agents → `~/.claude/agents/` (paths rewritten too)
- Seeds `.env` from `.env.example`
- Reports missing prerequisites

Testing tip: set `ECOSYSTEM_CLAUDE_DIR=/tmp/test` to bootstrap into a throwaway
dir without touching your real `~/.claude/`.

## 4. Secrets
Fill in `.env` (gitignored):
```bash
gh auth login                  # then:
gh auth token                  # -> paste into GITHUB_TOKEN in .env
```
Also set as a user env var so MCP servers resolve it:
```powershell
[Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_...", "User")
```

## 5. Ollama (semantic memory)
```bash
ollama pull nomic-embed-text
```
On Windows with an accented username, set an ASCII-safe model path:
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\ollama-models\models", "User")
```
Optionally register `scripts/start-ollama.bat` as a logon task (see
`memory/decisions/ollama-accented-path.md`).

## 6. Restart Claude Code
Hooks, commands, and the SessionStart agent-suggester load at startup.

## 7. Verify
```bash
/ecosystem-brain:health-check
```

## Updating later
```bash
git pull
uv run python scripts/bootstrap.py    # re-sync commands/agents/hooks
/ecosystem-brain:update               # update installed third-party agents (re-scanned)
```

## Scheduled tasks (Windows)
One idempotent script registers all recurring jobs, path-derived from this clone:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-scheduled-tasks.ps1
```
It schedules:
| Task | When | Does |
|------|------|------|
| `EcosystemBrain-OllamaServe` | at logon | starts the Ollama server (semantic memory search) |
| `EcosystemBrain-CatalogRefresh` | weekly (Sun 9am) | `catalog.py build` — refresh the agent catalog from GitHub |
| `EcosystemBrain-Maintenance` | weekly (Mon 9am) | health heartbeat: `bootstrap --verify` + `selfcheck` + `update --check`, writes `memory/maintenance/<date>.md` |

- Re-running is safe (`-Force`). Overwriting a task first created in an **elevated**
  shell needs an elevated PowerShell; the script reports `[exists]` and moves on otherwise.
- Remove them all: `scripts\register-scheduled-tasks.ps1 -Unregister`.
- The catalog + update steps need `gh auth login`. Reports land in `memory/maintenance/`
  (gitignored) — read the latest to see the last heartbeat's verdict.

## Per-machine notes
Things that legitimately differ per PC (paths, tokens) live in `.env` and
`~/.claude/settings.json` — both machine-local, never committed. Everything in
the repo is portable.
