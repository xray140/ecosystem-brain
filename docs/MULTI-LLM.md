# Using ecosystem-brain projects with other LLMs

Scaffolded projects are **portable across AI coding tools** via the **AGENTS.md**
standard (originated by OpenAI, governed under the Linux Foundation). One set of
project rules, every assistant.

## Single source of truth
Every scaffolded project ships:
- **`AGENTS.md`** — the canonical, tool-neutral project rules.
- **`CLAUDE.md`** — `@AGENTS.md` (Claude Code reads CLAUDE.md, which imports it).
- **`GEMINI.md`** — `@AGENTS.md` (Gemini CLI reads GEMINI.md, which imports it).

Edit **`AGENTS.md`**. The two stubs only import it — no duplication, no drift.

## Per-tool support (as of June 2026)
| Tool | What it reads | Setup in a scaffolded project |
|------|---------------|-------------------------------|
| **Codex CLI** (OpenAI / ChatGPT) | `AGENTS.md` natively | none — run `codex` in the dir |
| **Cursor** | `AGENTS.md` (+ `.cursor/rules/`) | none — open the folder |
| **GitHub Copilot** | `AGENTS.md` as primary instructions | none |
| **Windsurf / Amp / Devin** | `AGENTS.md` natively | none |
| **Gemini CLI** | `GEMINI.md` → imports `AGENTS.md` | ships a `GEMINI.md` stub |
| **Claude Code** | `CLAUDE.md` → imports `AGENTS.md` | ships a `CLAUDE.md` stub |

## DeepSeek
DeepSeek is a **model, not a reader** — there is no DeepSeek CLI that parses
AGENTS.md. You run DeepSeek *inside* an AGENTS.md-aware tool through its
OpenAI-compatible API, and that host tool feeds it your `AGENTS.md`:

1. Get a key at `platform.deepseek.com`. The endpoint `https://api.deepseek.com`
   is OpenAI-compatible; models e.g. `deepseek-v4-pro` / `deepseek-v4-flash`.
2. Point an AGENTS.md-aware tool at it:
   - **Cline / Roo / Kilo / Continue / Cursor** → provider **"OpenAI Compatible"**,
     Base URL `https://api.deepseek.com`, paste the key, pick the model.
   - **Codex CLI** with a DeepSeek profile (same base URL + key).
3. The host tool loads `AGENTS.md`; DeepSeek answers under those rules.

**Secrets:** the DeepSeek API key goes in the host tool's own config or `.env`
(gitignored) — never in `AGENTS.md` or any committed file.

## Key naming
The repo's `.env.example` reserves the standard names — `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY` (names only; real values
live in the gitignored `.env`). Most CLIs and SDKs pick these up automatically.

## What does NOT transfer
The *project rules* are shared; the *control-tower automation* stays Claude-native:
- **Agents** (`~/.claude/agents/`), **slash commands**, **hooks** (gitleaks / ruff),
  the **install / update / scan / pin** supply chain, and the **memory vault**.
- **MCP servers** — supported by several tools, but configured per-tool.

## Bottom line
One project, many assistants — all reading the same `AGENTS.md`. Switching model
or tool (Claude ↔ Gemini ↔ Codex ↔ DeepSeek-in-Cline) changes the engine, not the
rulebook.
