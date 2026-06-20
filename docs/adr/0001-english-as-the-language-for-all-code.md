# 0001. English as the language for all code

- **Status:** accepted
- **Date:** 2026-06-19
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The team and its tooling (Claude Code, ADRs, the skill library) already operate in
English, but the working language of the project's contributors is Spanish, so
without a stated rule the codebase drifts toward mixed-language identifiers and
comments. Which natural language should all code be written in, and how broadly
does that rule apply?

## Decision drivers

- Consistency: a single language removes the cognitive cost of switching and
  prevents half-translated names like `getUsuarioById`.
- Tooling and ecosystem: language keywords, standard libraries, and third-party
  APIs are English; matching them keeps names uniform.
- Collaboration and AI assistance: English is the lingua franca for open source
  and for the LLM tooling this project leans on, maximizing future
  reviewer/contributor reach.
- Reviewability: an explicit rule can be enforced in code review instead of being
  argued case by case.

## Considered options

1. English for all code (identifiers, comments, docstrings, internal log/error
   messages, test names, commit messages).
2. Spanish for all code.
3. No rule — let each contributor choose.

## Decision outcome

Chosen option: **English for all code**, because it best satisfies every driver
above: it is the language of the keywords and libraries the code already uses, it
gives the widest collaboration and AI-tooling reach, and as a single explicit rule
it is trivially enforceable in review. The other options either fight the
ecosystem (Spanish) or guarantee the inconsistency this decision exists to
prevent (no rule).

**Scope.** "Code" means everything inside source files: identifiers (variables,
functions, classes, modules), comments, docstrings, internal log and error
messages, and test names — plus commit messages and branch names. **Out of
scope:** user-facing copy (UI strings, end-user-facing API messages). Those are a
localization concern and may be authored in any language or routed through i18n;
they are not governed by this ADR.

### Pros and cons of the options

**English for all code**
- Good, because it aligns identifiers with the English keywords and APIs the code
  already calls.
- Good, because it maximizes reach for future contributors, reviewers, and LLM
  tooling.
- Bad, because contributors whose first language is Spanish carry a small
  translation overhead when naming domain concepts.

**Spanish for all code**
- Good, because it matches the contributors' first language and domain vocabulary.
- Bad, because it clashes with English keywords/APIs, producing mixed-language
  lines, and narrows the contributor and tooling pool.

**No rule**
- Good, because it imposes nothing up front.
- Bad, because it guarantees mixed-language drift and turns every review into an
  ad-hoc language debate.

## Consequences

- Good: one language across the codebase; naming reviews become mechanical, and
  the code reads uniformly against its English dependencies.
- Bad / cost: a translation burden on Spanish-first contributors for domain terms,
  and existing non-English identifiers/comments must be migrated as they are
  touched.

## Confirmation

Enforced as a code-review checklist item: a reviewer rejects any new non-English
identifier, comment, docstring, log/error message, test name, or commit message.
This ADR is the reference the rule points to. A linter rule (e.g. flagging
non-ASCII identifiers) may be added later to automate the check.
