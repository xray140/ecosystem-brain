---
name: secrets
description: Secrets hygiene and identity. Use before commits/pushes, when setting up a repo, when handling API keys or the user's profile/identity, or when the user asks to check for leaked secrets.
---
# Secrets & identity

## Audit (read-only)
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/secrets/secrets-doctor.sh
```
Checks: `.gitignore` covers `.env*`/`.identity.local.env`, nothing secret is tracked, `.env` vs `.env.example` parity, gitleaks clean, a git credential helper is set.

## Identity
Public identity (git author, handle, public usernames) lives in `memory/identity.md` and is applied with:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/secrets/apply-identity.sh [--local]
```
Private contact (phone, personal email) lives only in `.identity.local.env` (gitignored). Read a key by name when filling a private field, but never echo its value into a committed file, a log, or anything pushed.
