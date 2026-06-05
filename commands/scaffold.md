---
description: Scaffold a new project from a template, git-init it, and register it in the memory vault.
argument-hint: <type> <name>
---
> For a guided, auto-configured setup (tailored AGENTS.md + auto-selected agents),
> use **`/ecosystem-brain:init`** instead. This command is the raw/manual path —
> it drops a plain template with no agent selection.

The user wants to scaffold a new project. Arguments: `$ARGUMENTS`

Parse the arguments as: first word = template type, second word = project name.
Available types: `python-project`, `typescript-project`

Steps:
1. Run: `uv run python /d/claude-projects/ecosystem-brain/scripts/scaffold.py --type <type> --name <name> --templates-root /d/claude-projects/ecosystem-brain/templates --dest-root /d/claude-projects --git`
2. Create `memory/projects/<name>.md` in `/d/claude-projects/ecosystem-brain/memory/projects/` using this format:
   ```
   ---
   type: project
   status: active
   created: <today>
   stack: [python, uv, ruff, pytest]
   tags: [project, python]
   ---
   # <name>
   Scaffolded from `<type>` template on <today>.
   ## Paths
   - Project: `D:\claude-projects\<name>`
   - Package: `<name with hyphens replaced by underscores>`
   ```
3. Refresh the manifest: `uv run python /d/claude-projects/ecosystem-brain/skills/memory/memory-index.py`

Report the created path and next steps (`uv sync`, `pre-commit install`). If the destination already exists, confirm before passing `--force`.
