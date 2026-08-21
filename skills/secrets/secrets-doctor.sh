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
# Two directives in .env.example, shared with project_doctor.py:
#   #! optional: A, B     never reported; declared but not required
#   #! one-of: A, B       satisfied by any one member; reported once if none set
# Without them a plain set difference cannot tell "not configured yet" from
# "deliberately not using that tool". The four multi-LLM keys here are reserved
# names that nothing in this repo reads, and they were warned about on every run
# with no edit that would clear them short of pasting keys you do not use.
if [ -f .env.example ] && [ -f .env ]; then
  missing=0
  optional="$(grep -oE '^#!\s*optional:.*' .env.example | sed 's/^#!\s*optional:\s*//' \
    | tr ',' '\n' | tr -d ' ' | grep -v '^$' || true)"
  # Members of a one-of group are excluded here and judged as a group below.
  # Without this the unchosen member is reported missing — the exact defect the
  # marker exists to prevent, reintroduced one layer down. Caught by the test
  # that asserts this script and project_doctor.py reach the same verdict.
  grouped="$(grep -oE '^#!\s*one-of:.*' .env.example | sed 's/^#!\s*one-of:\s*//' \
    | tr ',' '\n' | tr -d ' ' | grep -v '^$' || true)"
  skip="$(printf '%s\n%s\n' "$optional" "$grouped" | grep -v '^$' || true)"
  while IFS= read -r key; do
    [ -z "$key" ] && continue
    printf '%s\n' "$skip" | grep -qx "$key" && continue
    grep -q "^${key}=" .env || { warn "missing in .env: $key"; missing=1; }
  done < <(grep -oE '^[A-Z0-9_]+=' .env.example | sed 's/=$//')

  # one-of groups: the group is met when any member is set.
  while IFS= read -r group; do
    [ -z "$group" ] && continue
    satisfied=0
    for key in $(printf '%s' "$group" | tr ',' ' '); do
      grep -q "^${key}=" .env && satisfied=1
    done
    if [ "$satisfied" -eq 0 ]; then
      warn "missing in .env: one of $(printf '%s' "$group" | tr -d ' ' | tr ',' '|')"
      missing=1
    fi
  done < <(grep -oE '^#!\s*one-of:.*' .env.example | sed 's/^#!\s*one-of:\s*//' || true)

  [ "$missing" -eq 0 ] && ok "all required .env.example keys present in .env"
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
