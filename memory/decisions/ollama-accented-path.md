---
type: decision
status: superseded
date: 2026-06-04
superseded_by: no-ollama
tags: [ollama, windows, path, historical]
---
# Ollama — Accented Username Path Bug

> **Superseded 2026-08-22 by [[no-ollama]].** Ollama was removed from the
> ecosystem; `OLLAMA_MODELS` is no longer set or documented anywhere here. Kept
> because the underlying trap is not Ollama-specific: a native tool that mangles
> an accented Windows username will do it again, and this is the worked example.

## Problem
Username `Martin Cayré` contains `é` (accented char). Ollama's llama-server
(llama.cpp) corrupts the path to `Martin Cayr�` when loading model blobs,
causing a fatal load error.

## Fix
Set `OLLAMA_MODELS` to an ASCII-safe path:

```
OLLAMA_MODELS=D:\ollama-models\models
```

Model blobs are stored at `D:\ollama-models\models\blobs\`.
The `~\.ollama\` default location is abandoned (still exists but unused).

## Auto-start
`D:\ecosystem-tools\start-ollama.bat` — uses `%LOCALAPPDATA%` to avoid
hardcoding the accented username. Registered as Windows Task Scheduler task
`EcosystemBrain-OllamaServe`, fires at logon.

## Commands path
Global `~/.claude/commands/ecosystem-brain/` — use absolute paths, written by
`bootstrap.py`'s `rewrite_paths()` at install time.

**Correction (2026-07-31):** the earlier claim here — that
`${CLAUDE_PLUGIN_ROOT}` "is NOT resolved by Claude Code; it was aspirational" —
is out of date. Both `${CLAUDE_PLUGIN_ROOT}` (plugin install dir) and
`${CLAUDE_SKILL_DIR}` (the directory holding a skill's own `SKILL.md`) are
documented, supported tokens. They expand only for content Claude Code actually
loads as a plugin/skill — which is *not* how this repo is installed today, so
`bootstrap.py`'s rewrite remains the working mechanism for `commands/` and
`agents/`. See [[text-file-write-conventions]] for the sibling portability rule.
