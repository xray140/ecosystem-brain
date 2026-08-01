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
1. Run: `uv run python {{ECOSYSTEM_ROOT}}/scripts/scaffold.py --type <type> --name <name> --templates-root {{ECOSYSTEM_ROOT}}/templates --git`
   (`--dest-root` defaults to the clone's parent directory, or `$ECOSYSTEM_DEST_ROOT`
   if set — don't hardcode it. The script prints the path it created.)
2. Create `memory/projects/<name>.md` in `{{ECOSYSTEM_ROOT}}/memory/projects/` using this format:
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
   - Project: `<the path scaffold.py printed>`
   - Package: `<name with hyphens replaced by underscores>`
   ```
3. Refresh the manifest: `uv run python {{ECOSYSTEM_ROOT}}/skills/memory/memory-index.py`

Report the created path and next steps (`uv sync`, `pre-commit install`). If the destination already exists, confirm before passing `--force`.
