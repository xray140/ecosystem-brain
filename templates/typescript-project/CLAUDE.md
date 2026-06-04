# pkgname — operating rules

Part of the claude-unified-ecosystem. Inherits ecosystem-brain conventions.

## Stack
- **Runtime:** Node.js / TypeScript 5, ESM
- **Test:** vitest (`npm test`)
- **Lint/format:** Biome (auto-applied on Write by ecosystem hook if configured)
- **Build:** `tsc` → `dist/`
- **Secrets:** `.env` only (gitignored); never committed, never echoed

## Workflow
- Propose → get approval → execute for any multi-file change
- Use plan mode for structural changes
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
