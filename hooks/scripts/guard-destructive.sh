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
# Match root/home wipes WITHOUT false-positiving on legit paths like /tmp/foo.
# "rm -rf /" only triggers when / is the target (end-of-string or followed by a
# space), not when it's a prefix of a real path. Plus explicit system dirs.
case "$cmd" in
  *"rm -rf /"|*"rm -fr /"|*"rm -rf / "*|*"rm -fr / "*|*"rm -rf ~"*|*"rm -fr ~"*|*'rm -rf $HOME'*) \
    block "refusing catastrophic recursive delete of root/home" ;;
  *"rm -rf /etc"*|*"rm -rf /usr"*|*"rm -rf /bin"*|*"rm -rf /var"*|*"rm -rf /lib"*|*"rm -rf /boot"*|*"rm -rf /sys"*|*"rm -rf /root"*|*"rm -rf /home"*) \
    block "refusing recursive delete of a system directory" ;;
  *"git push"*--force*main*|*"git push -f"*main*) block "refusing force-push to main" ;;
esac
exit 0
