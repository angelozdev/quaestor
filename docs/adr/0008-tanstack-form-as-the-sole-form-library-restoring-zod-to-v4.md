# 0008. TanStack Form as the sole form library, restoring zod to v4

- **Status:** accepted
- **Date:** 2026-06-21
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

We are migrating Quaestor's forms from untyped inline `useState` blocks to a
schema-driven form library backed by zod. The first attempt (committed in
`docs/superpowers/plans/2026-06-21-zod-form-validation.md`, see commits
`6c69363`..`e6b88a7`) adopted **react-hook-form 7.80 + @hookform/resolvers/zod
5.4.0** and was forced to **downgrade zod from v4.4.3 to v3.25.76** (commit
`497e515`) because the resolver's TypeScript overloads could not disambiguate
zod v4 schemas (`Type '4' is not assignable to type '0'` for
`_zod.version.minor`). We were already mid-migration (5 of 10 forms done) when
the incompatibility surfaced. Staying on zod v3 means giving up the v4 release
we originally targeted (better TS inference, smaller bundle, schema-method
ergonomics); staying on react-hook-form ties us to a single-maintainer library
whose integration story with our zod version is fragile. We need a form
library that supports zod v4 today.

## Decision drivers

- **zod v4 support is a hard requirement** — we want the newer API; downgrading
  zod was a workaround, not a destination.
- **Same author family as React Query** (already in the stack at
  `@tanstack/react-query ^5.101.0`) keeps mental model and support channels
  consistent.
- **Headless, design-system agnostic** — must respect ADR-0002's
  `ui/` module boundary (no form library leaks into `ui/`).
- **TS-first** — strict mode, no `any` escape hatches in the library API.
- **Schema-driven validation** — zod schemas are the single source of truth;
  the library should consume them, not duplicate them.
- **Reversibility** — the decision should be reversible; we should not be
  locked into a library that owns our render output (rules out Formik-style
  `<Formik>` + `<Field>` components).

## Considered options

1. **react-hook-form 7.80 + zod v3.25.76** (status quo): rhf works fine with zod
   v3, all 5 migrated forms pass tests. We stay on zod v3 forever.
2. **react-hook-form 7.80 + zod v4.4.3 (no resolver)**: hand-write a
   `validate` function per form that calls `schema.safeParse` and maps errors
   to rhf's `FieldError` shape. ~30 lines of boilerplate per form, no shared
   helper.
3. **TanStack Form 1.33.0 + zod v4.4.3 + custom validator**: install
   `@tanstack/react-form`; write a 10-line helper that wraps `safeParse` and
   returns TanStack's `validationError` shape (`{ fields: Record<string, string> }`).
   No adapter package — `@tanstack/zod-form-adapter` 0.42.1 still pins `zod ^3.x`
   in peer deps (verified via `npm view` on 2026-06-21).
4. **Formik + formik-validator-zod**: Formik's zod support is third-party and
   pinned to zod v3. Same incompatibility, plus Formik is in maintenance mode.
5. **No library (custom `useState` + `safeParse`)**: drop the form library
   entirely. Every form re-implements dirty/touched/async state tracking.
   Highest cost, no upside.

## Decision outcome

Chosen option: **3 — TanStack Form 1.33.0 + zod v4.4.3 + per-form custom
validator function**, because it uniquely satisfies all decision drivers:

- zod v4 supported today (no peer-dep conflict).
- Same author family as React Query already in use.
- Headless — `ui/` boundary preserved.
- TS-first API; no `any` escapes.
- Schema-driven via the shared `frontend/lib/schemas/primitives.ts` and
  `frontend/lib/schemas/messages.ts` modules.
- One small validator helper replaces every per-form `safeParse` call.

**No third-party resolver/adapter packages** are adopted:

- `@hookform/resolvers/zod` is removed — it pinned zod v3 and was the root
  cause of the original version conflict.
- `@tanstack/zod-form-adapter` is **also not** adopted: it currently pins
  `zod ^3.x` in peer dependencies (verified via `npm view` on 2026-06-21)
  and would re-create the same conflict we just escaped.

TanStack Form's `validators` slot accepts `StandardSchemaV1<TFormData, unknown>`
directly, and **zod v4 implements `StandardSchemaV1`** (verified on
2026-06-21 — zod exports `version: 1` and a `validate(value)` method per the
standard schema spec). So the validator is just the zod schema itself —
there is no helper to write, no `safeParse` wrapper, no peer-dep conflict:

```ts
const form = useForm({
  defaultValues: { ... },
  validators: { onChange: myZodSchema },
})
```

Spanish messages flow through zod's chain-level message options
(`.regex(/.../, messages.mesInvalido)`); TanStack surfaces them via
`field.state.meta.errors` and `form.state.errors`.

**Schemas live in sibling files, not inside components.** Each form's zod
schema is defined in a dedicated `*.schema.ts` next to the page/component
(e.g. `frontend/app/(app)/recurring/recurring.schema.ts` for the recurring
page), not co-located with the JSX. This keeps the component file focused on
rendering and form-state wiring; the schema, its inferred `Values` type, and
its error-mapping live in one place that the form imports.

### Pros and cons of the options

**Option 1 — rhf + zod v3 (status quo)**
- Good: zero migration cost (5 forms already done); rhf is mature and well-known.
- Bad: locks us into zod v3 forever; we lose v4's TS inference improvements;
  rhf + resolvers v4-vs-v3 ambiguity was the root cause of the original bug;
  no alignment with the TanStack family we already use.

**Option 2 — rhf + zod v4 + hand-written validator**
- Good: keeps rhf, gets zod v4.
- Bad: ~30 lines of `safeParse`/error-mapping boilerplate per form (5 migrated
  forms × 30 = 150 lines of noise); custom validator must be kept in sync with
  rhf's `FieldError` shape; no library upgrade ever lifts it.

**Option 3 — TanStack Form + zod v4 + custom validator** ✅
- Good: zod v4 supported; TanStack family; headless; TS-first; one 10-line
  helper replaces all per-form boilerplate; forward-compatible with future
  official adapter.
- Bad: re-implements the 5 migrated forms; team learns TanStack Form's API;
  `validators.onChange` API is per-field (slightly different ergonomics than
  rhf's form-level `resolver`).

**Option 4 — Formik**
- Good: mature.
- Bad: in maintenance mode; zod adapter pinned to v3; couples render to
  `<Formik>`/`<Field>` components (violates "reversibility" driver).

**Option 5 — No library**
- Good: zero deps.
- Bad: every form reinvents dirty/touched/async tracking; no schema-driven
  validation; higher long-term cost.

## Consequences

- **Good:** zod restored to `^4` (originally `4.4.3`); one form library
  aligned with the TanStack family; `frontend/lib/schemas/` modules stay the
  single source of validation truth.
- **Good:** Form-level + field-level validation in a single API
  (`validators: { onChange, onBlur }`).
- **Bad / cost:** The 5 forms already migrated to react-hook-form in
  commits `9b36235`..`e6b88a7` (recurring create+edit, transaction
  create+edit, budgets) must be re-migrated to TanStack Form. The `FormField`
  component (commit `7652d57`) must be rewritten against TanStack's
  `useStore` + `field.state.meta` API. The `@hookform/resolvers/zod` and
  `react-hook-form` packages must be removed from `frontend/package.json`.
- **Bad / cost:** Tasks 11–18 in the current plan (goals, settings FX,
  to-pay, entity-form-dialog, backend constraints, axios `field`, final
  polish) all need to be retargeted from rhf to TanStack Form; the plan file
  should be revised before resuming execution.
- **Risk:** TanStack Form's `validators` API is younger than rhf's; if a
  sharp edge surfaces mid-migration we fall back to Option 2 (hand-written
  validator on rhf) — never to dropping zod v4.

## Confirmation

- `pnpm tsc --noEmit` in `frontend/` stays clean with zod `^4` and TanStack
  Form installed.
- `pnpm test --run` runs the existing `frontend/lib/schemas/` and FormField
  test files green; new tests cover the FormField ↔ TanStack wiring.
- `pnpm biome check` clean across all touched files.
- `grep -r "react-hook-form\|@hookform\|zod-form-adapter" frontend/` returns
  zero matches (proves the swap is complete and no resolver/adapter is in use).
- `grep "zod" frontend/package.json` returns `^4.x`.
- A minimal smoke test mounts `useForm({ validators: { onChange: schema } })`
  with a `z.object({...})` schema from `frontend/lib/schemas/primitives.ts`
  and asserts the error string surfaces in `field.state.meta.errors`. This
  proves the StandardSchemaV1 wiring end-to-end without a custom helper.
- Every form's schema lives in a sibling `*.schema.ts` file, not inside the
  component; verified by listing `frontend/app/(app)/**/*.schema.ts` and
  `frontend/components/**/*.schema.ts` and confirming the corresponding
  component imports its schema from that file.
