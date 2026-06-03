#!/usr/bin/env bash
# Read-only secrets hygiene check. Exits non-zero if any issue is found.
set -uo pipefail   # not -e: run every check, then aggregate

issues=0
ok()   { echo "  [ok]   $*"; }
warn() { echo "  [warn] $*"; issues=$((issues+1)); }
bad()  { echo "  [FAIL] $*"; issues=$((issues+1)); }

echo "secrets-doctor"

echo "- .gitignore covers secrets"
for pat in '\.env' '\.env\.\*' '\.identity\.local\.env' '\*\.local\.env'; do
  grep -qxE "$pat" .gitignore 2>/dev/null && ok "ignored: $pat" || warn "not in .gitignore: $pat"
done

echo "- nothing secret is tracked"
for f in .env .identity.local.env; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    bad "$f is TRACKED — untrack: git rm --cached $f"
  else
    ok "$f not tracked"
  fi
done

echo "- .env vs .env.example"
if [ -f .env.example ] && [ -f .env ]; then
  missing=0
  while IFS= read -r key; do
    [ -z "$key" ] && continue
    grep -q "^${key}=" .env || { warn "missing in .env: $key"; missing=1; }
  done < <(grep -oE '^[A-Z0-9_]+=' .env.example | sed 's/=$//')
  [ "$missing" -eq 0 ] && ok "all .env.example keys present in .env"
else
  warn ".env or .env.example absent (skipping key diff)"
fi

echo "- gitleaks"
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-banner --redact --log-level error 2>/dev/null && ok "gitleaks: clean" \
    || bad "gitleaks: findings (run: gitleaks detect --redact -v)"
else
  warn "gitleaks not installed (scoop install gitleaks / brew install gitleaks)"
fi

echo "- git credential helper"
helper="$(git config --get credential.helper || true)"
[ -n "$helper" ] && ok "credential.helper = $helper" \
  || warn "none set (Windows: git config --global credential.helper manager)"

echo
[ "$issues" -eq 0 ] && { echo "[ok] no issues"; exit 0; } || { echo "[!] $issues issue(s)"; exit 1; }
