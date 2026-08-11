---
slug: "2026-08-11-a-recurring-charge-cannot-live-in-a-dollar-account"
title: "A recurring charge cannot be created in, or moved to, an account that holds dollars"
severity: high
blocks_user: true
workaround: "none from the screen. The charge has to be created against a peso account, and each occurrence corrected to the dollar account by hand once it is posted."
status: hardened

source:
  kind: internal
  ref: ".engineer/fixes/2026-08-11-a-foreign-currency-account-cannot-be-written-to.md"

repro: |
  Creating:
  1. Recurrentes → the create form.
  2. Cuenta = an account that holds dollars. Note the amount label reads
     "Monto * (COP)" and there is no control anywhere to change it.
  3. Fill the rest and save.

  Moving an existing one:
  1. Recurrentes → edit a charge that lives in a peso account.
  2. Change its account to one that holds dollars, and save.

expected: "A subscription charged in dollars — Opal, Hevy Pro, DolarApp Premium, Smart Fit, all of them real charges on this owner's DolarApp account — can be recorded as recurring against the account that actually pays it."
actual: "Both refuse with `currency COP does not match account currency USD`, in English. No sequence of clicks helps: the screen has no way to say the charge is in dollars."

feature_refs: []

investigation:
  match_mode: none
  candidates_considered: 1
  root_cause: |
    `frontend/app/(app)/recurring/page.tsx` hard-codes the currency in three
    places — the create form's defaults (line 119), a reset (line 145) and
    another reset (line 196) — all `currency: "COP"`. The edit form seeds it from
    the row being edited (line 341) and never re-derives it when the account
    changes. Nothing on the screen derives currency from `accountId`, and there
    is no currency control for the owner to set it directly.

    The backend refuses on both paths: `services/recurring.py:113` on create and
    `:257` on update, once the account is moved.

    Lines 442 and 596 read `getFieldValue("currency")` non-reactively to label
    the amount box. That is the same non-reactive shape fixed today in the create
    and plan dialogs, but here it is not the cause — the value it reads is a
    constant, so making the read reactive would change nothing until the value
    itself starts following the account.

  found_by: "The agent fixing `2026-08-11-a-foreign-currency-account-cannot-be-written-to`, while grepping the frontend for other non-reactive `form.state.values` reads. It is the same defect on a third screen, arrived at from the opposite direction: not a stale currency, an absent one."

gap_analysis:
  - category: missing_ac
    phase: discover-acs
    finding: "No acceptance criterion in any feature says a recurring charge can live in an account that holds another currency, and feature 007's ACs are silent on currency entirely. So the create form was built with a peso constant and nothing ever asked why."
    followup_kind: amend_ac
  - category: inadequate_verification
    phase: verify
    finding: "The recurring screen's tests never pick a foreign-currency account, so a hard-coded currency is invisible to them. Identical to the gap that hid the same defect on the create and plan dialogs — three screens, one blind spot, found only by driving the app in a browser."
    followup_kind: add_verification

pin_confirmation:
  feature_refs:
    - feature: "frontend/app/(app)/recurring/page.tsx"
      spec_path: "frontend/app/(app)/recurring/page.test.tsx + features/007-recurring-engine/spec.md (AC-19)"
      red_run:
        result: red
        command: "cd frontend && pnpm vitest run 'app/(app)/recurring/page.test.tsx'"
        output: |
          × The boxes carry what the charge already says
            → expect(element).toHaveValue(Netflix)
          × The amount box asks for dollars as soon as a dollar account is chosen
            → Unable to find an element with the text: Monto * (USD).
          × The charge is created in dollars, cents and all
            -   "amount": 2935, "currency": "USD",
            +   "amount": 293500, "currency": "COP",
          × A charge moved to a dollar account is restated in dollars, cents and all
            → expected "spy" to be called 1 times, but got 0 times
          Tests  5 failed | 3 passed (8)
      note: |
        The first failure is a defect nobody had reported and which the assigned
        repro could not be observed without: the edit dialog opened BLANK and
        Guardar never fired a request. `useForm` calls `FormApi.update` during
        render, overwriting the store right after `reset()` whenever the inline
        `defaultValues` no longer deep-equals what the form holds. It was about
        to become a money bug: a dollar charge opened for editing would have
        shown a peso box, turning a typed 29.35 into US$2.935,00.

fix_commits:
  - "0e75c93 feat: a recurring charge can live in, and move to, an account that holds dollars"
  - "cb2f7e2 test(007): AC-19's two scenarios never tested anything, and the trap that hid it is closed"
  - "Ships inside feature 012's branch, same trade as its two siblings."

harden_results:
  mutation_score: 0.877
  bug_line_mutation_confirmed: true
  arch_check: "`uv run lint-imports` → 2 contracts kept, 0 broken, after `recurring.py` gained an import of `transactions as _tx`. The arrow points the way `planned.py` already established; `test_the_transaction_service_never_learns_about_recurring_items` still holds."
  notes: |
    Bug-line gate run by the dispatcher: the production files were reverted to
    HEAD with the new tests left in place. **Five tests went red**, including the
    one asserting the update request was never sent. Restoring returned all 515
    to green.

    The scenario controls were run one rule at a time by the agent and re-checked
    here: the type made mutable, the restated-amount refusal removed, the
    currency assignment removed, the account assignment removed — each turned its
    own scenario red, each restored. One control did NOT go red — removing
    `row.amount = amount` from `retarget` — because `update_recurring` already
    assigns `item.amount` before calling it. That line is dead on the recurring
    path and is recorded rather than removed; `services/recurring.py` is in no
    feature's mutation opt-in list, a debt ADR-0052 itself names.

    `services/recurring.py` was swept for the first time — it is in no feature's
    mutation opt-in list, the debt ADR-0052 names. **65 mutants, 57 killed,
    8 survivors, 87,7%**, three stages cheapest-first, each proven green against
    the untouched module first.

    **The 8 survivors are NOT adjudicated and no test was written for them.**
    Every one is a boundary — the `==` case — of a comparison or a constant:
    `end_date == start_date` on both create and update (a charge that starts and
    ends the same day), `start_date == today`, `interval_count` of 1 or 2, an
    amount of exactly 1 cent, and moving a start date to the date it already
    holds. Whether each is a real gap, an equivalent mutant or an unreachable
    state is a judgment that has to be made against feature 007's acceptance
    criteria, not against the code — the standing rule that a test written to
    kill a survivor can pin a bug. Feature 012's CP8 ran that adjudication on a
    fresh agent and the correct answer for all five of its survivors was to write
    nothing; this one has not been run.

gap_analysis:
  - category: missing_ac
    phase: discover-acs
    finding: "Feature 007's AC-19 fixed the currency at declaration, and nobody noticed the owner's own subscriptions contradicted it. The criterion was written from the engine's point of view — what a rule may change — rather than from the owner's, and the four dollar charges that break it were already in his data when it was approved."
    followup_kind: amend_ac
  - category: inadequate_verification
    phase: verify
    finding: "AC-19's two scenarios passed because a keyword was misspelled: World.attempt caught the TypeError as a rejection. They would have passed against an empty function. The same escape hatch sat in named_goals.py and sinking_funds.py, putting 41 more rejection scenarios one typo away from the same vacuity, and AttributeError was in the tuple too — a misspelled attribute would have read as a refusal."
    followup_kind: add_verification

followups:
  - category: inadequate_verification
    action: "Pin before fixing: creating a recurring charge against a USD account must send currency USD, and moving an existing one to a USD account must restate its currency."
    status: applied
  - category: missing_ac
    action: "Decide whether a recurring charge in a foreign currency is in scope, and if so state it as an AC."
    status: applied
  - category: inadequate_verification
    action: "Remove TypeError and AttributeError from every acceptance handler's rejection tuple, so a misspelled keyword can never read as a refusal again."
    status: applied
  - category: inadequate_verification
    action: "Adjudicate the 8 survivors of services/recurring.py against feature 007's ACs, on a fresh agent — real gap, equivalent mutant or unreachable state, one verdict each. Write nothing until that is decided. Also settle the dead `row.amount = amount` in retarget, which a control proved unreachable on the recurring path."
    status: open
---

# A recurring charge cannot live in a dollar account — notes

Filed 2026-08-11, out of the fix for the same defect on the create and plan
dialogs. It is the third screen with one symptom, and the one where the owner has
the most real charges waiting for it: the roadmap item `id:fund-smooths-an-annual-charge`
names Opal at US$29,35/year, Hevy Pro at US$30,22/year, DolarApp Premium at
US$69,99/year and Smart Fit at US$37,20/month — every one of them a dollar
subscription that cannot currently be recorded as recurring against the account
that pays it.

**Not the same cause as its two siblings**, and that matters for the fix. There
the currency was stale or absent because a non-reactive read never updated it.
Here it is a constant nobody ever wired to anything, on a screen with no currency
control at all. Making the two `getFieldValue("currency")` reads reactive would
change nothing on its own — the value has to start following the account first.

The English message is not this defect's to fix; `id:error-contract` on the
roadmap covers that class exhaustively and the owner has already decided its
shape.

Resume at Step 3 (Pin): write the two red tests above, confirm they fail, then
derive the currency from the chosen account on both forms.
