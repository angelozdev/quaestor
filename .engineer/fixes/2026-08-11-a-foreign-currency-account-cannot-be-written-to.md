---
slug: "2026-08-11-a-foreign-currency-account-cannot-be-written-to"
title: "Recording or planning money in a foreign-currency account fails with an English error"
severity: high
blocks_user: true
workaround: "Creating a movement: press Crear a second time — the first attempt corrects the currency and the retry goes through. Planning a payment: no workaround; plan it against a peso account and move it afterwards with the correction dialog."
status: closed

source:
  kind: internal
  ref: "features/012-movement-corrections/handoffs/2026-08-11T1200-browser-verification.md"

repro: |
  Planning (no workaround):
  1. Por pagar → Planear pago.
  2. Beneficiario, Cuenta = a USD account, Monto = 100, fecha, categoría.
  3. Press Planear. Press it again. And again.

  Creating (recoverable):
  1. Transacciones → Nueva.
  2. Cuenta = a USD account. Note the amount label still reads "Monto * (COP)".
  3. Fill the rest and press Crear.

expected: "A payment planned or a movement recorded against an account that holds dollars is stated in dollars, and is accepted. No screen in this app speaks English to the owner."
actual: "Both refuse with the raw backend message `currency COP does not match account currency USD`, in English. Creating succeeds on the second press; planning never succeeds at all."

feature_refs:
  - "features/012-movement-corrections"

investigation:
  match_mode: manual
  candidates_considered: 2
  root_cause: |
    Two distinct causes behind one symptom.

    **Planning — the currency is never sent.** `frontend/app/(app)/to-pay/page.tsx`
    `plan.mutationFn` builds the body with payee, amount, due_date, account_id,
    category_id, new_category, meta_id and notes — and no `currency`. It is
    optional in `PlanPaymentCreate` (`frontend/lib/api/types.ts:314`), so the
    request omits it and the backend takes its default of COP. Against a USD
    account `plan_payment` then raises. There is no sequence of clicks that fixes
    this: the field is not merely stale, it is absent.

    **Creating — the currency is one render stale.** `transaction-create-dialog.tsx`
    reads `form.state.values.accountId` directly to derive the currency. A direct
    read of TanStack Form's state is not reactive, so picking an account does not
    re-render the label or the value that goes on the wire; the failed mutation is
    what re-renders, which is why the second press works. The amount label is the
    visible symptom — it still reads `(COP)` with a dollar account selected, and
    `MoneyInput` is therefore in peso mode, so a typed `1556.04` is parsed as
    155.604 pesos. `frontend/app/(app)/to-pay/page.tsx`'s plan dialog reads
    `planAccountId` the same way and shows the same stale label.

    **Neither is feature 012's.** `git diff --merge-base main` shows the branch
    changed only the import in `transaction-create-dialog.tsx` — a local
    `currencyOf` replaced by the identical shared one from `lib/money.ts` — and
    `main`'s own `plan.mutationFn` omits `currency` exactly as this one does.

  found_by: "Browser verification of feature 012 against the SQLite sandbox, 2026-08-11. Found while creating the fixture for AC-13's own example (US$1.556,04 moved to a peso account); it is not reachable from the correction dialogs, which resolve currency correctly through `currencyForAccount`."

gap_analysis:
  - category: missing_ac
    phase: discover-acs
    finding: "No acceptance criterion, in any feature, says that a payment can be planned against an account that holds another currency. AC-4 and AC-5 of feature 012 cover confirming and storing in that currency, and feature 005 covers reading in it, but planning was never stated — so nothing tested it and the omission survived every green suite."
    followup_kind: amend_ac
  - category: inadequate_verification
    phase: verify
    finding: "The frontend suite has no test that picks an account of a different currency in either the create dialog or the plan dialog and asserts what reaches the wire. Every existing test uses the default peso account, so a stale currency and an absent currency are both invisible to it."
    followup_kind: add_verification

pin_confirmation:
  feature_refs:
    - feature: "features/012-movement-corrections"
      spec_path: "frontend/app/(app)/to-pay/page.test.tsx + frontend/components/transaction-create-dialog.test.tsx"
      red_run:
        result: red
        command: "cd frontend && pnpm vitest run 'app/(app)/to-pay/page.test.tsx' components/transaction-create-dialog.test.tsx"
        output: |
          FAIL  The payment is planned in dollars, cents and all
          -   ObjectContaining { "amount": 155604, "currency": "USD" }
          +   { "amount": 15560400, ... }            ← no currency key at all
          FAIL  The amount box asks for dollars as soon as a dollar account is chosen
          Unable to find an element with the text: Monto * (USD).
          FAIL  The first press states the movement in dollars, cents and all
          -     "amount": 155604, "currency": "USD",
          +     "amount": 15560400, "currency": "COP",
          FAIL  Dollars leaving for a peso account are asked for as two figures
          Unable to find an element with the text: Monto enviado * (USD).
      note: |
        Five red tests, not the two the followup named: the transfer tab of the
        create dialog turned out to be a third path with the same cause —
        `isCrossCurrency` was computed from the same non-reactive reads, so a
        dollar-to-peso transfer never revealed its second amount box and sent
        pesos off a dollar account. The 1556.04 → 15560400 in two of the four is
        the peso-mode MoneyInput swallowing the decimal point.

fix_commits:
  - "3cf13f4 fix: an account that holds dollars can be written to again"
  - "Ships inside feature 012's branch rather than its own. Decision by the dispatcher, same trade the owner accepted for 2026-07-31-phantom-budget-assignment: app/(app)/to-pay/page.tsx was rewritten by 012, so a separate branch guarantees a conflict on a file that moves balances."

harden_results:
  bug_line_mutation_confirmed: true
  mutation_score: "n/a — frontend only. The fix changed `to-pay/page.tsx` and `transaction-create-dialog.tsx`; `backend/scripts/mutate.py` mutates Python and the project has no JS mutation tool. The bug-line gate is the evidence in its place: reverting the production files with the new tests in place turned 10 tests across 4 files red."
  arch_check: "n/a — frontend only. `pnpm knip` clean; the new `lib/use-form-values.ts` export is consumed by both dialogs."
  notes: |
    Bug-line gate, run by the dispatcher and not taken from the agent's report:
    the production files were reverted to HEAD with the new tests left in place.
    **10 tests across 4 files went red**; restoring the fixes returned all 510 to
    green. So the tests pin the defects and not the fixes.

    Scope deviation, flagged for the owner: no `atdd:mutate` pass, for the same
    reason as its sibling — `backend/scripts/mutate.py` walks a Python AST and
    has no frontend counterpart. No separate three-subagent refine either.

    The grep the artifact's notes asked for was run across the whole frontend and
    classified every `state.values` / `getFieldValue` site. Two were the defect
    and are fixed. Five in `recurring/page.tsx` were left and turned out to hide
    a third instance of the same symptom from the opposite direction — a currency
    constant nobody ever wired to an account — filed separately as
    `2026-08-11-a-recurring-charge-cannot-live-in-a-dollar-account`. The rest are
    correct: inside `form.Subscribe` selectors, inside submit handlers, or already
    reactive through `useStore` (`funds/create-form.tsx:100`, the precedent the
    new hook generalises).

fix_commits:
  - "3cf13f4 fix: an account that holds dollars can be written to again"

handoff_path: .engineer/handoffs/2026-08-13-the-three-of-august-11-close.md

followups:
  - category: inadequate_verification
    action: "Pin both before fixing: picking a USD account in the create dialog must put USD on the wire on the FIRST submit; planning against a USD account must send currency USD."
    status: applied
  - category: missing_ac
    action: "Settled 2026-08-13 by reading rather than writing: feature 006 AC-17 already governs it — a payment may not be planned \"in a currency that differs from the account's own\", so planning in the account's currency was always in scope and the fix made the screen obey a criterion that predated it. The gap this followup was really about — that nothing tested it — is closed: `to-pay/page.test.tsx`, `transaction-create-dialog.test.tsx` and `recurring/page.test.tsx` all pick a foreign-currency account now, and CHARTER §6 was amended the same day to require it."
    status: applied
---

# A foreign-currency account cannot be written to — notes

Filed out of feature 012's browser verification, deliberately **not** fixed
inside it: both causes predate the branch and live in the create and plan
dialogs, neither of which is what 012 was about. 012's own dialogs — correcting
a movement and confirming a payment — resolve the currency correctly and were
verified end to end against the sandbox on 2026-08-11.

The two causes deserve separate fixes even though the owner sees one symptom.
The absent field is a real gap in what the screen sends; the stale read is a
reactivity bug that likely has siblings anywhere `form.state.values` is read
outside a subscription. Worth grepping for that pattern before closing.

The English message is a third, smaller thing: raw backend text reaching the
owner. Feature 012's CP6 fixed exactly this class in the edit dialog. The same
treatment applies here.

Resume at Step 3 (Pin): write the two red tests above, confirm they fail, then
fix the absent field first — it is the one with no workaround.
