# pkgname — agent operating rules

Cross-tool instructions (AGENTS.md standard). Read by Claude Code, Gemini CLI,
OpenAI Codex, Cursor, Copilot, and others. Part of the claude-unified-ecosystem.

## Stack
- **Runtime:** Node.js / TypeScript 5, ESM
- **Test:** vitest (`npm test`)
- **Lint/format:** Biome (`npm run lint` / `npm run format`)
- **Build:** `tsc` → `dist/`
- **Secrets:** `.env` only (gitignored); never committed, never echoed

## Workflow
- Explore → plan → implement. Use plan mode when a change spans multiple files, the approach is unclear, or the code is unfamiliar; for a one-sentence diff, just do it.
- Propose → get approval → execute for any multi-file change
- After changes, run the check and show its output — `npm test` (and `npm run lint`). Never claim success you haven't verified.
- Commit messages: `type(scope): description` (feat, fix, chore, docs, test)

## Key files
| File | Purpose |
|------|---------|
| `src/core.ts` | Pure business logic — no I/O |
| `src/index.ts` | Entry point — thin wrapper over core |
| `tests/core.test.ts` | Unit tests |
| `tsconfig.json` | Strict TypeScript config |
| `biome.json` | Formatter + linter config |

## After scaffold — first-time setup
```bash
npm install
cp .env.example .env
npm test               # confirm green baseline
```

## Conventions
- `core.ts` stays pure — no `process`, no `fetch`, no `fs`
- All exports from `core.ts` must be tested
- Use `.js` extensions in imports (ESM NodeNext requirement)
- No `any` without a comment explaining why
