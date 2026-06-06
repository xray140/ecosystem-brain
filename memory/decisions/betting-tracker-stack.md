---
type: decision
status: confirmed
date: 2026-06-06
tags: [betting-tracker, stack, typescript, react, nextjs, web]
---
# betting-tracker: React 18 + Next.js (App Router) web stack

## Problem
The `betting-tracker` project was scaffolded via `/ecosystem-brain:init` as a
web build type. The init interview fixed a concrete stack + an agent roster, but
those choices were inlined in the project card where they're easy to lose track
of and can't be linked to from the roadmap or other notes.

## Decision
Build `betting-tracker` as a **web application** (UI + client-side state talking
to an API/data layer) on:

- **React 18 + Next.js (App Router)** — server components where sensible.
- **TypeScript strict** mode.

## Agents installed
Selected and security-scanned by `/ecosystem-brain:init` for this build type:
`frontend-developer`, `ui-designer`, `security-auditor`, `react-specialist`,
`nextjs-developer`.

## Why
Standard web build profile from `registry/project-profiles.json`; App Router +
server components is the current Next.js default and matches the ecosystem's
"server where sensible" framing. Strict TypeScript is the ecosystem baseline.

See [[claude-best-practices]] for the convention grounding and [[agent-pinning]]
for how the installed agents are pinned.
