---
description: Check for and apply updates to all installed agents, skills, and commands.
argument-hint: [--all | --check | --name <name>]
---
Update all installed ecosystem agents/skills/commands. Arguments: $ARGUMENTS

Each GitHub-sourced update is re-scanned by `scan_agent.py`; a HIGH-risk upstream
is refused and stashed in `quarantine/` (current version kept) for manual review.

Steps:
1. Run check first: `uv run python /d/claude-projects/ecosystem-brain/scripts/update-agents.py --check`
2. Show what would change, then apply all: `uv run python /d/claude-projects/ecosystem-brain/scripts/update-agents.py --all`
3. Re-sync global dirs:
   ```
   cp /d/claude-projects/ecosystem-brain/agents/*.md ~/.claude/agents/
   cp /d/claude-projects/ecosystem-brain/commands/*.md ~/.claude/commands/ecosystem-brain/
   ```
4. Commit any changes: `git -C /d/claude-projects/ecosystem-brain add -A && git commit -m "chore: update agents"`

If $ARGUMENTS contains `--check`, only run step 1. If it contains `--name <x>`, pass that to the script.
If any update was BLOCKED (quarantined), tell the user to review `quarantine/<name>.md` before trusting it.
