---
title: "Metas: named savings goals that live beside the fund, not inside it"
slug: named-goals
number: 009
status: ready
autonomy_level: medium
branch: named-goals
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: named-goals
relevant_adrs: [0005, 0006, 0028, 0043, 0044]
created: 2026-08-05
intake: discuss
---

# Metas: named savings goals that live beside the fund, not inside it

## Outcome

The owner can save for a named thing — a phone, a television — as many at a time
as he likes, without inventing a category for each one and without touching how
funds work. A meta asks for its own monthly share automatically, so no month
requires an act of saving. When the thing is finally bought, the owner links the
expense to the meta: the meta counts it and closes, the category's fund is left
untouched, and the app asks what comes next — close it, raise the amount, or
move the date.

## Scope

- **A new noun beside the fund.** A meta has a name, a target amount and a
  target month. It does **not** belong to a category, and a category may carry
  any number of metas — or none. Nothing about the fund changes; the
  one-fund-per-category constraint (AC-25) stays exactly as it is.
- **It fills itself.** A meta's monthly share is derived from what is left to
  save and how many months remain, the same way a dated fund derives its ask.
  Not touching the app for a month still advances the meta. Contributing extra
  on top is allowed but never required.
- **It costs the month.** What every meta asks joins what every fund asks in
  the money-available figure, so the headline number already accounts for it.
- **The purchase is linked, once.** Recording the expense, the owner may point
  it at a meta. That expense counts toward the meta and is excluded from the
  category's fund arithmetic, so a $8.000.000 phone does not read as a
  $7.900.000 overspend on a $100.000 Tecnología budget.
- **It ends, and it says so.** Reaching the target stops the asking. Linking
  the purchase completes the meta and prompts for the next step: close, renew
  with a new amount, or renew with a new date.
- **Lifecycle** follows the project's uniform soft-delete + restore stance
  (ADR-0005).
- **Out of scope:** any change to the fund's rules, its fold, or its
  one-per-category constraint; any coupling of a meta to an account
  (deliberately refused — see below); the fund-rule naming problem, which is
  its own roadmap item (`id:fund-vs-budget-vocabulary`).

## What the discuss decided, and why

Decided 2026-08-05 with the owner, question by question, each against numbers.

| Question | Decision |
|---|---|
| Does a meta live in a category? | **No.** The link is made on the movement, not on the classification |
| Who fills it? | **The app**, monthly, automatically |
| Does the contribution cost the month? | **Yes** — it joins what the funds ask |
| What happens on the purchase? | The expense is **linked to the meta and excluded from the fund** |
| What happens when it completes? | The app **asks**: close, new amount, or new date |

The category question is the one that unlocks the rest. The roadmap item feared
that several funds on one category could not answer *"which one did this
$200.000 charger come out of"*, and that asking per purchase would reinstate the
monthly ritual feature 003 exists to delete. Linking on the movement dissolves
it: the ordinary charger is linked to nothing and behaves exactly as it does
today, and the one purchase that matters is named once, on the day it happens —
an event, not a ritual.

## Verified against current practice before deciding

| System | Separate noun? | In a category? | Spending the saved money |
|---|---|---|---|
| YNAB | No — a *target* on the category | It **is** the category | Hits the category; YNAB asks you to top it up |
| Actual Budget | No — templates that auto-assign | It **is** the category | Same |
| Firefly III | Yes — *piggy banks* | No | Tied to a real savings account |
| Monarch Money | Yes — *Goals* | No | **Linked expense counts in the goal, budget actuals untouched** |

Three findings carried the decision:

1. **YNAB has this exact constraint today** — one target per category per month,
   the same shape as Quaestor's one fund per category. Its users work around it
   by creating a category per goal, which is precisely the workaround already
   recorded here. The limit is not Quaestor's; it is what happens when the goal
   is put *inside* the category.
2. **Monarch already ships the chosen behaviour**, and documents an asymmetry
   worth copying: linked *contributions* do count against the budget (that money
   is genuinely being set aside), while linked *expenses* do not (that money was
   set aside already). Charging it twice is the obvious error.
3. **Firefly III ties a piggy bank to an asset account** and refuses to hold more
   than that account contains — exactly the coupling ADR-015 removed and ADR-037
   confirmed gone. Not reopened.

## Open questions for CP2

Deliberately left undecided — they are AC-discovery material, not discuss
material:

- Buying the thing with less than the target saved (the $8.000.000 phone bought
  with $6.000.000 put by).
- Cancelling a meta: where the money it was holding goes.
- A meta with no date — *"$5.000.000, whenever it gets there"*.
- Whether the assistant can create metas and contribute to them (REST/MCP
  parity, ADR-0006/0009).
- Metas in a currency other than COP.
- How metas and funds sit together on the screen the owner actually reads.

## Charter signals

- **A new table means a migration.** CHARTER §7 requires the owner explicitly,
  and `backend/src/quaestor/migrations/**` is capped at autonomy `low` by the
  manifest regardless of this feature's level. ADR-0030 requires a fresh
  `just backup` before any migration touching real data.
- **An ADR is required before code** — a new domain noun and its write path is
  architecturally significant (CLAUDE.md).
- **Every new screen speaks English on refusal** until `id:error-contract`
  ships. Known, tracked, does not block.
