# Quaestor — agent rules

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
