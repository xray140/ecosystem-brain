---
type: decision
status: confirmed
date: 2026-06-04
tags: [hooks, claude-code, config]
---
# Claude Code Hook Format

Discovered through live debugging — 3 restart cycles to get right.

## Correct structure

```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "if": "Bash(git commit*)", "command": "bash /path/to/script.sh" }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Write",
      "hooks": [
        { "type": "command", "if": "Write(*.py)", "command": "bash /path/to/fmt.sh" }
      ]
    }
  ]
}
```

## Rules
- `matcher` = **tool name only** (`Bash`, `Write`, `Edit`) — no argument patterns here
- `if` = permission-rule syntax for argument filtering — goes on the individual hook entry
- `Write(*.py)` ✅ matches by filename suffix (works for absolute paths too)
- `Write(**/*.py)` ❌ does NOT match — avoid
- `Bash(git commit*)` ✅ in `if` field, not `matcher`
- PostToolUse hooks reload **without restart** when settings.json is edited
- PreToolUse hooks require a restart to take effect

## Where hooks live
`~/.claude/settings.json` — global, fires in every session and project.
Project-level: `.claude/settings.json` in any project folder.
