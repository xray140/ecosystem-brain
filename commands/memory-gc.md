---
description: Prune stale and duplicate notes from the memory vault, then rebuild the index.
---
Clean up the memory vault at `/d/Claude_projects/ecosystem-brain/memory/`:

1. List all notes and identify: duplicates, notes older than 90 days with status "archived", empty notes (frontmatter only, no body).
2. Propose a deletion list — do NOT delete without confirmation.
3. After approval: remove approved files, then run `uv run python /d/Claude_projects/ecosystem-brain/skills/memory/memory-index.py` to rebuild the manifest.

Report how many notes were pruned and the new total.
