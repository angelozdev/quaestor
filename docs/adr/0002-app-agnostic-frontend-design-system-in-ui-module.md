# 0002. App-agnostic frontend design system in `ui/` module

- **Status:** accepted
- **Date:** 2026-06-20
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The frontend mixes two kinds of components in `components/`: app-agnostic UI
primitives (shadcn/Base UI: `button`, `card`, `input`, `table`, …) and
domain-specific components that import application code (`money-amount` imports
`@/lib/api`, plus `to-pay-widget`, `app-shell`). Nothing stops a "reusable"
primitive from reaching into `@/lib` or `@/app`, so the presentation layer drifts
toward coupling with Quaestor's domain. We want a design system that is so
decoupled it could be lifted into another app with effectively no changes. Where
should it live, and how do we keep it agnostic over time?

## Decision drivers

- **Portability:** the design system must depend only on React, Tailwind, and
  generic UI libraries — never on app/domain code — so it can be copied to another
  app or extracted to a package later.
- **Enforceability:** "stay agnostic" must be a mechanical check, not a code-review
  argument, or it will erode like ADR 0001's language rule warns.
- **Low migration cost:** the existing primitives are already agnostic; the move
  should not require rewriting them or churning the whole app's imports.
- **Tooling fit:** the stack uses shadcn (`components.json`) and Tailwind v4 theme
  tokens; the chosen layout should keep `shadcn add` working and tokens coherent.
- **Reversibility / future-proofing:** today one app consumes it, but the structure
  should map 1:1 onto a workspace package (the repo already has a pnpm workspace)
  with zero code changes if/when that is warranted.

## Considered options

1. **Dedicated `ui/` folder with an enforced ESLint import boundary**, self-contained
   (own `cn`, own design-token contract), aliased `@/ui`.
2. **Extract a workspace package now** (`packages/ui`, `@quaestor/ui`) with its own
   `package.json`, build, and tsconfig — a hard boundary via the dependency graph.
3. **Convention only** — a folder plus a README saying "don't import app code", no
   automated enforcement.
4. **Status quo** — keep growing `components/ui/` (shadcn default) with no boundary.

## Decision outcome

Chosen option: **a dedicated `ui/` folder with an enforced ESLint import boundary,
self-contained**, because it satisfies every driver at once: it is portable (the
folder depends only on React/Tailwind/UI libs and owns its `cn` + token contract),
its agnosticism is enforced mechanically (`no-restricted-imports` blocks `@/app`,
`@/lib`, `@/components`, `@/hooks` from `ui/**`), the migration is cheap (the
already-agnostic primitives move as-is, only their `cn` import changes), and the
layout maps directly onto a future `packages/ui` with no code changes. The package
option (2) buys a harder boundary but adds build/versioning/tsconfig overhead that
is not justified for a single consumer; the lint boundary gives ~the same guarantee
at a fraction of the cost and is the documented upgrade path to (2). Options (3)
and (4) fail the enforceability driver and guarantee the coupling drift this
decision exists to prevent.

**Shape of the decision:**

- **Location & name:** a top-level `ui/` directory in `frontend/`, imported as `@/ui`.
- **Self-contained:** the module ships its own `cn` (`ui/lib/cn.ts`) and defines its
  **design tokens as a documented CSS-variable contract** (`ui/styles/tokens.css`:
  the Tailwind `@theme inline` mapping + a neutral default `:root` theme). The app
  *provides values* for those variables and may override them; it does not own them.
- **Boundary:** an ESLint config block scoped to `ui/**/*` forbids importing
  `@/app`, `@/lib`, `@/components`, and `@/hooks`. The DS may import React, generic
  UI libraries, and its own internals only.
- **Domain stays out:** domain tokens (`--income`, `--expense`) and domain
  components (`money-amount`, `to-pay-widget`, `app-shell`) remain in the app under
  `components/` and `app/globals.css`. The `ui/` boundary is what keeps them apart.
- **shadcn alignment:** `components.json` aliases point `ui` → `@/ui/components` and
  `utils` → `@/ui/lib/cn`, so `shadcn add` drops new primitives straight into the DS.

### Pros and cons of the options

**Dedicated `ui/` folder + ESLint boundary (chosen)**
- Good, because the boundary is enforced in lint/CI, not by reviewer vigilance.
- Good, because it is self-contained and extractable to a package with no code edits.
- Good, because migration is mechanical: move primitives, repoint `cn`, done.
- Bad, because the boundary is a lint rule, not a dependency-graph guarantee — a
  developer can disable the rule inline (visible in review).
- Bad, because the self-contained `cn` and token contract duplicate a little of what
  the app already had (`lib/utils.ts`, `globals.css`).

**Workspace package now (`packages/ui`)**
- Good, because the boundary is structural — the package literally cannot see app code.
- Bad, because it adds a build step, separate tsconfig, and versioning for a single
  in-repo consumer; premature for the current stage.

**Convention only**
- Good, because it costs nothing up front.
- Bad, because it has no teeth — coupling creeps back in exactly as it has already.

**Status quo (`components/ui/`)**
- Good, because it is the shadcn default and needs no move.
- Bad, because primitives and domain components share a tree with no boundary, which
  is the problem being solved.

## Consequences

- Good: a clearly-bounded, portable design system; agnosticism is a CI-checkable
  invariant; the path to a `packages/ui` workspace package is a lift-and-shift.
- Good: tokens become an explicit contract, so theming/re-skinning is a matter of
  overriding CSS variables rather than editing component internals.
- Bad / cost: a small amount of duplication (`cn`, default tokens) and an extra
  import boundary to keep configured; future contributors must learn that `ui/`
  cannot import app code and that new domain components do **not** belong there.
- Migration: the 8 existing primitives move from `components/ui/` to `ui/components/`;
  `app/providers.tsx`, `app/globals.css`, `components.json`, and `lib/utils.ts` are
  repointed. All identifiers stay English per ADR 0001.

## Confirmation

- An ESLint config block scoped to `ui/**/*` (`no-restricted-imports` against `@/app`,
  `@/lib`, `@/components`, `@/hooks`) fails `pnpm lint` / CI if the DS imports app or
  domain code. This is the primary automated guard.
- Code-review checklist: new code under `ui/` must be domain-agnostic; new
  domain-specific components belong in `components/`, not `ui/`.
- `ui/README.md` documents the boundary, the token contract, and the
  extraction-to-package upgrade path, and is the reference the rule points to.
