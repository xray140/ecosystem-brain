---
name: memory
description: Search and index the Obsidian-style memory vault. Use when the user asks what was decided/discussed before, references "my project / our approach / the decision", or when recalling cross-session context. Also used to refresh the vault manifest after writing notes.
---
# Memory vault tools

The vault lives at `memory/` (frontmatter + `[[wikilinks]]`). Two bundled scripts:

## Recall (semantic search)
```bash
uv run python /d/claude-projects/ecosystem-brain/skills/memory/memory-search.py index            # build/refresh embeddings (Ollama: nomic-embed-text)
uv run python /d/claude-projects/ecosystem-brain/skills/memory/memory-search.py search "QUERY" -k 5
```
Add `--offline` to use the deterministic hash embedder when Ollama isn't running. The cache is `memory/.search-index.db` (gitignore it).
On Linux/Mac with a real `python3`, `python` can be used directly instead of `uv run python`.

## Structural manifest
```bash
uv run python /d/claude-projects/ecosystem-brain/skills/memory/memory-index.py        # writes memory/index.json
uv run python /d/claude-projects/ecosystem-brain/skills/memory/memory-index.py --check  # summary only
```
Load `index.json` at session start instead of reading the whole vault; pull individual notes on demand. Refresh it after creating or editing notes.
