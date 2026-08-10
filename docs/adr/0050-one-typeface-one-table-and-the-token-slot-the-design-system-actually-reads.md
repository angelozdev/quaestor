# 0050. One typeface, one table, and the token slot the design system actually reads

- **Status:** accepted
- **Date:** 2026-08-10
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The owner asked for a design that is "mucho más intuitivo/elegante/minimal", and
after being offered two distinctive visual worlds he deliberately took the
standing exit: the category standard, played straight, with **Linear and Stripe**
as the craft bar (recorded as a brand commitment in `PRODUCT.md`, and as the
visual authority in `DESIGN.md`). Replacing the look is a matter of token values
and composition, which ADR 0002 already governs. Three things it uncovered are
not: which font dependencies the frontend carries, which CSS variable the app is
supposed to override to install them, and whether each screen may keep writing
its own table.

Measured while doing the work: `document.fonts.check('16px Inter')` returned
`false` with every Inter face `unloaded`, and the headline computed to
`ui-sans-serif` — **no body font had ever been applied**, in either the old look
or the new one. And `DataTable` (`frontend/components/data-table.tsx`), built for
this purpose, had **zero consumers among the twelve screens**: six of them
hand-rolled a `<table>` with their own padding, border, empty state and loading
skeleton.

## Decision drivers

- **Respect ADR 0002.** Re-skinning provides values from the app; `ui/` internals
  are not edited to make a screen look right.
- **Uphold ADR 0004.** Dark stays the default, both themes stay authored, and
  elevation stays a single token pair defined per theme in `app/globals.css`.
- **The app is 90% figures.** Whatever typeface is chosen has to lock numeric
  columns without per-column work, or every table needs hand-tuning.
- **One reading per concept.** The owner is the only user; two behaviours for the
  same component cost him a second reading to learn, which is worse than either.
- **DRY, KISS, low coupling, high cohesion** — restated by the owner mid-task as
  the standing bar for this work.
- **The acceptance surface is a contract.** Frontend ACs bind to vitest
  (ADR 0045); a visual change may not quietly rewrite what they assert.

## Considered options

1. **One family (Inter), the `--font-sans-stack` slot, and one `DataTable` with a
   presentation option.**
2. **Keep two families** (a display face beside the body face) and fix only the
   variable name.
3. **Geist Sans + Geist Mono** as the single type system.
4. **Absorb all six tables into `DataTable`**, adding whatever options each screen
   needs.
5. **Leave the six tables alone** and only restyle them in place.

## Decision outcome

Chosen option: **option 1**, in three clauses.

**One typeface: Inter, and no display face.** Verified against Inter's own
documentation rather than a secondary source: `tnum` gives tabular figures, which
is the actual reason — it locks every amount column to one width so `$ 0` and
`$ 5.681.641` stack without drift. The slashed zero (`zero`, or the `ss02`
disambiguation set) is deliberately **left off**: it reads as engineering, and
this surface is finance. Manrope and Bricolage Grotesque are dropped, so the
frontend carries one font dependency instead of two.

**The app overrides `--font-sans-stack`, never `--font-sans`.** `ui/styles/tokens.css`
maps `--font-sans` inside `@theme inline`, which means Tailwind inlines it into
utilities and never emits it as a custom property; the slot an app is meant to
provide is `--font-sans-stack`, exactly as that file's own comment says. The app
had been setting `--font-sans` since ADR 0004, which is why no body font ever
loaded. This is a correction of app-side usage, not a change to the `ui/`
contract.

**One table, with a presentation option.** Every screen whose rows are single-line
records moves onto `DataTable`: the four masters, recurrentes, and both tables in
reportes. It gains exactly one new prop — `actionsAs: "menu" | "inline"` — because
how a row's actions are *presented* is a per-screen call while what they *are* is
not: a long list with many columns hides them behind one overflow control, and a
short master list where acting is the point keeps them in the row. **Fondos stays
out on purpose:** its rows are four-line records, and absorbing it would have cost
four more options (top alignment, per-row `aria-label`, per-shape empty state,
`aria-labelledby`) — the abstraction serving itself. It carries the same visual
rules without being forced through the shared component.

Two consequences of the same "one reading" driver, decided here because they
change what a figure means:

- **Money going out carries no colour.** Spending is the default case on every
  screen, so tinting it coloured almost every figure and discriminated nothing —
  ten red amounts in a row on Transacciones. Red is now reserved for what is
  *wrong* (an overdue date, a negative net, a fund spent past what it had) and
  green for the exception, money coming in. One rule, applied once in
  `MoneyAmount`.
- **Surfaces are flat.** `--shadow-card` is redefined as a 1px hairline ring, so
  every existing call site becomes the flat treatment with no edit. ADR 0004's
  mechanism is untouched — one token pair, per theme, in `app/globals.css`; only
  its value changed. `--shadow-pop` still carries offset and blur for what
  genuinely leaves the page plane.

### Pros and cons of the options

**1. One family, the real slot, one table with a presentation option**
- Good, because the font bug cannot recur silently: the variable that is set is the
  variable that is read.
- Good, because one table means padding, hover, header rule, pagination and the
  empty/loading/error states are changed in one file, and the diff removed ~350
  more lines than it added.
- Good, because `actionsAs` preserves each screen's existing behaviour, so the
  vitest suite kept passing through the conversion.
- Bad, because one component now serves seven screens: a careless change to
  `DataTable` breaks all of them at once. The suite is the guard.
- Bad, because Fondos is an admitted exception, and an exception invites the next
  one.

**2. Keep two families**
- Good, because the display face gives headings a voice of their own.
- Bad, because a second, expressive family is what makes a money app read as a
  brand exercise, and the owner's chosen bar has no display face.
- Bad, because it keeps a font dependency that was never loading.

**3. Geist Sans + Geist Mono**
- Good, because it is one type system covering prose and figures, tuned for
  density and free to self-host.
- Bad, because its register is developer-facing and technical, and Inter's
  tabular numerals are the documented reason for the choice.

**4. Absorb all six tables**
- Good, because there would be no exception to explain.
- Bad, because Fondos would push four options into a shared component to serve one
  caller — precisely the coupling this decision exists to avoid.

**5. Leave the six tables alone**
- Good, because zero regression risk on 440 tests.
- Bad, because six copies of one treatment is the largest DRY breach in the
  frontend, and every future table look has to be applied six times.

## Consequences

- Good: one font dependency, one typeface, one table, one colour rule, one
  container measure. `DESIGN.md` is the single visual authority and the direction
  contract lives inside it — **not** as a comment in the emitted markup, because
  `CLAUDE.md` prohibits code comments project-wide and that instruction outranks
  the tool's default placement.
- Good: three decorative devices are gone rather than tuned — gradient text, the
  zero-offset glow behind the headline, and the hover lift — plus the staggered
  entrance on every block.
- Good: it closed **D2** of the August UX audit on the way past. Ajustes claimed a
  "job diario" refreshes the TRM; that job does not exist (roadmap
  `daily-trm-fetch`) and "job" is jargon on a human screen. It now tells the
  truth, and the rate reads `$ 3.142,00` instead of `3100.000000`.
- ~~Bad / cost: `ui/styles/tokens.css` still documents `--font-sans` as the value
  an app overrides, which is the sentence that caused the bug.~~ **Paid, on
  acceptance:** the contract now names the `-stack` slots and states the
  indirection outright, so the trap is written down where the next reader meets
  it. Docstring only — no contract change, no component internals touched.
- Bad / cost: `PRESUPUESTOS` and `FONDOS` remain shouting in all-caps. That copy
  is asserted by eight vitest assertions pinning feature 010's vocabulary
  (product ADR-042), so lowering it needs the owner's decision, not a designer's.
- Bad / cost: two test locators in `reports/page.test.tsx` walked with
  `closest("div")` to a card wrapper that no longer exists and were re-anchored to
  `closest("section")`. AC-36's intent is unchanged; only the anchor moved. In the
  breakdown the subtraction operator is rendered as a separate muted glyph
  precisely so AC-4's asserted figures stay the strings they were.
- Bad / cost: the pre-commit biome hook did not run for the commits that carried
  this decision; the checks were run by hand instead. **Fixed on acceptance:** the
  installed hook held an absolute path into a deleted worktree, and the
  `LEFTHOOK_CONFIG` indirection was never carried into the hook at run time, so
  the config moved to the repo root with `root: frontend/`. Putting it back to
  work exposed two errors that had been latent for as long as the hook had been
  dead — `glob_strict` is not valid in lefthook 2.1.9, and `biome check --files`
  is not a flag in biome 2.5.0. **A gate nobody watches fail is a gate that has
  already rotted**, which is the same lesson ADR 0001's language rule warns about
  and ADR 0040 answered by making lint a pipeline gate.

## Confirmation

- `frontend/app/layout.tsx` loads exactly one `next/font/google` family, and
  `app/globals.css` sets `--font-sans-stack`. A regression shows up as
  `document.fonts.check('16px Inter') === false`, which is how the original bug
  was found.
- `grep -c '<table' frontend/app/**/page.tsx` stays at 1 (Fondos). A second
  hand-rolled table is the signal this decision eroded.
- `DESIGN.md` carries the named rules the render is audited against — the Default
  Case Rule for colour, the Flat Surface Rule for depth, the Tabular Rule for
  figures, the Quiet Label Rule for labels.
- The suite: `pnpm exec tsc --noEmit`, `pnpm exec biome check`, and
  `pnpm exec vitest run` — 440 tests passing at the time of this decision.
