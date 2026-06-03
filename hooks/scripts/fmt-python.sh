#!/usr/bin/env bash
# PostToolUse(Write *.py): format + autofix the written file. Non-blocking.
set -euo pipefail
command -v ruff >/dev/null 2>&1 || exit 0
if command -v uv >/dev/null 2>&1; then
  f="$(uv run --no-project python -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"
else
  f="$(python3 -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"
fi
case "$f" in
  *.py) ruff format "$f" >/dev/null 2>&1 || true; ruff check --fix "$f" >/dev/null 2>&1 || true ;;
esac
exit 0
