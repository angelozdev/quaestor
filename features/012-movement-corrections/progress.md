> ▶ CP4 Plan — 6/6 criteria met | NEXT: /atdd:atdd-team — slice 1, the core and the proof | BLOCKED: none

# Progress — 012 movement-corrections

A movement is corrected, not deleted. 30 acceptance criteria, 66 scenarios —
53 against the logic, 13 against the screen. Red: 51 failed, 2 passed, the two
being declared control arms.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | 2026-08-10T1730-feature-init.md |
| 2 | ACs | done — approved by the owner 2026-08-10 | 2026-08-10T1900-discover-acs.md |
| 3 | Spec | done — approved by the owner 2026-08-10 | 2026-08-10T2015-atdd.md |
| 4 | Plan | done — ADR-0051 accepted | 2026-08-10T2140-plan.md |
| 5 | Implement | — | |
| 6 | Refine | — | |
| 7 | Verify | — | |
| 8 | Harden | — | |

## The two rules everything derives from

1. **The record survives the correction.** It keeps its identity, date,
   beneficiary, category, tags, meta and recurring due date.
2. **No money figure moves without being seen, and nothing is saved unless the
   arithmetic proves out.** Both balances must move by exactly the declared
   deltas or the whole correction is undone.

## Decided across two discuss rounds

| | |
|---|---|
| Which accounts confirming offers | all of them, other currencies included |
| Foreign-currency amount | prefilled at the app's rate, editable — on both screens |
| Confirming from another account | a one-month exception; the obligation is untouched |
| Transfers | each leg moves alone; same-currency halves move together; cross-currency asks both |
| Correcting the amount alone | yes |
| What a correction remembers | nothing of what it said before |
| The assistant | gains nothing, deliberately |
| The stored balance | never rebuilt; each correction's arithmetic checked |

## What must never be built

Rebuilding `account.balance` from the sum of its movements. Six of nine accounts
disagree with that sum and none is an error — an account's opening figure is
written straight to its balance and appears in no movement. Writing the sum in
would destroy $2.101.837,94 on Nu Débito alone. Filed as
`id:account-opening-balance-and-audit`.

## Owed, and when

**Paid:** the ADR. `docs/adr/0051` — accepted 2026-08-10. Nothing was superseded,
because nothing recorded the old rule except an `update_transaction` docstring.

**Still owed, at CP6:** verification independence. This session does not dispatch
subagents unless asked, so CP6/CP7 need either the owner invoking fresh agents or
his authorisation to dispatch. 009's CP6 ran on the implementing agent and an
independent review afterwards found six user-facing defects in merged code.

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-08-10T1726 | discuss | main | promoted `confirm-asks-which-account`; grew into one idea; the transfer branch died measuring |
| 2026-08-10T1730 | feature-init | main | 012 allocated, branch cut from main at 9229784 |
| 2026-08-10T1815 | discuss (round 2) | main | five questions answered, then re-checked against sources; four held, one changed — the mispriced one was mine |
| 2026-08-10T1900 | discover-acs | main | 30 ACs; the last two gaps closed with the owner |
| 2026-08-10T2015 | atdd | main | 66 scenarios; red on 30 unbound step texts; 224 existing steps reused where they fit |
| 2026-08-10T2140 | plan | main | ADR-0051 accepted; correcting = reverse + restate + apply + prove, reusing what delete already does |
