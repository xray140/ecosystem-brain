---
description: Check for and apply updates to all installed agents, skills, and commands.
argument-hint: [--check | --name <name>]
---
Update all installed ecosystem agents/skills/commands. Arguments: $ARGUMENTS

Steps:
1. Run check first: `uv run python /d/Claude_projects/ecosystem-brain/scripts/update-agents.py --check`
2. Show what would change, then apply: `uv run python /d/Claude_projects/ecosystem-brain/scripts/update-agents.py`
3. Re-sync global dirs:
   ```
   cp /d/Claude_projects/ecosystem-brain/agents/*.md ~/.claude/agents/
   cp /d/Claude_projects/ecosystem-brain/commands/*.md ~/.claude/commands/ecosystem-brain/
   ```
4. Commit any changes: `git -C /d/Claude_projects/ecosystem-brain add -A && git commit -m "chore: update agents"`

If $ARGUMENTS contains `--check`, only run step 1. If it contains `--name <x>`, pass that to the script.
