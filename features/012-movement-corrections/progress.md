> ▶ CP6 Refine — 5/5 criteria met | NEXT: /engineer.crap-analyzer for CP7, on a fresh agent | BLOCKED: none

# Progress — 012 movement-corrections

A movement is corrected, not deleted. 30 acceptance criteria, 66 scenarios —
53 against the logic, 13 against the screen. **All green**, and the whole
project's pipeline with them.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | 2026-08-10T1730-feature-init.md |
| 2 | ACs | done — approved by the owner 2026-08-10 | 2026-08-10T1900-discover-acs.md |
| 3 | Spec | done — approved by the owner 2026-08-10 | 2026-08-10T2015-atdd.md |
| 4 | Plan | done — ADR-0051 accepted | 2026-08-10T2140-plan.md |
| 5 | Implement | done — all four slices, both streams green | 2026-08-10T2340-implement.md |
| 6 | Refine | **done** — 25 fresh agents; four user-facing defects and a money hole | 2026-08-11T0400-refine.md |
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

**Paid:** the ADR (`docs/adr/0051`, accepted 2026-08-10; nothing superseded,
because nothing recorded the old rule except a docstring) and verification
independence — the owner authorised dispatch on 2026-08-10 and CP6 ran on 25
fresh agents while `main-session` wrote none of it.

**Still owed, at CP7 and CP8:** the same independence. And the mutation policy
this feature opted into matters more than usual: AC-23's verification is a check
that must be able to fail, so a surviving mutant inside it would mean it cannot.

## What CP6 found, after both streams were green

The feature did not work on the screen. Every same-currency correction returned
422, so AC-7 and AC-8 had no path for the owner — and the vitest test asserted
the rejected body byte-for-byte, passing only because the client was mocked.
Three more defects, one hazard, and then a money hole nobody had reported:
moving one leg of a cross-currency transfer into its counterpart's currency left
the halves disagreeing by $110.922 on production's own numbers.

**The worst of it was in the spec, not the code.** An approved scenario asserted
that hole as the correct outcome. It was measured against the code rather than
against the rule the owner had decided in the same session — and a green suite
defended it for as long as it stood.

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-08-10T1726 | discuss | main | promoted `confirm-asks-which-account`; grew into one idea; the transfer branch died measuring |
| 2026-08-10T1730 | feature-init | main | 012 allocated, branch cut from main at 9229784 |
| 2026-08-10T1815 | discuss (round 2) | main | five questions answered, then re-checked against sources; four held, one changed — the mispriced one was mine |
| 2026-08-10T1900 | discover-acs | main | 30 ACs; the last two gaps closed with the owner |
| 2026-08-10T2015 | atdd | main | 66 scenarios; red on 30 unbound step texts; 224 existing steps reused where they fit |
| 2026-08-10T2140 | plan | main | ADR-0051 accepted; correcting = reverse + restate + apply + prove, reusing what delete already does |
| 2026-08-10T2340 | implement | main | four slices; 66/66 scenarios; ten spec defects of my own, all measured before fixing; one 184-line test file clobbered and restored |
| 2026-08-11T0400 | refine | 25 fresh agents | 44 findings, 6 survived adversarial verification; 4 user-facing defects, 1 hazard, 1 money hole; main-session dispatched and wrote nothing |
