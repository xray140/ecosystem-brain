# Using the Memory Vault in Obsidian

The `memory/` folder is a fully configured Obsidian vault. Obsidian is the
human-readable window into the same knowledge base Claude searches semantically.

## Open it
1. Launch Obsidian
2. **Open folder as vault** → select `D:\Claude_projects\ecosystem-brain\memory`
3. The `.obsidian/` config (graph colors, templates, plugins) loads automatically

## What's in the vault
| Folder | Contents |
|--------|----------|
| `decisions/` | Permanent lessons (hook format, Windows path quirks, …) |
| `projects/` | One card per scaffolded project |
| `sessions/` | Dated logs auto-written by the SessionEnd hook |
| `templates/` | `decision.md`, `project.md` — use via the Templates plugin |
| `README.md` | The MOC (map of content) hub |

## Daily use
- **Graph view** (Ctrl+G): nodes colored by type — projects (blue), decisions
  (red), sessions (green), MOCs (yellow). Edges are `[[wikilinks]]`.
- **Quick switcher** (Ctrl+O): jump to any note by name.
- **Global search** (Ctrl+Shift+F): full-text across the vault.
- **New note from template**: Ctrl+P → "Templates: Insert template".
- **Backlinks** panel: see what links to the current note.

## How it stays in sync with Claude
- Claude writes notes here (decisions, project cards) as markdown with frontmatter.
- The SessionEnd hook appends a dated session note automatically.
- `memory-index.py` rebuilds `index.json` (the manifest Claude loads first).
- `memory-search.py` embeds notes (Ollama) for semantic recall.

You edit in Obsidian; Claude reads/writes the same files. No special sync — it's
just markdown on disk. Run `/ecosystem-brain:memory-gc` to prune + re-index.

## Convention
Every note: YAML frontmatter (`type`, `tags`, `date`) + `[[wikilinks]]` to
related notes. Keep notes atomic — one decision/tool/project per file.
