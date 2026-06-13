# Using the Memory Vault in Obsidian

The `memory/` folder is a fully configured Obsidian vault. Obsidian is the
human-readable window into the same knowledge base Claude searches semantically.

## Open it
1. Launch Obsidian
2. **Open folder as vault** → select **`D:\claude-projects\ecosystem-brain\memory`**
3. The `.obsidian/` config (graph colors, templates, plugins) loads automatically

> **Open `memory/`, not a parent folder.** If you open `D:\claude-projects` (or
> the repo root) the graph fills with noise that isn't part of the knowledge
> base — screenshots (`.png`), compiled files (`__pycache__/*.pyc`), scripts
> (`.py`), and a `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`README.md` from every
> project and template (operational files that don't wiki-link to anything). The
> `memory/` vault is the curated, fully-connected knowledge graph; everything
> else is code, not notes.
>
> If you *do* want a repo-wide view, declutter it in **Settings → Files & Links →
> Excluded files** (`__pycache__`, `.git`, `.venv`, `node_modules`) and turn off
> **Show attachments** in graph settings.

## What's in the vault
| Folder | Contents |
|--------|----------|
| `decisions/` | Permanent lessons (hook format, Windows path quirks, …) |
| `projects/` | One card per scaffolded project |
| `sessions/` | Dated logs auto-written by the SessionEnd hook |
| `maintenance/` | Weekly heartbeat reports (auto-written) |
| `templates/` | `decision.md`, `project.md` — use via the Templates plugin |
| `README.md`, `roadmap.md`, `projects-moc.md` | MOC (map-of-content) hubs |

## See every connection (graph view)
The vault is a single connected web: `README` and `roadmap` link every decision,
`projects-moc` links every project, and each project card links back to the hub
and to the stack decisions it relies on. To see it cleanly:

- **Global graph**: `Ctrl+G`. **Local graph** (one note + its neighbours):
  open a note → `Ctrl+P` → "Open local graph"; raise **Depth** to 2-3.
- **Color groups by type** (graph settings → Groups): `tag:#moc` yellow,
  `tag:#decision` red, `tag:#project` blue. Links resolve by note name, so
  `[[hook-format]]` and `[[decisions/hook-format]]` both point to the same node.
- **Hide the auto-generated noise**: in the graph search add
  `-path:sessions -path:maintenance` (those are machine-written logs with no
  links — expected orphans). Toggle **Orphans** off to drop templates too.
- A genuinely dangling link shows as a faint unresolved node; the indexer also
  lists them under each note's `unresolved` in `index.json` (and the count in
  `counts.unresolved`) so they're easy to find and fix. `/ecosystem-brain:memory-gc`
  repoints them.

## Daily use
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
