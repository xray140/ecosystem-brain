---
name: memory
description: Search and index the Obsidian-style memory vault. Use when the user asks what was decided/discussed before, references "my project / our approach / the decision", or when recalling cross-session context. Also used to refresh the vault manifest after writing notes.
---
# Memory vault tools

The vault lives at `memory/` (frontmatter + `[[wikilinks]]`). Two bundled scripts:

Paths below are absolute because a skill runs with the user's project as the
working directory, not the repo. `bootstrap.py` rewrites the canonical prefix
to this clone's real location when it installs the skill, so do not edit them
by hand. `--no-project` stops `uv` from hunting for a pyproject.toml in
whatever project the session happens to be in, and `--vault` is required for
the same reason: it defaults to the relative `memory`, which only resolves
when the working directory is the repo root.

## Recall (keyword search)
```bash
# build/refresh the index
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-search.py --vault {{ECOSYSTEM_ROOT}}/memory index
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-search.py --vault {{ECOSYSTEM_ROOT}}/memory search "QUERY" -k 5
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-search.py --vault {{ECOSYSTEM_ROOT}}/memory status
```
There is one embedder — a deterministic hashed bag-of-words — so there is no
backend to choose and no `--offline` flag any more (v4.8.0). The cache is
`<vault>/.search-index.db` (gitignored).

It matches **wording, not meaning**: a query finds a note only if they share
vocabulary. Phrase queries with words you expect the note itself to use, and
fall back to `grep` / the `index.json` tags when recall comes up short.

`status` is worth running before you trust a result. The offline embedder is a
bag of words, and a search backed by it still returns related-*looking* notes —
which is how this vault spent weeks answering from a hash index nobody knew was
there. `status` reports coverage and which embedder is actually in the cache.
The weekly heartbeat refreshes the index and gates on that status.

## Structural manifest
```bash
# writes memory/index.json
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-index.py --vault {{ECOSYSTEM_ROOT}}/memory --out {{ECOSYSTEM_ROOT}}/memory/index.json
# summary only
uv run --no-project python {{ECOSYSTEM_ROOT}}/skills/memory/memory-index.py --vault {{ECOSYSTEM_ROOT}}/memory --check
```
Load `index.json` at session start instead of reading the whole vault; pull individual notes on demand. Refresh it after creating or editing notes.
