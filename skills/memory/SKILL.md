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

## Recall (semantic search)
```bash
# build/refresh embeddings (Ollama: nomic-embed-text)
uv run --no-project python /d/claude-projects/ecosystem-brain/skills/memory/memory-search.py --vault /d/claude-projects/ecosystem-brain/memory index
uv run --no-project python /d/claude-projects/ecosystem-brain/skills/memory/memory-search.py --vault /d/claude-projects/ecosystem-brain/memory search "QUERY" -k 5
```
Add `--offline` to use the deterministic hash embedder when Ollama isn't running.
It is a global flag: it goes **before** the subcommand, not after. The cache is
`<vault>/.search-index.db` (gitignored).

## Structural manifest
```bash
# writes memory/index.json
uv run --no-project python /d/claude-projects/ecosystem-brain/skills/memory/memory-index.py --vault /d/claude-projects/ecosystem-brain/memory --out /d/claude-projects/ecosystem-brain/memory/index.json
# summary only
uv run --no-project python /d/claude-projects/ecosystem-brain/skills/memory/memory-index.py --vault /d/claude-projects/ecosystem-brain/memory --check
```
Load `index.json` at session start instead of reading the whole vault; pull individual notes on demand. Refresh it after creating or editing notes.
