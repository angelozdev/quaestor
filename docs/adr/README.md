# Architecture Decision Records (technical)

Technical and architecture decisions for Quaestor. Each decision is one file
named `NNNN-slug.md`. Numbering is stable — never renumber; gaps from rejected
ADRs are kept.

**Product decisions** live in `../decisions/product-decisions.md` — do not mix
them in here.

New ADRs are created with the `adr` skill:
`uv run .claude/skills/adr/scripts/new_adr.py "<title>"`.

## Index

| #    | Title | Status | Date |
|------|-------|--------|------|
| 0001 | English as the language for all code | accepted | 2026-06-19 |
| 0002 | App-agnostic frontend design system in `ui/` module | accepted | 2026-06-20 |
| 0003 | pnpm as the sole package manager for the frontend | accepted | 2026-06-20 |
| 0004 | Dark-first theming via next-themes with an app-level elevation token layer | accepted | 2026-06-20 |
| 0005 | Soft-delete and restore as the uniform lifecycle for goals, recurring, and masters | accepted | 2026-06-21 |
| 0006 | Goals and budgets write API with MCP parity | accepted | 2026-06-21 |
| 0007 | Biome and lefthook as frontend format/lint | accepted | 2026-06-21 |
| 0008 | TanStack Form as the sole form library, restoring zod to v4 | accepted | 2026-06-21 |
| 0009 | Closing the MCP parity gap | accepted | 2026-06-21 |
| 0010 | Deployment posture | superseded by 0026 | 2026-06-22 |
| 0011 | MCP only over Tailscale | superseded by 0025 | 2026-06-22 |
| 0012 | Litestream for continuous backup | superseded by 0024 | 2026-06-22 |
| 0013 | Daily scheduler as a thin sidecar | superseded by 0026 | 2026-06-22 |
| 0014 | Chat endpoint with LiteLLM and an in-memory MCP bridge | accepted | 2026-06-22 |
| 0015 | Frontend chat request wire-format adapter (UIMessage → {role, content}) | accepted | 2026-06-22 |
| 0016 | Chat tool-error recovery: degrade LLM tool-call mistakes to isError, never 500 | accepted | 2026-06-22 |
| 0017 | Chat system prompt: server-side injection of a financial coach persona | accepted | 2026-06-22 |
| 0018 | Adopt Vercel template best practices for chat SSE | accepted | 2026-06-24 |
| 0019 | Markdown rendering with streamdown | accepted | 2026-06-24 |
| 0020 | Security hardening: CSRF, tool tier policy, and tool-output sanitization | accepted | 2026-06-28 |
| 0021 | Default transaction listing order: created_at desc | accepted | 2026-06-28 |
| 0022 | Chat SSE tool-output-error chunk | accepted | 2026-06-28 |
| 0023 | Outstanding queue: overdue + upcoming buckets | accepted | 2026-07-03 |
| 0024 | Postgres replaces SQLite (supersedes 0012) | accepted | 2026-07-03 |
| 0025 | Remove external MCP HTTP exposure | accepted | 2026-07-03 |
| 0026 | Local-only posture | superseded by 0030 (database clause) | 2026-07-05 |
| 0027 | URL query params as the filter source of truth | accepted | 2026-07-10 |
| 0028 | Bounded-query read path for monthly aggregates | accepted | 2026-07-22 |
| 0029 | Frontend async-state contract via QueryBoundary | accepted | 2026-07-22 |
| 0030 | Local Postgres container replaces Render as the production database | accepted | 2026-07-28 |
| 0031 | Read-time FX conversion from the single TRM value replaces frozen per-transaction snapshots | accepted | 2026-07-30 |
| 0032 | Stored transfer-leg direction enables atomic pair deletion | accepted | 2026-07-31 |
| 0033 | Migrations apply only at container start, never on autoreload | accepted | 2026-07-31 |
| 0034 | Skipping a planned payment is reversible | accepted | 2026-08-01 |
| 0035 | Passed due dates are offered for per-date acceptance, never backfilled silently | accepted | 2026-08-02 |
| 0036 | Per-charge commit replaces batch-atomic recurring materialization | accepted | 2026-08-02 |
| 0037 | A recurring item that ended is derived at read time; resuming offers the stretch left behind | accepted | 2026-08-02 |
| 0038 | Engine-made movements carry their own source, and deleting one closes its due date | accepted | 2026-08-02 |
| 0039 | Existing manual repeating incomes are migrated to automatic, their movements left alone | accepted | 2026-08-02 |
| 0040 | Strict ruff lint as a gate on the acceptance pipeline | proposed | 2026-08-02 |
| 0041 | Category presence is a type-discriminated constraint, not a blanket NOT NULL | proposed | 2026-08-03 |
| 0042 | A category belongs to one direction and one resolver answers which category a movement carries | proposed | 2026-08-03 |
