---
name: secrets
description: Secrets hygiene and identity. Use before commits/pushes, when setting up a repo, when handling API keys or the user's profile/identity, or when the user asks to check for leaked secrets.
---
# Secrets & identity

Script paths are absolute — a skill runs with the user's project as the working
directory. `bootstrap.py` rewrites the canonical prefix to this clone at install
time; do not edit them by hand.

## Audit (read-only)
```bash
bash /d/claude-projects/ecosystem-brain/skills/secrets/secrets-doctor.sh
```
Audits **the current working directory's repo**, which is the intent — run it
from whichever project you are checking, not from the ecosystem clone.

Checks: `.gitignore` covers `.env*`/`.identity.local.env`, nothing secret is tracked, `.env` vs `.env.example` parity, gitleaks clean, a git credential helper is set.

## Identity (optional — setup required)
Public identity (git author name/email) can be stored in `memory/identity.md`
frontmatter and applied to git config:
```bash
bash /d/claude-projects/ecosystem-brain/skills/secrets/apply-identity.sh --file /d/claude-projects/ecosystem-brain/memory/identity.md [--local]
```
`--file` is required here: it defaults to the relative `memory/identity.md`,
which only resolves when the working directory is the ecosystem clone.
**Setup:** this requires a `memory/identity.md` with `git_name:` and `git_email:`
in its frontmatter (does not exist by default — create it to use this).

Private contact (phone, personal email) lives only in `.identity.local.env` (gitignored). Read a key by name when filling a private field, but never echo its value into a committed file, a log, or anything pushed.
