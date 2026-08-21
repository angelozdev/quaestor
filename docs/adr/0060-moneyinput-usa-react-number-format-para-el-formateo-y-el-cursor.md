# 0060. MoneyInput usa react-number-format para el formateo y el cursor

- **Status:** accepted
- **Date:** 2026-08-20
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Feature 018 (`thousand-separator-number-inputs`) added a live thousand-separator
to `MoneyInput` — the field showing the amount typed while the digits are still
being entered, plus a hand-rolled mechanism to keep the text cursor in place
while reformatting on every keystroke. Two real bugs surfaced in that hand-rolled
logic before the feature even closed: the implementer (CP5) found and fixed a
case where the cursor jumped to the wrong spot at the USD decimal-point
boundary; the independent verifier (CP7) then found a second, more serious bug
— typing a second decimal point mid-string in a USD field silently dropped
already-typed cents from the value sent to the API, while the screen kept
showing the old, unchanged text. Two genuine defects in ~50 lines of caret
arithmetic, found on the first two passes anyone looked hard at it, is a signal
that this problem is harder than it looks and better solved by a
purpose-built, widely-used library than by more hand-rolled fixes.

## Decision drivers

- **Caret math is a known hard problem.** Getting cursor position right while
  reformatting text on every keystroke is exactly the kind of code that looks
  simple, is easy to get subtly wrong, and is expensive to verify by hand —
  confirmed twice over on this feature alone.
- **The saved value must never silently diverge from what the screen shows.**
  CHARTER §6's whole rationale ("green is not verified") applies doubly to a
  screen that writes money — a formatting bug that quietly changes the
  submitted amount is the worst class of defect this app can ship.
- **Don't reinvent a solved problem.** This project already avoids hand-rolling
  solved problems where a maintained library exists (Zod for validation,
  TanStack Query/Form for async and form state, `@base-ui/react` for
  primitives) — text-mask/number-formatting for inputs is the same kind of
  problem.
- **Must not force a redesign of `MoneyInput`'s public contract.** Every
  consumer (`transaction-create-dialog`, `transaction-edit-dialog`,
  `transfer-received-field`, `metas/*`, `funds/create-form`) passes/receives
  cents through `value`/`onChange` — the fix has to slot in behind that same
  contract.

## Considered options

1. **Keep hand-rolling it, fix bugs as found.** The status quo after CP7's
   fix — currently 615/615 green, both known bugs fixed and regression-tested.
2. **`react-number-format` (`NumericFormat`).** Purpose-built for exactly this:
   grouped display formatting with an internal caret-position engine, 2.2M
   weekly downloads, actively maintained (v5.4.5, published 2026-03-22),
   supports React 19 per its own peer-dependency range.
3. **`imask`/`react-imask`.** Also actively maintained (911k weekly downloads),
   more general-purpose (arbitrary input masks, not specialized for numbers),
   which means more configuration surface for a narrower need than this app has.
4. **`cleave.js`.** Highest GitHub-star count of the three, but its own
   ecosystem position has shifted toward maintenance mode relative to
   `react-number-format` and `imask` on recent download trends, and it predates
   React's function-component/hooks era (built around imperative DOM
   attachment), which fits this codebase's patterns worse than the other two.

## Decision outcome

Chosen option: **`react-number-format`'s `NumericFormat` component**, because
it directly targets this exact problem (grouped numeric input with a caret
engine), is the most widely-adopted and actively-maintained of the purpose-fit
options, and its `customInput` prop lets it render through this app's existing
styled `Input` component (`frontend/ui/components/input.tsx`) rather than a
bare native `<input>`, so the visual design is unaffected.

Integration keeps `MoneyInput`'s public contract identical — `currency`,
`value` (cents), `onChange(cents)` — so no consumer changes. Internally:
`NumericFormat` renders via `customInput={Input}`; `thousandSeparator` is
`thousandsSeparatorFor(currency)` (kept from feature 018 — still the single
source of truth shared with `formatCents` in `lib/money.ts`); COP sets
`decimalScale={0}` (whole pesos only, matching today's behavior); USD sets
`decimalScale={2}` with `fixedDecimalScale` left `false` (so `"1000."` while
typing does not get force-padded to `"1000.00"` — the exact behavior AC-2
requires); `allowNegative={false}` (amounts are never negative — consistent
with feature 017's AC-15 scope decision); `onValueChange`'s `floatValue` is
converted to cents via `Math.round(floatValue * 100)`. All hand-rolled
formatting/caret code (`keptCharIndices`, `formatForDisplay`,
`keptCaretCharsBefore`, `caretIndexAfterKeptChars`, the `useLayoutEffect`
cursor-restoration mechanism) is deleted — the library owns that surface now.

### Pros and cons of the options

**Keep hand-rolling it**
- Good: zero new dependency, no migration risk to an already-green feature.
- Bad: two real bugs found in two review passes on ~50 lines is evidence this
  keeps costing correctness bugs in exactly the class of defect (silent
  wrong-amount-saved) this app can least afford.

**`react-number-format`**
- Good: purpose-built, most widely used, actively maintained, integrates
  behind `MoneyInput`'s existing contract with no consumer-facing change.
- Bad: a new runtime dependency; the caret/format bugs this app found become
  someone else's problem to have already solved, which is exactly the point,
  but does mean trusting a third party for a money-adjacent code path.

**`imask`/`react-imask`**
- Good: also mature, also actively maintained, more flexible if this app ever
  needs arbitrary (non-numeric) masks.
- Bad: broader/more general API than a plain grouped-number field needs; no
  concrete advantage over `react-number-format` for this specific case.

**`cleave.js`**
- Good: highest star count, long track record.
- Bad: pre-hooks imperative design fits this codebase's patterns worse; lower
  relative download/maintenance signal than the other two libraries today.

## Consequences

- Good: eliminates the entire class of hand-rolled caret-math bugs this
  feature shipped twice; `MoneyInput`'s internals shrink significantly (no more
  `keptCharIndices`/caret ref/layout effect).
- Good: `thousandsSeparatorFor` (added in feature 018) stays useful and is now
  the single source for `thousandSeparator` across both `formatCents` and
  `MoneyInput`.
- Bad / cost: one new runtime dependency (`react-number-format`, ~5.4.5) to
  keep patched; the existing hand-rolled unit tests for
  `formatForDisplay`/caret math are replaced with behavior-level tests against
  the same 8 `spec.md` scenarios, so acceptance coverage is unaffected but the
  removed unit tests' specific assertions no longer apply.

## Confirmation

`frontend/components/money-input.tsx` imports `NumericFormat` from
`react-number-format` and contains no hand-rolled caret-index logic. The 8
scenarios in `features/018-thousand-separator-number-inputs/spec.md` stay
green under the new implementation (`money-input.test.tsx` +
`transaction-create-dialog.test.tsx`), and the full frontend suite
(`pnpm vitest run`) stays green with no regressions.
