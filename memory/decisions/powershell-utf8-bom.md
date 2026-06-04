---
type: decision
status: confirmed
date: 2026-06-05
tags: [windows, powershell, encoding, env]
---
# PowerShell 5.1 Out-File Adds a UTF-8 BOM

## Problem
`$x | Out-File -Encoding utf8 file` on Windows PowerShell 5.1 writes the file
with a leading UTF-8 BOM (bytes EF BB BF). This silently breaks tools that
anchor-match the first line:

- `.env` written this way → secrets-doctor's `grep ^GITHUB_TOKEN=` misses the
  first key only (BOM sits before it). Lines 2+ match fine, so it looks like
  just one key is "missing."
- dotenv parsers may read the first key name as `﻿GITHUB_TOKEN`.

## Symptom seen
health-check reported `missing in .env: GITHUB_TOKEN` even though the token was
present — only the first line was affected.

## Fix
Write files without a BOM:
```powershell
[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $false))
```
NOT `Out-File -Encoding utf8` (5.1) and NOT `Set-Content -Encoding utf8` (5.1).

Python's `Path.write_text(encoding="utf-8")` does NOT add a BOM — so
bootstrap.py and the memory scripts are already safe. The BOM only sneaks in via
PowerShell here-string → Out-File.

## Rule
For any file a non-PowerShell tool will parse (.env, .json, .sh, .py), write via
`[IO.File]::WriteAllText` with `UTF8Encoding $false`, or use Python/the Write
tool instead of PowerShell Out-File.

See [[windows-python-invocation]], [[windows-path-translation]].
