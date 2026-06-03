#!/usr/bin/env bash
# Apply the PUBLIC identity (memory/identity.md frontmatter) to git config.
# Never reads or prints private contact data (.identity.local.env).
set -euo pipefail

SCOPE="--global"
IDENTITY_FILE="memory/identity.md"

usage() {
  cat <<USAGE
apply-identity.sh — set git author identity from memory/identity.md
  --local        apply to the current repo only (default: --global)
  --global       apply globally (default)
  --file <path>  identity note (default: memory/identity.md)
  -h, --help     this help
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --local) SCOPE="--local"; shift ;;
    --global) SCOPE="--global"; shift ;;
    --file) IDENTITY_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[error] unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

[ -f "$IDENTITY_FILE" ] || { echo "[error] not found: $IDENTITY_FILE" >&2; exit 1; }
fm() { sed -n 's/^'"$1"':[[:space:]]*//p' "$IDENTITY_FILE" | head -n1 | tr -d '"'; }

NAME="$(fm git_name)"; EMAIL="$(fm git_email)"
[ -n "$NAME" ]  || { echo "[error] git_name missing"  >&2; exit 1; }
[ -n "$EMAIL" ] || { echo "[error] git_email missing" >&2; exit 1; }

git config "$SCOPE" user.name  "$NAME"
git config "$SCOPE" user.email "$EMAIL"
echo "[ok] git $SCOPE user.name='$NAME' user.email='$EMAIL'"
