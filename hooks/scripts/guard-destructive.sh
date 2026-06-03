#!/usr/bin/env bash
# PreToolUse(Bash): hard-block catastrophic commands. Softer confirms come from permissions.ask.
set -euo pipefail
if command -v uv >/dev/null 2>&1; then
  cmd="$(uv run --no-project python -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("tool_input",{}).get("command",""))' 2>/dev/null || true)"
else
  cmd="$(python3 -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("tool_input",{}).get("command",""))' 2>/dev/null || true)"
fi
block() { printf '{"decision":"block","reason":"%s"}\n' "$1"; exit 2; }
case "$cmd" in
  *"rm -rf /"*|*"rm -rf ~"*|*"rm -fr /"*) block "refusing catastrophic recursive delete" ;;
  *"git push"*--force*main*|*"git push -f"*main*) block "refusing force-push to main" ;;
esac
exit 0
