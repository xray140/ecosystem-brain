---
type: decision
status: confirmed
date: 2026-07-31
tags: [windows, encoding, git, python, file-io]
---
# Text File Write Conventions

## Problem

Two distinct bugs, same root cause — Python's `Path.write_text()` defaults:

1. **CRLF Translation (Windows):** `Path.write_text()` runs in text mode, so on Windows every `\n` is translated to `\r\n`. The repo's own `.gitattributes` pins `* text=auto eol=lf` and `*.md text eol=lf`, so every file the ecosystem wrote came back dirty in `git status`. Measured symptoms:
   - The three GitHub-sourced agents (cli-developer, data-engineer, python-pro) sat permanently modified
   - A freshly scaffolded python-project came out with 8 CRLF files (AGENTS.md 46 CRLF, pyproject.toml 31, cli.py 21, test_core.py 22)

2. **Encoding Fallback (cp1252):** `write_text()`/`read_text()` without `encoding=` fall back to the locale codec — cp1252 on Windows. A single non-ASCII character (reproduced with `✓`) raised `UnicodeEncodeError` and aborted `:install`.

## Solution

Every `Path.write_text()` in the ecosystem passes **both** `encoding="utf-8"` and `newline="\n"`. Same for `read_text()`: always `encoding="utf-8"`. This rule is now enforced at all 16 write sites, verifiable by AST.

### Additional rule for upstream content

`.replace("\r\n", "\n")` **before** writing, but **only** where raw fetched upstream bytes are written:
- `install-agent.py`
- `update-agents.py`

**Reason:** `newline="\n"` only suppresses translation of `\n`; it does not strip `\r\n` already present in upstream content. Everywhere else the content came through `read_text()` in universal-newline mode or was generated in-process, so the replace would be dead code.

### Exception: scan_agent.py

The quarantine write takes `newline="\n"` but deliberately **NOT** the replace. A forensic copy of suspect content should not be re-translated. (Note: this fidelity is partial — the local `--file` path already went through universal-newline `read_text()` upstream, so only network-fetched content is intact.)

### Update detection safety

`entry["hash"]` is md5 of the raw fetched upstream string, compared against a freshly fetched string. Normalizing what lands on disk cannot cause a false "updated" loop.

## Implementation

Landed in commits 41c20e6, 84be657, 3bbfd95 (released as v4.3.4).

## Related

- [[powershell-utf8-bom]] — adjacent encoding decision (Out-File BOM issue)
- [[windows-python-invocation]] — use `uv run python` (same Windows-specific class of issue)
- [[windows-path-translation]] — path syntax in Python vs. CLI args
