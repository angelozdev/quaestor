---
slug: "2026-08-11-a-recurring-charge-cannot-live-in-a-dollar-account"
title: "A recurring charge cannot be created in, or moved to, an account that holds dollars"
severity: high
blocks_user: true
workaround: "none from the screen. The charge has to be created against a peso account, and each occurrence corrected to the dollar account by hand once it is posted."
status: investigating

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

followups:
  - category: inadequate_verification
    action: "Pin before fixing: creating a recurring charge against a USD account must send currency USD, and moving an existing one to a USD account must restate its currency."
    status: open
  - category: missing_ac
    action: "Decide whether a recurring charge in a foreign currency is in scope, and if so state it as an AC. The owner's own production data says yes — Opal, Hevy Pro, DolarApp Premium and Smart Fit are all dollar subscriptions, and the roadmap item id:fund-smooths-an-annual-charge already reasons about them by name."
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
