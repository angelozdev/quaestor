# Quaestor — agent rules

## No code comments

Adding comments to code is PROHIBITED, project-wide. If a comment feels
necessary, the code is not self-documenting enough — refactor instead:
better names, smaller functions, clearer structure, DRY. Applies to all
new and modified code (backend, frontend, scripts, tests).

Docstrings on public modules/functions follow the existing codebase
convention and are allowed — kept lean (what/args/raises), never used to
excuse unclear code.

## Technical decisions

Any architecturally-significant technical decision (library choice, DB schema,
migrations, API/transport design, auth, testing strategy, module boundaries) MUST
be recorded as an ADR in `docs/adr/` using the `adr` skill.

Before proposing a technical change, read the existing ADRs in `docs/adr/` and
respect accepted ones — supersede with a new ADR instead of silently
contradicting them.

Product decisions live in `docs/decisions/product-decisions.md`. Do not mix them
into `docs/adr/`.

## Verify against current industry practice

The user has limited backend/architecture experience, so they rely on Claude
to consult current industry sources before answering technical questions.

When the user asks about libraries, patterns, schema design, APIs, security,
performance, tooling, or any other technical topic, verify against current
industry best practices on the internet — don't rely solely on prior knowledge.

Use the available skills:

- `grill-with-docs` for single-source deep-dive
- `deep-research` for multi-source verified research
- `claude-api` for Claude/Anthropic-specific questions
- `WebSearch` / `WebFetch` for general lookups

This applies BEFORE recommending a library, proposing an architecture, or
stating what is "the right way" to do something.

## Acceptance Tests

Acceptance specs are `spec.md` files (standard Gherkin) under
`features/NNN-slug/`.

### Pipeline

```
spec.md → dae_gherkin.py → .build/spec.json (IR) → acceptance/generator.py → pytest
```

1. **Parse:** `dae_gherkin.py` (portable, shipped with the DAE plugin) —
   `spec.md` → `<feature>/.build/spec.json`
2. **Generate:** `python3 acceptance/generator.py <feature-dir>` — reads the
   IR, emits pytest files into `<feature>/.build/generated/`
3. **Run:** `cd backend && uv run pytest <feature>/.build/generated/` —
   host-side, in-memory SQLite (fresh DB per scenario)

Full pipeline: `./run-acceptance-tests.sh [feature-dir ...]` (no args = every
feature that has a `spec.md`).

Step handlers live in `acceptance/handlers/` and bind step text to the
services layer (`backend/src/quaestor/services/…`). The generator and
handlers are committed source; everything under `.build/` is a regenerated
artifact.

### Rules

- Never modify a `spec.md` without explicit permission.
- Never modify generated tests under `.build/generated/` — only delete and
  regenerate via the pipeline (`./run-acceptance-tests.sh`).
- `.build/` is gitignored — do not commit the IR or generated tests.
- Before a push, run the full acceptance test pipeline.
- On failure, report the `spec.md` and the failing scenario name (the
  generated tests already include both in the assertion message).
- During ATDD red phase, failing acceptance tests are the expected state —
  do not "fix" handlers to make them pass; implement the feature.
