---
slug: thousand-separator-number-inputs
checkpoint: 4
plan_status: superseded-in-place
created: 2026-08-20
---

## Amendment (2026-08-20, after CP7)

**The hand-rolled architecture below was replaced by `react-number-format`
(ADR-0060) before this feature closed.** CP7's independent verify found a
second real bug in the hand-rolled caret/format logic (a USD field's second
decimal point silently dropped typed cents from the saved value while the
screen showed no change) — the second genuine defect in this ~50-line surface
after CP5's implementer already found and fixed one. The user, presented with
that history, chose to replace the hand-rolled formatting/caret code with a
purpose-built, actively-maintained library rather than continue trusting more
hand-fixes to the same surface. See ADR-0060 for the full decision record.

**What stays true from the plan below:** `MoneyInput`'s public contract
(`currency`, `value` in cents, `onChange(cents)`), the one-file blast radius,
`parseMoneyToCents`'s replacement (cents now derived from
`onValueChange`'s `floatValue`), `thousandsSeparatorFor` (kept as the shared
separator source), the Charter Check outcome (still no ADR was needed for the
*original* hand-rolled approach — this new ADR is for the library swap, not a
retroactive gap), the Performance/Collaboration/Execution sections, and the
Test strategy's CHARTER §6 browser-check requirement (now re-scoped to verify
the library-backed implementation instead of the hand-rolled one).

**What changed:** `formatForDisplay`, `keptCharIndices`,
`keptCaretCharsBefore`, `caretIndexAfterKeptChars` and the
`useLayoutEffect`/`inputRef` cursor-restoration mechanism are deleted —
`NumericFormat` (via `customInput={Input}`) owns formatting and caret
position internally. `money-input.test.tsx`'s assertions are unchanged
(behavior-level, bound to the same 8 `spec.md` scenario titles) except the
CP7 regression test, updated to match the library's actual (and better)
behavior: a second decimal point is rejected outright rather than truncating
the display — see the test's own diff for the exact before/after.

## Architecture (original — see Amendment above for what superseded it)

**One file changes: `frontend/components/money-input.tsx`.** Every consumer
(`transaction-create-dialog.tsx`, `transaction-edit-dialog.tsx`,
`transfer-received-field.tsx`, `metas/*.tsx`, `funds/create-form.tsx`) renders
`<MoneyInput>` and passes/receives cents — none of them touch text formatting
today, so none of them need to change (AC-8).

**New pure function — `formatForDisplay(text, currency)`.**
Presentation-only; sits next to the existing `parseMoneyToCents` /
`centsToText` and is called wherever `text` state is set (initial mount,
currency-resync, and every `onChange`).

- COP: strip everything but digits, then insert `.` every 3 digits from the
  right (`\B(?=(\d{3})+(?!\d))`). `"500"` has fewer than 4 digits → no
  separator inserted → AC-4 falls out of the regex for free, no special case.
- USD: split the cleaned text (digits + at most one `.`) at the decimal
  point. Group the integer part with `,` the same way; re-attach `.` +
  whatever decimal digits the user has typed **verbatim, ungrouped, no
  rounding** — so a user mid-typing `"1000."` sees `"1,000."` and can keep
  going, rather than the field fighting them (AC-2).

**`parseMoneyToCents` does not change.** It already strips every non-digit
(and, for USD, non-dot) character before parsing, so it already tolerates a
value that contains separators — pasting `"1.000.000"` or typing through an
already-grouped display parses exactly as it does today (AC-5, AC-7). This is
the reason the whole feature is a presentation-layer change: the value that
reaches `onChange` (and therefore the API) is untouched.

**Cursor preservation (AC-3) — the one genuinely new mechanism.** A
controlled `<input>` resets its caret to the end of the value on every
re-render unless told otherwise. Fix, entirely inside `MoneyInput`:

1. Give `<Input>` a `ref` (React 19 — plain prop, no `forwardRef` needed;
   `Input` already spreads `...props` onto `@base-ui/react/input`'s
   `InputPrimitive`, which forwards refs to the native element).
2. In `onChange`, before formatting: read `e.target.selectionStart` (the
   caret position in the *raw*, already-edited DOM value) and count how many
   digit characters (`0-9`) sit before it. Store that count in a ref.
3. After `setText(formatted)`, a `useLayoutEffect` keyed on `text` walks the
   new formatted string, finds the index right after that same count of
   digits, and calls `inputRef.current.setSelectionRange(pos, pos)`.

This only counts digits (not separators), so it is correct regardless of
which separator character surrounds the edit point — inserting or deleting a
digit anywhere in the string keeps the caret glued to that digit.

**Why not `Intl.NumberFormat`.** It is locale-data-dependent (behavior can
differ across Node/browser/test environments) and rounds/reformats the
decimal part, which would fight in-progress USD typing (`"1000.5"` risks
becoming `"1,000.50"` mid-keystroke). A manual regex over the raw digit
string is deterministic, testable without locale mocking, and never touches
digits the user hasn't finished typing.

**Alternative considered and rejected: format from `cents` instead of from
raw text.** Re-deriving the display from the parsed cents value on every
keystroke would round USD to 2 decimals as soon as parsing succeeds,
overwriting a still-being-typed `"1000.5"` the moment the second digit lands
— the opposite of the "don't fight the user's typing" principle the
component already follows for currency changes (its own comment on the
resync block).

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| §1 Methodology — ADR for architecturally-significant decisions | ✅ N/A | Presentation-only change to one component's display formatting; no library, schema, API, auth, testing-strategy or module-boundary decision. No ADR required (CLAUDE.md's own trigger list excludes this). |
| §2 Architecture — module boundaries, MoneyInput as the shared money widget | ✅ | No new component, no new coupling; the existing shared-component boundary is exactly why this is a one-file change. |
| §3 Conventions — English identifiers, pnpm, vitest colocated | ✅ | `formatForDisplay` is English; test file is `money-input.test.tsx`, colocated. |
| §6 Quality stance — screen that writes money tested against a foreign-currency account | ✅ | AC-2's whole point is USD; `money-input.test.tsx` covers COP and USD, and the CHARTER §6 browser pass (below) exercises a USD field live. |
| §6 Quality stance — green is not verified, browser pass required | ⚠️ → planned | See Test strategy: a manual Chrome MCP pass on a COP and a USD field is scheduled before CP8 closes, per `feature.md`'s `validation_method`. |
| §7 Autonomy — medium, data gates | ✅ | No schema/migration/data touch; nothing requires escalation past medium. |
| Verification independence (Principle 7) | ✅ | CP6 refine review subagents are fresh regardless of gating; CP7 verify dispatched to an agent distinct from the implementer. |
| Mutation policy (`manifest.mutation`: cadence `on_demand`, opt-in per feature) | N/A | `mutate.py` is Python/AST-based; this feature touches zero Python/backend files. CP8's mutation step is skipped for this feature — noted explicitly rather than silently omitted. |

**Amendments:** none. No ⚠️ deviation lacks a matching resolution — the one
⚠️ row (browser pass) is closed by a planned step in Test strategy, not a
charter exception.

## Phasing

**One slice — no natural sub-cuts.** All 8 ACs land in the same function and
the same cursor-restoration mechanism; splitting them into separate slices
would mean re-touching the same 30 lines repeatedly for no isolation benefit.

1. `formatForDisplay` (COP + USD grouping, decimal point untouched) — AC-1,
   AC-2, AC-4, AC-5, AC-6.
2. Wire `formatForDisplay` into mount / resync / `onChange` — AC-7 (round
   trip) falls out once both are in place.
3. Cursor-position preservation (ref + `useLayoutEffect`) — AC-3.
4. `money-input.test.tsx` (new) binds AC-1..AC-7; one added scenario-title
   test inside the existing `transaction-create-dialog.test.tsx` binds AC-8.

## Performance budgets

Negligible. `formatForDisplay` is one or two regex passes over a string at
most ~15 characters (no realistic personal-finance amount is longer); the
cursor restoration is a single `setSelectionRange` call in a layout effect
that only runs when `text` changes. No new renders, no new network calls, no
measurable budget beyond the existing controlled-input re-render on every
keystroke that already happens today.

## Collaboration schedule

Solo — implementer runs CP5 directly (small, single-file, no cross-team
coordination needed). CP6 refine and CP7 verify still run as independent
passes per the standard checkpoint contract.

## Execution modes

Local subagent for CP5 implement (auto-dispatched, autonomy `medium`); CP6
refine's three review subagents and CP7's independent verifier are also local
subagents. No cloud dispatch — this is fast enough locally that the
dispatch-router overhead isn't worth it.

## Test strategy

Default DAE stack for the frontend stream (per `feature.md`'s `acceptance_stream:
frontend`): `money-input.test.tsx` binds AC-1 through AC-7 as vitest tests
whose titles match `spec.md`'s scenario names verbatim; one test added to
`transaction-create-dialog.test.tsx` binds AC-8. `spec_coverage.py` gates that
every scenario has a bound test before the suite is considered green.

No `@backend` scenarios exist (zero Python touched), so CP7's mutation-testing
step is not run for this feature — see Charter Check.

**`validation_method` (from `feature.md`):** CHARTER §6 manual browser check
before CP8 closes — drive `MoneyInput` live via Chrome MCP in two cases: (1) a
COP field (e.g. transaction create), typing a 7-digit amount and editing a
digit mid-string, confirming the separator appears and the cursor doesn't
jump; (2) a USD field (e.g. a dollar-denominated meta or fund), typing an
amount with a decimal, confirming the comma-grouping appears and the decimal
point still behaves as it does today. For both: the value shown matches
expectation, the cursor stays put through a mid-string edit, and the value
that would be saved (checked via the dialog's submit / network tab if needed)
is unchanged from today's behavior.
