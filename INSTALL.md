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

## 5. Ollama — optional (semantic memory)
Skip this and everything still works: `memory-search` falls back to an offline
hash embedder, and no check reports it as a problem. Install it for markedly
better recall — real embeddings match on meaning, the fallback on wording.

```bash
ollama pull nomic-embed-text
ollama serve          # only while you want embeddings; there is no logon task
```
Index with it running: `memory-search.py index --rebuild`.

On Windows with an accented username, set an ASCII-safe model path:
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\ollama-models\models", "User")
```
See `memory/decisions/ollama-accented-path.md` for why.

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
`-ExecutionPolicy Bypass` is not optional: the Windows default is `Restricted`,
so without it the script fails `UnauthorizedAccess` before running a line. The
flag applies to that one process and changes no machine state.

It schedules:
| Task | When | Does |
|------|------|------|
| `EcosystemBrain-CatalogRefresh` | weekly (Sun 9am) | `catalog.py build` — refresh the agent catalog from GitHub |
| `EcosystemBrain-Maintenance` | weekly (Mon 9am) | health heartbeat: 8 checks — `doctor`, `selfcheck`, `project_doctor`, `task_doctor`, memory index refresh + status, `agent_usage`, `update --check`. Writes `memory/maintenance/<date>.md` and `last-run.log` |

- The registrar disables both battery guards. PowerShell defaults them **on**,
  which means a laptop task refuses to start on battery and is killed if the
  machine switches to it — every weekly run here died that way from 2026-07-15
  to 08-02 while the tasks showed `State: Ready`. `task_doctor` now checks each
  task's last *result*, so that cannot go unnoticed again.

- Re-running is safe (`-Force`). Overwriting a task first created in an **elevated**
  shell needs an elevated PowerShell; the script reports `[exists]` and moves on otherwise.
- Re-running also drops tasks the script no longer ships — `EcosystemBrain-OllamaServe`
  was retired in v4.7.0 and is unregistered on the next run.
- Remove them all: `powershell -ExecutionPolicy Bypass -File scripts\register-scheduled-tasks.ps1 -Unregister`.
- The catalog + update steps need `gh auth login`. Reports land in `memory/maintenance/`
  (gitignored) — read the latest to see the last heartbeat's verdict.

## Per-machine notes
Things that legitimately differ per PC (paths, tokens) live in `.env` and
`~/.claude/settings.json` — both machine-local, never committed. Everything in
the repo is portable.
