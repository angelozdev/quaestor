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
