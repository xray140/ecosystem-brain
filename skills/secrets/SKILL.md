---
name: secrets
description: Secrets hygiene and identity. Use before commits/pushes, when setting up a repo, when handling API keys or the user's profile/identity, or when the user asks to check for leaked secrets.
---
# Secrets & identity

## Audit (read-only)
```bash
bash /d/Claude_projects/ecosystem-brain/skills/secrets/secrets-doctor.sh
```
Checks: `.gitignore` covers `.env*`/`.identity.local.env`, nothing secret is tracked, `.env` vs `.env.example` parity, gitleaks clean, a git credential helper is set.

## Identity (optional — setup required)
Public identity (git author name/email) can be stored in `memory/identity.md`
frontmatter and applied to git config:
```bash
bash /d/Claude_projects/ecosystem-brain/skills/secrets/apply-identity.sh [--local]
```
**Setup:** this requires a `memory/identity.md` with `git_name:` and `git_email:`
in its frontmatter (does not exist by default — create it to use this).

Private contact (phone, personal email) lives only in `.identity.local.env` (gitignored). Read a key by name when filling a private field, but never echo its value into a committed file, a log, or anything pushed.
