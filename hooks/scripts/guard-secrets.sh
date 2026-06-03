#!/usr/bin/env bash
# PreToolUse(git commit/push): block if gitleaks finds a staged secret.
set -euo pipefail
command -v gitleaks >/dev/null 2>&1 || { echo "[allow] gitleaks not installed — skipping scan"; exit 0; }
if ! gitleaks protect --staged --redact --no-banner --log-level error 2>/dev/null; then
  echo '{"decision":"block","reason":"gitleaks detected a secret in staged changes; commit/push blocked"}'
  exit 2
fi
exit 0
