---
description: Tidy the memory vault — promote decisions, find orphans/stale notes, refresh the index.
---
Delegate to the `memory-curator` subagent. It should: promote inlined decisions into `memory/decisions/`, list orphan notes and stale `active` projects (no session in 30 days), report dangling `[[wikilinks]]`, and run the memory indexer. Never delete a note without explicit confirmation. Return a short report.
