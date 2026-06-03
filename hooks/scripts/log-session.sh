#!/usr/bin/env bash
# SessionEnd: ensure a dated session note exists in the vault (only inside an ecosystem repo).
set -euo pipefail
base="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -d "$base/memory" ] || exit 0
dir="$base/memory/sessions"; mkdir -p "$dir"
f="$dir/$(date +%F).md"
if [ ! -f "$f" ]; then
  printf -- '---\ntype: session\ndate: %s\ntags: [session]\n---\n# Session %s\n' "$(date +%F)" "$(date +%F)" > "$f"
fi
printf -- '- session ended %s\n' "$(date +%H:%M)" >> "$f"
exit 0
