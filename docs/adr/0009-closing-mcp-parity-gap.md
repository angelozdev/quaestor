# 0009 — Closing the MCP Parity Gap

- **Status:** accepted
- **Date:** 2026-06-21

## Context

ADR-0006 mandates that every new HTTP write ships a sibling MCP tool. The P2
MCP server was launched before ADR-0006 was in force, so the existing tools
(24) cover only part of the backend's HTTP surface (~52 endpoints). 28
backend capabilities — masters CRUD, transaction updates/deletes/get, settings
read/write, budgets reads, recurring restore, goals reads, and the monthly
report — are reachable from the web UI but not from MCP agents.

## Decision

Ship the missing 28 MCP tools in one batch, plus a `delete_recurring` →
`archive_recurring` rename for consistency with ADR-0005's archive vocabulary.

The batch uses a hand-written parallel structure (one tool module per domain
area) instead of codegen-from-OpenAPI, because:

1. We are closing a one-time gap, not building a long-term parity mechanism.
2. Codegen introduces a second adapter layer that can drift from the existing
   service layer it is supposed to mirror.
3. ADR-0006 already covers future additions — a manual `<verb>_<noun>` tool
   per HTTP write keeps the invariant easy to enforce in code review.

Excluded from MCP (by design, not by omission):

- `POST /api/rollover` — scheduler-only trigger per ADR-017.
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` — MCP
  authenticates via bearer token; password login lives behind the frontend
  cookie session.

## Consequences

- Tool count grows from 24 to 52. Each tool has a stable, named verb and a
  precise input model, so discoverability improves, not degrades.
- The implementation plan (`docs/superpowers/plans/2026-06-21-mcp-parity-gap-closure.md`)
  ships the gap closure as 13 reviewable tasks with TDD throughout.
- ADR-0006's invariant becomes enforceable at code review: any new HTTP write
  merged without a sibling MCP tool can be flagged against this ADR plus
  ADR-0006.
- The `delete_recurring` → `archive_recurring` rename is a breaking change for
  any external MCP caller; no such caller exists in this repository as of
  2026-06-21.
- Follow-up ADR may codegen MCP tools from FastAPI's OpenAPI schema; that work
  is explicitly out of scope here.

## Related

- ADR-0005 — soft-delete + restore as the uniform lifecycle for masters,
  recurring, and goals.
- ADR-0006 — every new HTTP write ships a sibling MCP tool.
- Spec: `docs/superpowers/specs/2026-06-21-mcp-parity-gap-closure-design.md`.
