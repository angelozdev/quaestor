---
name: adr
description: Record and govern technical and architecture decisions for Quaestor as Architecture Decision Records (ADRs) in docs/adr/. Use when making, proposing, or revisiting an architecturally-significant technical decision — choosing a library or framework, DB schema or migration approach, API/transport design, auth model, testing strategy, module boundaries — or when the user mentions ADR, decision record, or asks "why did we do X".
---

# ADR — Technical Decision Records

Technical decisions for Quaestor are recorded as ADRs in `docs/adr/`, one file per
decision (`NNNN-slug.md`), indexed in `docs/adr/README.md`. Product decisions live
in `docs/decisions/product-decisions.md` — never mix them here.

## When to write an ADR

**Write one for** an architecturally-significant decision:
- library / framework choice
- DB schema shape or migration strategy
- API or transport design (REST / MCP)
- auth model
- testing strategy
- module boundaries
- anything with a high reversal cost or consequences spread across the code

**Do NOT write one for** trivial or easily reversible changes: variable renames,
formatting, local refactors with no contract change, or bug fixes.

## Before proposing a technical change

1. Read `docs/adr/README.md` and the relevant `accepted` ADRs.
2. If a decision is already made, respect it — or write a new ADR that supersedes
   it. Never silently contradict an accepted ADR.

## Create an ADR

```bash
uv run .claude/skills/adr/scripts/new_adr.py "<title>"
```

This picks the next stable number, creates `docs/adr/NNNN-slug.md` from
`TEMPLATE.md` in status `proposed`, and adds a row to the index. Open the printed
file and fill in: context, decision drivers, considered options (with pros/cons),
decision outcome, consequences, confirmation.

## Lifecycle (the `Status` field)

```
proposed ──► accepted ──► (deprecated | superseded by NNNN)
   └───────► rejected
```

- `proposed`: the file IS the live proposal, open for review.
- `accepted` / `rejected`: decided. Update the `Status` field and the index row.
- When a new ADR replaces an old one: set the old one's `Superseded by:` to the
  new number, set the new one's `Supersedes:` to the old number, and update both
  index rows.

## Hard rules

- Numbering is stable — never renumber. Keep gaps from rejected ADRs.
- Do not edit the decision of an `accepted` ADR; supersede it with a new one.
- Keep `docs/adr/README.md` in sync when a status changes.
