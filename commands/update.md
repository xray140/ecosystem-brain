---
description: Check for and apply updates to all installed agents, skills, and commands.
argument-hint: [--all | --check | --name <name>]
---
Update all installed ecosystem agents/skills/commands. Arguments: $ARGUMENTS

Each GitHub-sourced agent is **pinned to a commit SHA**. `update` re-resolves the
branch tip via `gh`, and on a real content change shows `oldsha -> newsha` plus a
GitHub compare URL so you can review the diff. Updates are re-scanned by
`scan_agent.py`; a HIGH-risk upstream is refused and stashed in `quarantine/`
(current pin kept) for manual review.

Steps:
1. Run check first: `uv run python {{ECOSYSTEM_ROOT}}/scripts/update-agents.py --check`
2. Show what would change, then apply all: `uv run python {{ECOSYSTEM_ROOT}}/scripts/update-agents.py --all`
3. Re-sync global dirs:
   ```
   cp {{ECOSYSTEM_ROOT}}/agents/*.md ~/.claude/agents/
   cp {{ECOSYSTEM_ROOT}}/commands/*.md ~/.claude/commands/ecosystem-brain/
   ```
4. Commit any changes: `git -C {{ECOSYSTEM_ROOT}} add -A && git commit -m "chore: update agents"`

If $ARGUMENTS contains `--check`, only run step 1. If it contains `--name <x>`, pass that to the script.
If any update was BLOCKED (quarantined), tell the user to review `quarantine/<name>.md` before trusting it.
