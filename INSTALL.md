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

## Optional: keep the agent catalog fresh
`scripts/refresh-catalog.bat` rebuilds `registry/catalog.json` from GitHub so the
SessionStart suggester recommends current agents. Run it manually anytime, or
register a weekly task (PowerShell, run once):
```powershell
$a = New-ScheduledTaskAction -Execute "D:\claude-projects\ecosystem-brain\scripts\refresh-catalog.bat"
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 9am
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName "EcosystemBrain-CatalogRefresh" -Action $a -Trigger $t -Settings $s -Force
```
(The bat derives the repo path from its own location, so adjust the `-Execute`
path to wherever you cloned. Requires `gh auth login` so `catalog.py build` can
query GitHub.)

## Per-machine notes
Things that legitimately differ per PC (paths, tokens) live in `.env` and
`~/.claude/settings.json` — both machine-local, never committed. Everything in
the repo is portable.
