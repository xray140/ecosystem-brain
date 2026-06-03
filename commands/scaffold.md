---
description: Scaffold a new project from a template, git-init it, and register it in the memory vault.
argument-hint: <type> <name>
---
Create a new project named `$2` of type `$1`.

1. Run: `python ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py --type $1 --name $2 --templates-root ${CLAUDE_PLUGIN_ROOT}/templates --dest-root /d/Claude_projects --git`
2. Create `memory/projects/$2.md` using the project-card format (status: active, today's date, stack inferred from the template). Link any relevant `[[tools/...]]` notes.
3. Refresh the manifest: `python ${CLAUDE_PLUGIN_ROOT}/skills/memory/memory-index.py`.

Report the created path and next steps (`uv sync`, `pre-commit install`). If the destination already exists, confirm before passing `--force`.
