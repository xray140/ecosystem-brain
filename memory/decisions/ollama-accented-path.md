---
type: decision
status: confirmed
date: 2026-06-04
tags: [ollama, windows, path]
---
# Ollama — Accented Username Path Bug

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
Global `~/.claude/commands/ecosystem-brain/` — use absolute paths.
`${CLAUDE_PLUGIN_ROOT}` is NOT resolved by Claude Code; it was aspirational.
