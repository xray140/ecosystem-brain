---
description: Scaffold a new project from a template, git-init it, and register it in the memory vault.
argument-hint: <type> <name>
---
Create a new project named `$2` of type `$1`.

1. Run: `uv run python /d/Claude_projects/ecosystem-brain/scripts/scaffold.py --type $1 --name $2 --templates-root /d/Claude_projects/ecosystem-brain/templates --dest-root /d/Claude_projects --git`
2. Create `memory/projects/$2.md` in `/d/Claude_projects/ecosystem-brain/memory/projects/` using the project-card format (status: active, today's date, stack inferred from the template). Link any relevant `[[tools/...]]` notes.
3. Refresh the manifest: `uv run python /d/Claude_projects/ecosystem-brain/skills/memory/memory-index.py`

Report the created path and next steps (`uv sync`, `pre-commit install`). If the destination already exists, confirm before passing `--force`.
