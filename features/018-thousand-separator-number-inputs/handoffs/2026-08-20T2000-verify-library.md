---
skill: crap-analyzer (Light Verify)
agent_id: cp7-cp8-library-verifier
feature: thousand-separator-number-inputs
started: 2026-08-20T19:20
ended: 2026-08-20T20:00
checkpoint: 7
artifacts:
  - frontend/components/money-input.test.tsx
findings_summary: >
  Independent re-verification against the FINAL (react-number-format) state of
  the feature — a fresh reviewer distinct from cp5-implementer, main-session,
  and the CP6 refine subagents; nothing from any prior handoff trusted without
  re-deriving it myself.

  Confirmed true end-to-end scope directly: `git diff
  54cdcf45ec368ffd4c1ec2e39c30f658d23eed24 --stat -- frontend/` and the
  full-repo equivalent — 10 tracked files (money-input.tsx, money.ts,
  money.test.ts, package.json, pnpm-lock.yaml, docs/adr/README.md, and 5
  test-only assertion updates in 4 consumer test files) plus 1 untracked new
  file (money-input.test.tsx). Read money-input.tsx and lib/money.ts in their
  current state — confirmed no hand-rolled formatForDisplay/keptCharIndices/
  caret-ref/useLayoutEffect code remains; `NumericFormat` via `customInput=
  {Input}` owns formatting and caret position, exactly as ADR-0060 and the
  plan.md Amendment describe. This is the surface validated below, not the
  earlier hand-rolled one.

  Ran crap-analyzer's compute_crap.py against real coverage (`pnpm vitest run
  --coverage` -> clover.xml) scoped to this diff (repo-root set to the git
  root, not frontend/, since the diff's paths are repo-relative). All 5
  touched functions score far under the default threshold (20): MoneyInput
  comp=7/cov=100%/CRAP=7.0, numberPartFor comp=3/100%/3.0,
  thousandsSeparatorFor comp=2/100%/2.0, decimalSeparatorFor comp=2/100%/2.0,
  separatorMapFor comp=1/100%/1.0. Given this is now library configuration
  rather than hand-rolled algorithms, treated this automated score as a
  starting point, not the verification itself, per the task's own framing.

  (a) onValueChange's `sourceInfo.source !== "event"` guard. Read
  react-number-format@5.4.5's actual shipped source
  (node_modules/.../dist/react-number-format.es.js) rather than trust the
  types alone: `updateValueAndCaretPosition` fires `_onValueChange` with
  `source: SourceType.event` synchronously from the input's own change
  handler whenever the user's edit produces a formatted value different from
  the current one; a separate `useEffect` keyed on
  `[formattedValue, numAsString]` fires with `source: SourceType.props`
  whenever those change for a reason OTHER than the just-applied event (i.e.
  the `value` prop changed from outside). Empirically confirmed via a
  throwaway probe (frontend/components/__scratch-probe.test.tsx, deleted
  after use) built as a REAL controlled round-trip — a Harness component
  holding its own `useState` and feeding `onChange`'s cents straight back into
  `value`, mirroring exactly how every one of the 11 real `<MoneyInput>`
  consumers is wired (confirmed by reading
  frontend/components/transaction-create-dialog.tsx:246-249:
  `value={finiteOrNull(field.state.value)}` /
  `onChange={(cents) => field.handleChange(...)}` — a genuine round trip
  through TanStack Form state, not a fire-and-forget callback). Under that
  real wiring: every keystroke fires source "event" and calls the consumer's
  onChange; an externally-driven value change (simulated as a currency
  switch changing both `currency` and `value` from outside, not from typing)
  fires source "prop", is correctly suppressed (onChange NOT re-invoked, no
  feedback loop), and typing immediately afterward still fires normally — the
  guard never permanently blocks future input. This is the answer to the
  task's (a): confirmed empirically, not merely read off the types.

  (b) Edge cases beyond spec.md's literal 8 scenarios, all grounded in things
  a real user of this app can hit (an account balance in the hundreds of
  millions of COP is a real balance size in this app's own data; a USD amount
  typed with one decimal digit and a field cleared-then-retyped are both
  ordinary user actions):
    - Hundreds of millions of pesos (typed "123456789") -> "123.456.789",
      three separator groups — deeper than any existing test (max was two
      groups, "1.500.000"/"15.900.000"). Correct.
    - USD typed with only one decimal digit ("10.5") and a bare trailing
      decimal point mid-typing ("1000." before the next digit lands) — both
      correct, and confirmed through the REAL controlled round-trip, not just
      the isolated `onChange={vi.fn()}` harness the committed suite already
      used (that harness never lets `value` change in response to typing, so
      it never actually exercises the round-trip the guard exists for).
    - Clearing the field entirely then retyping — correct, no leftover state.
    - The exact CP7-superseded bug (typing a second literal "." mid-string in
      a USD field, e.g. after "1000.5" inserting another "." before the "5")
      — re-confirmed under the real controlled round-trip (the existing
      committed regression test for this only used the non-echoing mock):
      the library rejects the second decimal point outright, display and
      value both stay at "1,000.5"/100_050, zero data loss. This is the
      library actually handling, under real usage, the exact defect class
      ADR-0060 was written to eliminate.

  No behavioral defect found in either (a) or (b) — the library-backed
  implementation is correct on every case checked. What the probe DID surface
  is a coverage-shape gap: the committed money-input.test.tsx's `onChange=
  {vi.fn()}` pattern, used in all 8 scenario-bound tests, never lets `value`
  change in response to what the user types, so it never exercises the
  controlled round-trip that is the ONLY way this component is used in
  production (11/11 real consumers pass a genuine round-trip, confirmed by
  grep). The source-guard logic is the one piece of hand-written logic this
  migration adds on top of the library, and it had never actually been
  exercised end-to-end by any committed test. Promoted 3 of the probe's 6
  cases into permanent tests in money-input.test.tsx (round-trip
  decimal-point survival, hundreds-of-millions grouping, external
  value-change/source-guard non-loop); the other 3 probe cases (single-digit
  USD decimal, clear-then-retype, second-decimal-point under round-trip)
  stayed as verification-only since they duplicate what the 3 promoted tests
  or the existing suite already cover once the round-trip pattern itself is
  represented. Deleted the scratch probe file entirely before the final test
  run.

  Separately re-confirmed (not trusted from the old CP7 handoff, which
  predates the library migration) that MoneyInput/thousandsSeparatorFor/
  decimalSeparatorFor's `?? ...COP` fallbacks stay untested dead code
  correctly: backend/src/quaestor/domain/money.py still enforces
  `SUPPORTED_CURRENCIES = ("COP", "USD")`; grepped all 11 non-test
  `<MoneyInput>` consumers fresh — every currency prop is a literal "COP"/
  "USD" or sourced from an account/transaction/meta record already restricted
  to that domain. No consumer can hand MoneyInput a third currency in
  practice.

  Personally re-ran everything (not trusted from any prior handoff): `pnpm
  vitest run` — Test Files 60 passed (60), Tests 620 passed (620) (617
  pre-existing + 3 new tests). `pnpm lint` — 0 errors, 4 pre-existing warnings
  (noExplicitAny in lib/filter-schemas.ts and lib/use-url-filters.ts, both
  untouched by this feature). `pnpm format:check` — clean. `npx tsc --noEmit`
  — clean. `python3 acceptance/spec_coverage.py
  features/018-thousand-separator-number-inputs frontend` — scenarios 8,
  bound to tests 8, unbound 0, @browser 0, @backend 0.

  Incidental note, not a feature defect: generating clover coverage via `pnpm
  vitest run --coverage` left a `coverage/` directory that briefly caused
  `pnpm lint`/`pnpm format:check` to blow up (biome has no exclude for
  `coverage/` and hits its max-file-size limit on the generated HTML report).
  `coverage/` is gitignored and was deleted before the final lint/format run
  above; this is a pre-existing repo-wide tooling gap unrelated to this
  feature's diff, not fixed here (out of scope for a frontend-only money-
  formatting feature; no CI workflow in this repo runs coverage and lint
  back-to-back today, so it is not an active risk).
human_action_needed: yes
recommended_next: >
  CHARTER §6 manual browser check. This has been outstanding since before the
  ADR-0060 library migration — plan.md scheduled it against the ORIGINAL
  hand-rolled implementation, and it was never run against that version
  before the architecture changed. It must now be run against the
  react-number-format implementation that is actually shipping (the one this
  handoff and the CP6 refine-library pass validated), not the earlier
  hand-rolled one, since a browser check of code that no longer exists would
  prove nothing. Drive MoneyInput live via Chrome MCP or a manual pass: (1) a
  COP field (e.g. transaction create), type a 7+ digit amount and edit a
  digit mid-string — confirm the separator appears live and the cursor stays
  where the user was typing, not at the end; (2) a USD field (e.g. a dollar
  meta/fund), type an amount with a decimal (e.g. "1000.5") — confirm
  comma-grouping and that the decimal point behaves correctly while typing;
  (3) on that same USD field, after typing a decimal amount, try inserting a
  second "." mid-string — confirm the library rejects it live (matches what
  this pass confirmed under jsdom); (4) confirm the value actually submitted
  (via the dialog's submit / network tab) matches what the field displayed in
  all three cases. No further automated verification is expected to change
  before this human step; the browser check is the last gate before the
  feature can close.
tracker_update: local (no-op driver)
exit_criteria:
  - criterion: full frontend suite independently re-run and green
    verified_by: tool
    met: true
    evidence: "pnpm vitest run — Test Files 60 passed (60); Tests 620 passed (620) (617 pre-existing + 3 new tests)"
  - criterion: every spec.md scenario still bound to a test after this pass's changes
    verified_by: tool
    met: true
    evidence: "python3 acceptance/spec_coverage.py features/018-thousand-separator-number-inputs frontend — scenarios 8, bound to tests 8, unbound 0"
  - criterion: CRAP/complexity independently assessed for every new/changed function against the FINAL library-based implementation, not the superseded hand-rolled one
    verified_by: tool
    met: true
    evidence: "compute_crap.py against fresh clover.xml coverage: MoneyInput 7/100%/7.0, numberPartFor 3/100%/3.0, thousandsSeparatorFor 2/100%/2.0, decimalSeparatorFor 2/100%/2.0, separatorMapFor 1/100%/1.0 — all well under default threshold 20"
  - criterion: the onValueChange source guard verified empirically, not merely read off the library's type declarations
    verified_by: tool
    met: true
    evidence: "throwaway probe using a real controlled round-trip (matching frontend/components/transaction-create-dialog.tsx's actual value/onChange wiring): every keystroke fires source=event and calls onChange; an externally-driven value change fires source=prop, is suppressed, does not loop, and does not block subsequent typing"
  - criterion: edge cases beyond spec.md's literal 8 scenarios checked against real user-reachable inputs, not invented hypotheticals
    verified_by: tool
    met: true
    evidence: "hundreds-of-millions COP grouping (123456789 -> 123.456.789), USD single-decimal-digit and trailing-decimal-point typing, clear-then-retype, and the CP7-superseded second-decimal-point scenario — all confirmed correct under the real controlled round-trip, not just the isolated onChange={vi.fn()} harness"
  - criterion: coverage gap resolved — either fixed with a meaningful regression test, or confirmed not a real gap
    verified_by: tool
    met: true
    evidence: "no behavioral defect found in (a)/(b); found and closed a coverage-shape gap instead — promoted 3 of the probe's cases into money-input.test.tsx, since no committed test previously exercised the controlled round-trip that is the only way MoneyInput is used in production; currency-domain gap re-ruled-out via fresh grep of all 11 non-test consumers plus backend SUPPORTED_CURRENCIES=(\"COP\",\"USD\")"
  - criterion: lint, format, and typecheck clean on the final state
    verified_by: tool
    met: true
    evidence: "pnpm lint — 0 errors, 4 pre-existing warnings in files untouched by this feature; pnpm format:check — clean; npx tsc --noEmit — clean"
status: complete
---

## Summary

Independent CP7 verify against the feature's FINAL state — the
react-number-format implementation, not the earlier hand-rolled one CP7's
first pass (2026-08-20T1900-verify.md) reviewed before ADR-0060 replaced it.
Fresh reviewer (`cp7-cp8-library-verifier`), nothing trusted from any prior
handoff without re-deriving it: re-ran the full diff scope, the full test
suite, spec-coverage, lint, format, and typecheck myself.

Applied crap-analyzer's automated CRAP score against real clover coverage —
all 5 touched functions score well under threshold, unsurprising now that
this is mostly library configuration. Per the task's own instruction, treated
that as a starting point and put real scrutiny into two things the automated
score cannot see: (a) whether react-number-format's `source !== "event"`
guard actually behaves correctly, confirmed both by reading the library's
shipped source and by an empirical probe; (b) whether the COP/USD formatting
configuration holds up on realistic edge cases (very large COP balances, a
USD amount with one decimal digit, clearing and retyping, and the exact bug
CP7's first pass found and ADR-0060 replaced the whole approach over).

No behavioral defect found — the library handles every case correctly,
including the second-decimal-point scenario that justified the library
migration in the first place. What the investigation did surface: the
committed test suite's `onChange={vi.fn()}` pattern never exercises the
controlled round-trip that every real consumer actually uses (confirmed via
grep + reading transaction-create-dialog.tsx), so the one piece of
hand-written logic this migration adds (the source guard) had never been
tested end-to-end. Closed that gap with 3 new permanent tests in
money-input.test.tsx, built from a throwaway probe that was deleted after
use. Full suite now 620/620, spec-coverage still 8/8, lint/format/tsc clean.

The CHARTER §6 browser check remains the one thing genuinely outstanding —
it was scheduled against the hand-rolled implementation and never run before
the architecture changed, so it still needs to happen, now against the code
that actually ships.
