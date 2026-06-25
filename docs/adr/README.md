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
| 0010 | Deployment posture | accepted | 2026-06-22 |
| 0011 | MCP only over Tailscale | accepted | 2026-06-22 |
| 0012 | Litestream for continuous backup | accepted | 2026-06-22 |
| 0013 | Daily scheduler as a thin sidecar | accepted | 2026-06-22 |
| 0014 | Chat endpoint with LiteLLM and an in-memory MCP bridge | accepted | 2026-06-22 |
| 0015 | Frontend chat request wire-format adapter (UIMessage → {role, content}) | accepted | 2026-06-22 |
| 0016 | Chat tool-error recovery: degrade LLM tool-call mistakes to isError, never 500 | accepted | 2026-06-22 |
| 0017 | Chat system prompt: server-side injection of a financial coach persona | accepted | 2026-06-22 |
| 0018 | Adopt Vercel template best practices for chat SSE | accepted | 2026-06-24 |
| 0019 | Markdown rendering with streamdown | accepted | 2026-06-24 |
