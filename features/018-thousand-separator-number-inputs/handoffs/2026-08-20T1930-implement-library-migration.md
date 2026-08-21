---
skill: feature-edit (architecture amendment, post-CP7)
agent_id: main-session
feature: thousand-separator-number-inputs
started: 2026-08-20T19:10
ended: 2026-08-20T19:30
checkpoint: 5
artifacts:
  - docs/adr/0060-moneyinput-usa-react-number-format-para-el-formateo-y-el-cursor.md
  - frontend/components/money-input.tsx
  - frontend/components/money-input.test.tsx
  - frontend/package.json
findings_summary: >
  After CP7 found a second real bug in the hand-rolled caret/format code, the
  user explicitly chose (against this agent's initial recommendation to scope
  it as a separate feature 019) to replace MoneyInput's hand-rolled logic with
  react-number-format inside this same feature. Per CLAUDE.md, a library
  choice is architecturally significant and requires an ADR regardless of
  which feature folder the work lands in — wrote ADR-0060 (accepted) before
  any code change, researched the library's current API first (WebSearch +
  WebFetch against the official docs and npm registry: v5.4.5, published
  2026-03-22, React 16-19 peer range, NumericFormat's decimalScale without
  fixedDecimalScale does not force trailing zeros — confirmed this satisfies
  AC-2 before writing any integration code, not assumed from prior knowledge).
  Installed react-number-format@5.4.5. Rewrote money-input.tsx: NumericFormat
  with customInput={Input} (preserves the app's existing styled input rather
  than a bare native one), thousandSeparator=thousandsSeparatorFor(currency)
  (kept from CP6 refine — still the single shared source), decimalSeparator
  set to a distinct character per currency (the library rejects
  thousandSeparator===decimalSeparator even when decimalScale=0 makes the
  decimal separator unreachable — a real integration snag found by running
  the tests, not anticipated from the docs alone), decimalScale 0 for COP / 2
  for USD with fixedDecimalScale=false, allowNegative=false, onValueChange
  filtered to sourceInfo.source==="event" (avoids a feedback loop on
  prop-driven value changes) converting floatValue to cents. Deleted all
  hand-rolled formatForDisplay/keptCharIndices/keptCaretCharsBefore/
  caretIndexAfterKeptChars/useLayoutEffect/inputRef code — the library owns
  formatting and caret position now (140 lines -> ~40).
  Ran the 8 spec.md-bound tests first: 7 passed unchanged, 1 (the CP7
  regression test for the second-decimal-point bug) failed — not because the
  migration broke anything, but because the library's actual behavior is
  better than the hand-rolled fix's: it rejects a second decimal point
  outright (input and value both stay exactly as they were), rather than
  truncating the display to match parseFloat's truncation the way the CP7 fix
  did. Updated that one test to assert the library's actual (superior)
  behavior rather than forcing the old truncation behavior.
  Full suite, spec-coverage, lint, format, and tsc all independently re-run
  clean after the migration.
human_action_needed: no
recommended_next: engineer:refine (Checkpoint 6, re-run against the new implementation) then re-verify (CP7/CP8) before the CHARTER §6 browser check
tracker_update: local (no-op driver)
exit_criteria:
  - criterion: library choice recorded as an ADR before implementation
    verified_by: tool
    met: true
    evidence: "docs/adr/0060-moneyinput-usa-react-number-format-para-el-formateo-y-el-cursor.md, status: accepted, docs/adr/README.md index row updated"
  - criterion: library API verified against current docs before use, not assumed from prior knowledge
    verified_by: tool
    met: true
    evidence: "WebSearch + WebFetch against s-yadav.github.io/react-number-format docs and npm registry — confirmed v5.4.5 (2026-03-22), decimalScale/fixedDecimalScale semantics, onValueChange values shape, getInputRef/customInput ref-forwarding, before writing any integration code"
  - criterion: MoneyInput's public contract unchanged (no consumer files touched)
    verified_by: tool
    met: true
    evidence: "git diff --stat shows zero changes to transaction-create-dialog.tsx, transaction-edit-dialog.tsx, transfer-received-field.tsx, metas/*.tsx, funds/create-form.tsx"
  - criterion: all 8 spec.md scenarios still bound and green
    verified_by: tool
    met: true
    evidence: "python3 acceptance/spec_coverage.py features/018-thousand-separator-number-inputs frontend — scenarios 8, bound 8, unbound 0; pnpm vitest run components/money-input.test.tsx — 8 passed"
  - criterion: full frontend suite green, no regressions
    verified_by: tool
    met: true
    evidence: "pnpm vitest run — Test Files 60 passed (60), Tests 615 passed (615)"
  - criterion: lint, format, typecheck clean
    verified_by: tool
    met: true
    evidence: "pnpm lint — 0 errors, 4 pre-existing unrelated warnings; pnpm format:check — clean; npx tsc --noEmit — clean"
status: complete
---

## Summary

Library migration complete, independently verified by main-session against
real tool output at every step (not narrated as done without checking). One
test needed updating — not because of a regression, but because the library
handles the exact edge case CP7 found *better* than the hand-rolled fix did
(rejects the invalid second decimal point instead of silently truncating the
display). plan.md amended in place to record the supersession rather than
silently overwriting the original (now-superseded) architecture section.
Re-running CP6 refine and CP7/CP8 verify against this new implementation
before the CHARTER §6 browser check, since the prior refine/verify passes
were against code that no longer exists.
