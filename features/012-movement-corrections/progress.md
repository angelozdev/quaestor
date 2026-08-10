> ▶ CP2 ACs — 5/5 criteria met | NEXT: the owner approves `acs.md`, then /engineer.atdd | BLOCKED: none

# Progress — 012 movement-corrections

A movement is corrected, not deleted. 30 acceptance criteria, no spec yet.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | 2026-08-10T1730-feature-init.md |
| 2 | ACs | **done, awaiting the owner** | 2026-08-10T1900-discover-acs.md |
| 3 | Spec | — | |
| 4 | Plan | — | |
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

## Owed before code

An ADR. This changes the write model of a posted movement, and nothing pins the
current rule today except an `update_transaction` docstring — so there is
nothing to supersede and a new one to write (CLAUDE.md).

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-08-10T1726 | discuss | main | promoted `confirm-asks-which-account`; grew into one idea; the transfer branch died measuring |
| 2026-08-10T1730 | feature-init | main | 012 allocated, branch cut from main at 9229784 |
| 2026-08-10T1815 | discuss (round 2) | main | five questions answered, then re-checked against sources; four held, one changed — the mispriced one was mine |
| 2026-08-10T1900 | discover-acs | main | 30 ACs; the last two gaps closed with the owner |
