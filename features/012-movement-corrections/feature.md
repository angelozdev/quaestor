---
title: "A movement is corrected, not deleted: which account it came out of, and the number on it"
slug: movement-corrections
number: 012
status: ready
autonomy_level: medium
branch: movement-corrections
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: confirm-asks-which-account
acceptance_stream: mixed
relevant_adrs: [0023, 0031, 0032, 0034, 0038, 0042, 0045]
created: 2026-08-10
intake: discuss
---

# A movement is corrected, not deleted: which account it came out of, and the number on it

## Outcome

When what the owner wrote down and what actually happened disagree, he fixes the
line instead of destroying it. He picks the account at the moment he confirms a
payment — not weeks earlier when he planned it — and if the account he really
paid from is in another currency, the amount comes with it. A movement already
recorded can move to another account, and its number can be corrected, without
losing its date, its category, its tags, or the meta it was pointed at.

## Scope

- **Confirming names the account.** The confirm dialog offers every live
  account, including accounts in another currency. The planned account comes
  preselected, so confirming unchanged stays one click.
- **Changing to a foreign-currency account converts.** The amount box is
  prefilled with the division at the app's single TRM and stays editable — the
  owner overwrites it with what the statement actually says. The movement is
  then stored in that account's currency. Read-time conversion (ADR-0031) is
  untouched; no per-movement rate is frozen.
- **The recurring declaration does not move.** Confirming Hogaru from RappiCard
  is an exception for that month. September proposes Nu Débito again. A real
  move of accounts is made once, on the recurring item.
- **A posted expense or income can change account.** Both balances adjust. If
  the destination account is in another currency, the amount changes with it
  under the same rule as above.
- **Each leg of a posted transfer moves on its own.** The leg that went out and
  the leg that came in are two separate corrections.
- **A posted movement's amount can be corrected** without changing its account.
  The balance adjusts by the difference.
- **Three surfaces.** The *Por pagar* and *Movimientos* screens, the REST API,
  and the assistant — `confirm_payment` and `update_transaction` already exist
  as MCP tools and would otherwise be the only surfaces that cannot do this.
- **Out of scope:** the account at *plan* time (already required, unchanged);
  changing a movement's type; any change to how the recurring item is declared
  (that is `id:recurring-currency-independent-of-account`); anything about
  closing a month.

## What the discuss decided, and why

Decided 2026-08-10 with the owner, question by question, each against measured
production numbers.

| Question | Decision |
|---|---|
| Which accounts does confirming offer? | **All of them**, including other currencies |
| What happens to the amount on a foreign-currency account? | **Prefilled** with the TRM division, editable |
| Does confirming from another account move the recurring declaration? | **No** — an exception for that month |
| Do transfers take part? | **Yes**, each leg on its own |
| Can the amount alone be corrected? | **Yes** |

The last two are where the owner overrode the recommendation, and the reason he
gave for the last one is the load-bearing one: once the number can change while
changing the account, refusing to change it when the account is already right is
a hole with no explanation.

## What was measured before deciding, not assumed

Every figure below was read from the production database on 2026-08-10.

**A planned transfer cannot exist, so its branch was never a question.** Only
two places create a `planned` movement: planning by hand, which makes an expense
and nothing else, and the recurring engine, whose model states in its own
docstring that the type is expense or income and *never* transfer. Production
holds 14 recurring expenses, 3 incomes, 0 transfers, and
`settings.default_source_account_id` is empty, so `_materialize_planned_transfer`
would refuse anyway. The roadmap item listed this as an open decision; it is a
dead branch.

**The month's arithmetic never reads the account.** `month_aggregate.py` does not
name it once. Moving a movement between accounts moves two balances and no
budget, fund, meta or savings-split figure.

**The drift has never been recorded because it cannot be.** All 59 charges made
against the 17 recurring items came out of exactly the account declared —
`count(distinct account_id) = 1` for every one. That measures the constraint,
not the owner's life: the confirm dialog has no account field to disagree with.

**Deleting is not neutral today.** Deleting an engine-made charge fires
`close_date_of_deleted_charge`, which marks that due date **skipped** and unlinks
it (`occurrences.py:331`, ADR-0038 — deliberate, so the date is not consumed
forever). So today's only remedy for a wrong account on a recurring charge —
delete and recreate — leaves that month reading as *omitido* and the replacement
movement hanging off nothing.

**Cross-currency transfers are real.** 25 transfer pairs, 3 of them across
currencies. The widest: DolarApp **US$1.556,04** → Préstamos a terceros
**$5.000.000**.

**The USD surface is not marginal.** 266 posted movements in USD against 355 in
COP. TRM 3.142,00.

## Verified against current practice before deciding

| System | Change a posted transaction's account? | How |
|---|---|---|
| Actual Budget | **Yes** | Bulk-editable; the docs name the reason: *"perhaps due to a manual entry or import error"*. No restriction documented |
| Actual Budget | — | Reconciled rows are *locked*: editing warns and asks to confirm, then stays locked. A guard, not a prohibition |
| Firefly III | **Yes**, and this is where it breaks | Issue #4589: changing source/destination silently does not save. Issue #3921: balances altered by past transactions. Ships `firefly-iii:correct-database` to repair |
| YNAB | Editing is offered broadly; the support article does not enumerate the fields | Transfers approve on both sides at once, so the pair is treated as one thing |

The Firefly finding is the one that shapes the plan. **`account.balance` in
Quaestor is a stored column that nothing recomputes** — the same shape that
produced both of those bugs. Every correction in this feature moves it by hand.
That is the risk to design against, not the feature's user-facing behaviour.

## Open questions for CP2

| Question | Why it is open |
|---|---|
| Does the stored balance stay stored? | Firefly's two bugs are both this. A derived balance, a checked invariant, or an explicit reconciliation are three different answers with different costs |
| Cross-currency: what exactly is stored on the moved movement? | The amount is in the new account's currency; the peso figure is derived at read time (ADR-0031). Whether the old amount survives anywhere is undecided |
| What refuses a correction? | Archived accounts (Korea is archived) are not offered. Whether anything else refuses — a movement already linked to a completed meta, an engine charge — is undecided |
| Does a transfer leg moving to another currency change what the other leg says? | The 3 cross-currency pairs already carry different amounts per leg, so possibly nothing changes. Needs a worked example |
| Does the assistant get the same power? | `update_transaction` as an MCP tool today edits payee/notes/category/date/tags. Extending it hands the assistant the balance-moving path |

## Charter signals

- **No migration.** A movement already carries its account; correcting one writes
  a different value. No new table, no new column, so CHARTER §7's migration
  clause does not apply and neither does the `migrations/**` autonomy cap.
- **An ADR is required before code.** This changes the write model of a posted
  movement. Nothing pins the current rule today — `update_transaction`'s
  docstring says *"amount/account/currency/type are immutable here, so no balance
  ever moves"*, and no ADR states it. So there is nothing to supersede, and a new
  ADR to write.
- **This is the highest-risk write in the app.** It is the only path that moves
  two stored balances at once, and it runs against real money.
- **Every refusal still speaks English** until `id:error-contract` ships. Known,
  tracked, does not block.

## Found while measuring, not this feature's, filed rather than fixed

46 recurring occurrences dated January–July 2026 read `skipped` while still
carrying a `transaction_id`. `close_date_of_deleted_charge` sets that field to
`None`, so these did not come from a deletion — they look like the historical
import reconciling itself against movements that already existed. Plausible and
probably deliberate, but nothing states it.
