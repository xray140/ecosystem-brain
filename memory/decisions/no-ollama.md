---
type: decision
status: confirmed
date: 2026-08-22
tags: [ollama, memory, search, dependencies]
---
# Ollama is out — memory search is keyword-only

## Decision

Removed Ollama from the ecosystem entirely (v4.8.0). `memory-search.py` has one
embedder: a deterministic hashed bag-of-words, local, no server, no network.

Gone with it: the `OllamaEmbedder` class, the `nomic-embed-text` default, the
`--offline` flag (it opted out of a backend that no longer exists), the
`OLLAMA_MODELS` key in `.env` / `.env.example`, the `OPTIONAL_TOOLS` prerequisite
list, and every doc line advertising semantic search.

## Why

Stated plainly by the operator on the other PC: *no more Ollama.* v4.7.0 had
only demoted it to optional — the process was still the recommended path, the
model was still the default, and every health report still printed a line about
it. Optional was not the ask.

## What it costs — this is real, do not paper over it

Search now matches **wording, not meaning**. The measured example from the
v4.7.0 changelog: *"why is the registry split between shared and machine-local"*
returned the right note at 0.805 with Ollama against 0.545 without, on a query
sharing almost no keywords with the note. Re-measured after removal: 0.538,
still rank 1 — the ordering survived here, the margin did not.

Nothing was added back to compensate. A replacement embedder was considered and
rejected in the same breath as the removal: `sentence-transformers` means torch
on a Windows box for a 42-note vault, and an API embedder means a key, a cost,
and every private note leaving the machine. If recall gets bad enough to matter,
the honest upgrade is BM25/TF-IDF over the vault — pure stdlib, no dependency,
strictly better than hashed bag-of-words — not another model server.

Say **"keyword search"** when describing this. See [[verification-integrity]]:
this vault has already spent weeks answering from an index that advertised
semantics it was not delivering, and the lesson was that plausible output is the
hardest kind of wrong to notice.

## Enforcement

`tests/test_ollama_is_gone.py` — asserts no backend, no network imports, no
`--offline`, no env key, no prerequisite, and that the retired scheduled task is
*still* actively unregistered. Prose was already tried; it lasted one release.

## Loose end (2026-08-22)

`EcosystemBrain-OllamaServe` is still registered on Verdun10. It was created in
an elevated shell, so `Unregister-ScheduledTask` answers `Accès refusé` from a
normal session. Run `scripts/register-scheduled-tasks.ps1` from an **elevated**
PowerShell to clear it. The script used to print `[retired]` regardless — it now
re-queries and reports `[STUCK]` with a non-zero exit instead.

## Links
- [[ollama-accented-path]] — superseded; the path bug it fixed no longer applies
- [[verification-integrity]] — why the degraded index went unnoticed for weeks
