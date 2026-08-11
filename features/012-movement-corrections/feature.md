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
- **Two surfaces: the screens and the REST API.** The *Por pagar* and
  *Movimientos* screens and the endpoints behind them. **The assistant is
  deliberately left out** — `confirm_payment` and `update_transaction` exist as
  MCP tools and stay exactly as they are. Correcting a movement is the only path
  that moves two stored balances at once, and it is not handed to a surface with
  no screen to review it on. Decided 2026-08-10 by the owner.
- **Every correction proves its own arithmetic.** Both balances are read before
  and after; each must have moved by exactly its expected delta. Anything else
  rolls the whole correction back and says so. The starting figures are never
  questioned and never rebuilt.
- **Nothing is refused except a closed account.** An archived account is not
  offered as a destination. Everything else corrects: a purchase that completed
  a meta, an engine-made charge, a movement of any age.
- **Out of scope:** the account at *plan* time (already required, unchanged);
  changing a movement's type; any change to how the recurring item is declared
  (that is `id:recurring-currency-independent-of-account`); anything about
  closing a month; extending the assistant.

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
| Does a correction remember what the line said before? | **No** — it forgets |
| Can anything move into an archived account? | **No** |
| Does correcting a purchase reopen the meta it completed? | **No** — the meta stays fulfilled whatever the new number says |
| Does correcting one month's charge teach the recurring item? | **No** — the declaration always wins |
| A transfer leg moving to another currency | The app **stops and asks** what really arrived; it never converts that number silently |
| Is the stored balance rebuilt from the movements? | **No** — it stays a stored number and its history is never questioned |
| Is each correction's arithmetic checked? | **Yes** — both balances must move by exactly the expected delta or the whole correction rolls back |
| Does the assistant get this power? | **No** |

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

### Checked again on 2026-08-10, at the owner's instruction

Each decision was put back against current sources before being written down.
Four held; one was changed.

| Decision | Verdict |
|---|---|
| A correction forgets what the line said before | **Held.** The immutable-ledger rule (compensating entries, WORM, never overwrite) is driven by SEC / FCA / MAS obligations that do not exist for a single owner with no auditor. GnuCash — the nearest single-user comparable — edits a past transaction in place |
| Nothing moves into an archived account | **Held.** Standard |
| The meta stays fulfilled whatever the corrected number says | **Held**, and already stated by ADR-0048 |
| The recurring declaration never learns from a corrected month | **Held.** Editing an occurrence does not edit its schedule, in every comparable |
| A transfer leg crossing currencies stops and asks | **Held**, and stricter than the confirm dialog, which prefills |
| The stored balance is never checked | **Changed.** Nobody recommends stored-and-never-verified: the design consensus is stored-and-reconciled, and Beancount — single-user, no regulator — makes the `balance` assertion its flagship for exactly this reason. The framing offered to the owner was also wrong: checking the arithmetic of each correction needs no opening balance, no column and no migration. Once separated from auditing history, he took it |

## The stored balance cannot be checked, and that is now a decision

Measured 2026-08-10, after the Firefly finding: summing every posted movement
per account and comparing against the stored `account.balance`.

| Account | Stored | Sum of movements | Gap |
|---|---|---|---|
| 💵 DolarApp | US$1.998,81 | −US$1.621,72 | US$3.620,53 |
| 🏦 Nu Débito | $6.230.545,62 | $4.128.707,68 | $2.101.837,94 |
| 💳 Nu Crédito | $0 | $2.175.396,96 | −$2.175.396,96 |
| 💳 RappiCard | −$90.525,00 | $197.183,23 | −$287.708,23 |
| 🆘 Emergency Fund | $30.805.146,28 | $8.370.000,00 | $22.435.146,28 |
| 📈 DolarApp Invest | US$27.000,00 | US$2.000,00 | US$25.000,00 |
| 🇰🇷 Korea · 🤝 Préstamos · 💰 Earnings | — | — | **exact** |

**Six of nine disagree, and that is not evidence of a bug.** `account` has
exactly six columns and none of them is an opening balance: the figure typed
when an account is created seeds `balance` directly and is written to no
movement. So the gap is whatever the account held before its first recorded
line.

The consequence is the point. **Three different things produce an identical
gap** — a legitimate opening balance, the hand adjustment made to RappiCard on
2026-08-09, and a correction applied wrongly three months ago. The app cannot
tell them apart, because it never wrote the first one down.

**Rebuilding the balance from the movements is therefore forbidden.** Writing
the sum into `account.balance` would take Nu Débito from $6.230.545,62 to
$4.128.707,68 and destroy $2.101.837,94 of real money. The gaps are data the
app never recorded, not errors to correct.

**What is checked instead is the arithmetic of each correction.** Both balances
are read before, the expected deltas are known exactly, and both are read again
after. If either moved by anything other than its expected delta, the whole
correction rolls back and says so. This is deliberately blind to the starting
figures: an account off by $2.101.837,94 stays off by exactly that, and the
three that reconcile exactly keep reconciling exactly. It cannot repair old
drift and it cannot create new drift — which is precisely the pair of Firefly
bugs it exists to prevent (#4589, a change that silently does not save; #3921,
a balance altered by more than the movement).

**Recording the opening balance so history could be audited was priced and
declined** — a new column, a migration, CHARTER §7, the `migrations/**` autonomy
cap, and nine figures only the owner can supply. Beancount's `balance` assertion
is that design; it is not this feature's.

## Open questions for CP2

| Question | Why it is open |
|---|---|
| Are "prefilled and editable" and "stops and asks" the same behaviour? | Confirming a payment prefills the TRM division; moving a transfer leg across currencies stops and asks. Both were decided by the owner in the same session, in different words. Whether the transfer leg also prefills, or must be typed from empty, is undecided |
| Does the other leg of a transfer notice? | The 3 cross-currency pairs already carry different amounts per leg, so possibly nothing happens to it. Needs a worked example |
| Can a movement be moved *out of* an archived account? | Korea is archived and holds nothing, so it is moot in production — but the rule still has to be stated |
| Does correcting an engine-made charge keep its link to the recurring item? | Deleting one deliberately unlinks it and marks the date skipped (ADR-0038). Correcting must not, or the correction inherits the bug the feature exists to avoid |

## Charter signals

- **No migration.** A movement already carries its account; correcting one writes
  a different value. No new table, no new column, so CHARTER §7's migration
  clause does not apply and neither does the `migrations/**` autonomy cap. This
  held only because the owner declined the opening-balance column — the one
  choice in this feature that would have introduced a migration.
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
