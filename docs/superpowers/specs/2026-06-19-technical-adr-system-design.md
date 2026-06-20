# Quaestor — Technical ADR system (design)

**Date:** 2026-06-19
**Depends on:** —
**Part of:** repo infrastructure (not a P0–P7 sub-project)

---

## Goal

Give Quaestor a **complete system for technical Architecture Decision Records (ADRs)**: a versioned record of **engineering proposals and decisions** (libraries, DB schema, migrations, API/transport design, auth, testing strategy, etc.), kept separate from the **product decisions** record that already exists.

The deliverable isn't just a template: it's a **guardrail** so that any Claude agent working on Quaestor **records and respects** technical decisions instead of improvising. The always-on rule (CLAUDE.md) makes using the system mandatory; the skill defines how.

## Context and problem

- Today `docs/adr/2026-06-16-quaestor-adrs.md` gathers 24 "ADRs", but they are all **product decisions** (budget model, safe-to-spend, goals…). They are mislabeled as ADRs.
- There is no place to record **technical decisions**. When an agent decides (e.g.) how to do migrations or which library to use, the decision is lost or redone differently in the next session.
- The ADR community's recommended practice is to **separate** concerns: keep ADRs focused on the architectural/technical, and put product decisions in a separate record ("Significant Decision Record"). See `adr.github.io`, Martin Fowler (*Architecture Decision Record*), InfoQ (*Has Your ADR Lost Its Purpose?*).

## Design decisions (made during brainstorming)

| # | Decision | Rejected alternative |
|---|---|---|
| 1 | Technical ADRs live in `docs/adr/`, **one per file** (`NNNN-slug.md`) + an index `README.md` | A single growing file; a separate `docs/tdr/` |
| 2 | The product file is **moved** to `docs/decisions/product-decisions.md` to leave `docs/adr/` 100% technical | Leaving it in `docs/adr/` (clutter) |
| 3 | **Full MADR** format | Minimal (Nygard) |
| 4 | **One record per decision with a `status` field**: `proposed` = live proposal; `accepted/rejected` = decided | A two-stage RFC → record flow |
| 5 | Delivered as a versioned **project skill**: `quaestor/.claude/skills/adr/` | A global skill filtered by description |
| 6 | **Guardrail**: `CLAUDE.md` at the root points to the skill (always-on rule) | Skill only, no always-on rule |
| 7 | **Deterministic script** `new_adr.py` numbers + creates the file + updates the index | Creating the ADR and index by hand |
| 8 | The skill and ADR content in **English**; communication with the user in Spanish | — |

## Scope

**In:**
- Project skill `quaestor/.claude/skills/adr/` (SKILL.md, TEMPLATE.md, scripts/new_adr.py).
- `docs/adr/README.md` (index) and the folder ready for `NNNN-slug.md`.
- `CLAUDE.md` at the root of Quaestor (always-on technical rule).
- Move `docs/adr/2026-06-16-quaestor-adrs.md` → `docs/decisions/product-decisions.md`.

**Out:**
- Migrating/rewriting the 24 product ADRs (the file is only moved, untouched).
- Creating technical ADRs with real content (the system starts empty; ADRs are written when there are decisions).
- CI automation (ADR linting, pre-commit validation) — backlog.

## File structure

```
quaestor/
├── CLAUDE.md                       # NEW — always-on rule that points to the skill
├── .claude/skills/adr/
│   ├── SKILL.md                    # workflow + triggers + rules
│   ├── TEMPLATE.md                 # Full MADR template (English), copied by the script
│   └── scripts/
│       └── new_adr.py              # numbers, creates the file, updates the index
├── docs/adr/
│   ├── README.md                   # index: table no. · title · status · date
│   └── (empty; 0001-*.md, 0002-*.md, … land here)
└── docs/decisions/
    └── product-decisions.md        # the moved product file (24 ADRs untouched)
```

## Component: the `adr` skill

### Description (frontmatter)

```
name: adr
description: Record and govern technical/architecture decisions for Quaestor as
  Architecture Decision Records (ADRs) in docs/adr/. Use when making, proposing,
  or revisiting an architecturally-significant technical decision — choosing a
  library, DB schema or migration approach, API/transport design, auth, testing
  strategy — or when the user mentions ADR, decision record, or "why did we do X".
```

### Trigger criteria (what warrants an ADR)

The skill includes explicit guidance to avoid both over- and under-recording:

- **Warrants an ADR:** choosing a library/framework, migration strategy, DB schema shape, API or transport design (REST/MCP), auth model, testing strategy, module boundaries, decisions with a high reversal cost or consequences scattered across the code.
- **Does not warrant an ADR:** renaming variables, formatting, local refactors with no contract change, bug fixes, trivial or easily reversible decisions.

### Workflow (what the skill requires)

1. **Before proposing a technical change:** read `docs/adr/README.md` and the relevant `accepted` ADRs. If a decision is already made, respect it or record an ADR that **supersedes** it (don't silently contradict it).
2. **Create the ADR:** `uv run .claude/skills/adr/scripts/new_adr.py "<title>"` → generates `NNNN-slug.md` from `TEMPLATE.md` with status `proposed` and adds the row to the index.
3. **Fill in** context, drivers, considered options (with pros/cons), decision, and consequences.
4. **Decide:** change `status` to `accepted` (or `rejected`). If it replaces another ADR, mark the old one as `superseded by NNNN` and link both.
5. **Keep the index** in sync (the script does it on creation; on a status change, the row is updated).

### Hard rules (guardrails)

- **Stable** numbering: it is never renumbered; gaps left by `rejected` ADRs are preserved.
- An `accepted` ADR **is not edited** in its decision; it is superseded by a new one.
- Every ADR links to the spec/PR/issue that motivates it, when one exists.

## Component: Full MADR template (`TEMPLATE.md`)

Content in English. Structure:

```markdown
# NNNN. <short title of the decision>

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

<What is the issue we're seeing that motivates this decision? 2–4 sentences,
framed as a problem or a question.>

## Decision drivers

- <driver / force / constraint>
- <driver / force / constraint>

## Considered options

1. <option A>
2. <option B>
3. <option C>

## Decision outcome

Chosen option: **<option X>**, because <justification — how it best meets the
drivers>.

### Pros and cons of the options

**<option A>**
- Good, because <pro>
- Bad, because <con>

**<option B>**
- Good, because <pro>
- Bad, because <con>

## Consequences

- Good: <positive consequence>
- Bad / cost: <negative consequence, follow-up work, risk>

## Confirmation

<How do we verify the decision is implemented and respected? e.g. a test, a CI
check, a code review item, a doc.>
```

### States (lifecycle)

```
proposed ──► accepted ──► (deprecated | superseded by NNNN)
   └──────► rejected
```

- `proposed`: the file **is the proposal**, open for review.
- `accepted` / `rejected`: decided; same file.
- `deprecated`: no longer applies, with no direct replacement.
- `superseded by NNNN`: replaced by a newer ADR (both are linked).

## Component: index `docs/adr/README.md`

Table maintained by the script:

```markdown
# Architecture Decision Records (technical)

Technical/architecture decisions for Quaestor. Product decisions live in
`docs/decisions/product-decisions.md`.

| #    | Title | Status | Date |
|------|-------|--------|------|
| 0001 | <title> | accepted | YYYY-MM-DD |
```

## Component: script `scripts/new_adr.py`

Deterministic operation (Python 3.12 + uv, like the rest of Quaestor; no external dependencies, stdlib only).

- **Input:** the ADR title as an argument.
- **Steps:**
  1. Scan `docs/adr/NNNN-*.md`, compute the next number (4 digits, zero-padded; the maximum + 1).
  2. Generate a `slug` from the title (lowercase, hyphens, no accents).
  3. Copy `TEMPLATE.md` to `docs/adr/NNNN-slug.md`, substituting `NNNN`, title, and date. The date is taken from the system **at script run time** (not from the agent).
  4. Insert the row into the `README.md` table with status `proposed`.
- **Output:** the path of the created file (so the agent can open and fill it in).
- **Idempotency/safety:** if the slug already exists, it aborts without overwriting.

## Component: guardrail `CLAUDE.md`

Quaestor has no `CLAUDE.md` today. One is created with a short, always-loaded rule (the rest of the file can grow later):

```markdown
## Technical decisions

Any architecturally-significant technical decision (library choice, DB schema,
migrations, API/transport design, auth, testing strategy) MUST be recorded as an
ADR in `docs/adr/` using the `adr` skill. Before proposing a technical change,
read the existing ADRs in `docs/adr/` and respect accepted ones (supersede with a
new ADR instead of silently contradicting them).

Product decisions live in `docs/decisions/product-decisions.md` — do not mix them
into `docs/adr/`.
```

## Migrating the product file

- `git mv docs/adr/2026-06-16-quaestor-adrs.md docs/decisions/product-decisions.md`.
- Content **untouched** (the 24 product ADRs stay the same; only the folder changes).
- Update any internal reference if one exists (check specs that cite the old path).

## Validation

- **Script:** a test run creates `0001-*.md` with the correct number, registers it in the index, and a second run produces `0002`. Delete the test files when done.
- **Skill:** verify that the `description` triggers in the target scenarios (mentioning "ADR", "decision record", choosing a library).
- **Guardrail:** confirm `CLAUDE.md` ends up at the root and the rule is readable.
- **Migration:** `docs/adr/` is left without the product file; `docs/decisions/product-decisions.md` exists with the 24 ADRs.

## Implementation plan (high level)

1. Create `quaestor/.claude/skills/adr/` with SKILL.md, TEMPLATE.md, and scripts/new_adr.py.
2. Create `docs/adr/README.md` (empty index) and `docs/decisions/`.
3. Move the product file with `git mv`.
4. Create/add the technical rule in `CLAUDE.md`.
5. Test the script (create and delete a test ADR), commit.

The step-by-step detail is produced by the `writing-plans` skill.
