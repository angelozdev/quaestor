---
ac_count: 19
high_priority_count: 11
discovered: 2026-08-02
---

# Acceptance criteria — 008 mandatory-categories

Discovered 2026-08-02 (Checkpoint 2), greenfield mode over existing code.
Source material: `feature.md`, the four service write paths
(`transactions._record`, `transactions.update_transaction`,
`planned.plan_payment`, `recurring.create_recurring` / `update_recurring`), the
MCP write surface, read-only measurements against the production Postgres, and
an industry comparison of how five reference systems type their categories.

## Decisions taken during discovery

**1. A category belongs to a direction.** Recording money coming in offers only
income categories; recording money going out offers only expense categories. It
is not possible to file a salary under 🍽️ Restaurants.

The industry splits on this. YNAB has no income categories at all — every
inflow lands in "Ready to Assign", and categorising an inflow into a spending
category *subtracts* from that category's spending, which YNAB documents as an
error to avoid. Actual Budget keeps exactly one income group that cannot be
deleted. Monarch fixes three types (Income, Expenses, Transfers) that cannot be
changed. Lunch Money marks a category "Treat as income" and lets the category —
not the sign — decide how money is classified, but never restricts which
category you may pick. Firefly III alone leaves categories untyped and puts the
expense-only constraint on *budgets* instead.

Quaestor's `Category` is Lunch Money's, field for field (`is_income`,
`exclude_from_budget`, `exclude_from_totals`). But Quaestor also has
`Transaction.type`, which Lunch Money does not — so Quaestor carries two
sources of truth for "does this money come in or go out" and can express a
contradiction none of the reference systems can. Production shows the owner has
been resolving it by hand: **467 categorised movements, 0 contradictions.** The
decision makes the app hold the line the owner already holds.

The consequence that settled it: feature 003 will compute funding rules from
three-month category averages. One salary of $6.223.101 filed under an expense
category drives that average negative and configures the fund wrong, silently.

**2. A missing category is created from the movement form.** No trip to the
categories screen, no losing what was already typed. This came from a real
case, not a hypothetical: four `4x1000` charges (Colombia's financial
transaction tax) had no category that fit among the owner's 34.

**3. The historical backfill happens before the rule turns on**, by hand, not
by an in-app to-fix queue. Completed 2026-08-02 — see AC-19.

**4. Skipped charges carry a category too.** Owner's position: *"cualquier cosa
que yo haga debe entrar en una categoría, debe."*

**5. A recurring item's category is copied at birth, not linked.** Changing a
recurring item's category later leaves its existing charges alone.

**6. Transfers stay uncategorised** — the rule in `feature.md` is unchanged.
Monarch and Lunch Money both *do* give transfers a category (one excluded from
budgets and totals), and the owner has already hand-built that pattern as
`🔄 Payment / Transfer`. That is a real design question, and it is **parked as
a separate discuss** rather than absorbed here.

## AC-1: Recording an expense requires a category

- **Priority:** high
- **Type:** happy-path

Money going out cannot be recorded without saying what it was for. An expense
submitted with no category is refused and nothing is stored — no movement, no
balance change. The refusal names what is missing.

## AC-2: Recording an income requires a category

- **Priority:** high
- **Type:** happy-path

Money coming in cannot be recorded without saying where it came from. An income
submitted with no category is refused and nothing is stored.

## AC-3: A transfer carries no category

- **Priority:** high
- **Type:** happy-path

Moving money between the owner's own accounts is not spending and is not
income — net worth does not change. A transfer is recorded with no category,
and attaching one is refused. Categorising a transfer would count the same
money twice: once moving into the emergency fund, again when it is finally
spent out of it.

## AC-4: The categories offered match the direction of the money

- **Priority:** high
- **Type:** happy-path

Recording income offers only income categories; recording an expense offers
only expense categories. A salary cannot be filed under 🍽️ Restaurants because
🍽️ Restaurants is not among the options — not because it is rejected
afterwards.

## AC-5: A new category can be created without leaving the form

- **Priority:** medium
- **Type:** happy-path

When nothing among the existing categories fits, a new one is created from the
same screen where the movement is being recorded. What was already typed —
payee, amount, date, account, notes — survives. The new category is available
immediately and the movement saves in one action.

## AC-6: A recurring item requires a category, and its charges inherit it

- **Priority:** high
- **Type:** happy-path

A recurring obligation cannot be set up without a category. Every charge the
engine produces from it — whether it posts, waits as planned, or is skipped —
arrives carrying that category. No charge is ever born uncategorised.

## AC-7: A planned payment requires a category

- **Priority:** medium
- **Type:** happy-path

A one-off payment scheduled for a future date carries a category from the
moment it is planned, not from the moment it is confirmed. Money that is owed
is already visible to per-category reporting.

## AC-8: Changing a recurring item's category leaves its existing charges alone

- **Priority:** medium
- **Type:** edge-case

Re-classifying an obligation applies from that point forward. Charges already
produced keep the category they were born with, so closed months never rewrite
themselves, and a single charge can be re-classified on its own without the
recurring item overwriting it next time.

## AC-9: A skipped charge carries a category too

- **Priority:** high
- **Type:** edge-case

A charge that was declined never moved money, but it still says what it would
have been for. Skipping does not open a hole in the rule.

## AC-10: An archived category keeps its history

- **Priority:** medium
- **Type:** edge-case

Archiving a category removes it from the choices offered for new movements. The
movements already filed under it keep it and stay categorised — archiving is
not a way to make money invisible again. Restoring the category brings it back
as a choice.

## AC-11: A category cannot be stripped off a movement that already has one

- **Priority:** medium
- **Type:** edge-case

Editing an expense or income can change which category it carries, but not
clear it. An edit that would leave a movement uncategorised is refused. The
rule holds for the life of the movement, not only at the moment it is created.

## AC-12: A category created from the form is born with the right direction

- **Priority:** medium
- **Type:** edge-case

A category created while recording an income is an income category; one created
while recording an expense is an expense category. The owner never has to
declare the direction separately — it is already known from what they were
recording.

## AC-13: Creating a category that already exists is refused

- **Priority:** low
- **Type:** edge-case

Creating categories from the movement form makes near-duplicates easy — typing
"Vuelos" instead of picking ✈️ Flights. A new category whose name matches an
existing active one is refused. If the match is an archived category, the app
offers to restore it instead of creating a second one. Production already
carries one such pair (`🛡️ Auto Insurance` exists twice, one archived).

**Amended 2026-08-03, after CP7 review, on two points the original wording left
open.**

*Where the rule applies:* everywhere a category is created — the movement form,
the Categorías screen, the API and the assistant — not only the form the
paragraph above describes.

*Which names collide:* **a name is unique per direction, not across the app.**
"Intereses" can exist twice, once for the ones paid to the bank and once for
the ones earned from it, and no offering ever shows the two together because
every one is already filtered by direction (AC-4). The same goes for
"Comisiones" and "Ajuste". Refusing across directions would leave the owner
told a category exists while the app declines to offer it — and would make the
advice AC-15's refusal gives ("use a category of the other direction") an
action the app then denies.

## AC-14: The rule holds on every way in, not just the form

- **Priority:** high
- **Type:** error

The same refusal happens whether the movement arrives from the app, the API, or
the agent. There is no path that can store an uncategorised expense or income.

## AC-15: A category of the wrong direction is refused

- **Priority:** high
- **Type:** error

The form prevents the mistake by not offering the option (AC-4); every other
way in refuses it outright. An income filed under an expense category is
rejected and nothing is stored.

## AC-16: An unknown or archived category is refused

- **Priority:** medium
- **Type:** error

Existing behaviour, pinned so the new rule cannot weaken it: a category that
does not exist, or one that has been archived, is refused with a message naming
which category was at fault.

## AC-17: The stored data cannot hold an uncategorised expense or income

- **Priority:** high
- **Type:** cross-cutting

The guarantee does not depend on the code being correct. An expense or income
without a category cannot be stored at all, while a transfer without one is
required. The constraint discriminates by movement type — it is not a blanket
"category is always required".

## AC-18: The change refuses to apply while any movement is uncategorised

- **Priority:** high
- **Type:** cross-cutting

Turning the rule on is blocked while historical money is still uncategorised,
and the refusal says how many movements are left and of which kind. The change
either lands on clean data or does not land.

## AC-19: The existing data is already clean

- **Priority:** high
- **Type:** cross-cutting

Completed 2026-08-02 against the production Postgres, after a fresh backup
(`quaestor-local-2026-08-02.dump`, ADR-0030):

```
expense      549 movements   0 uncategorised
income        50 movements   0 uncategorised
transfer      39 movements  39 uncategorised   ← correct, this is AC-3
recurring     14 items       0 uncategorised
direction contradictions:    0
```

131 movements were uncategorised at the start. 101 of them had been produced by
the 10 recurring items that carried no category, so setting those 10 resolved
them in one pass; the remaining 30 were classified individually. Seven
categories were created that had no equivalent before: 🎁 Bonos, 💰
Rendimientos, 💳 Cashback, 🏦 Comisiones bancarias, 💸 Impuestos, 🔧
Mantenimiento Carro, 🧽 Lavado Carro.

This AC is the precondition for AC-18, and it is met. The acceptance test
covers the *shape* of the assertion (no uncategorised expense or income
survives), not this one-time run.

## Out of scope

- **Re-categorising movements that already carry a category.** Notably the 24
  movements in `🔄 Payment / Transfer` that are typed as expenses but are not
  spending (`Ubidots (salario) -$6.223.101`, `Tyba -$29.084.436`, loans,
  Bitcoin) — the owner's hand-built workaround for the missing transfer
  category.
- **Any change to the category taxonomy itself** — groups, ordering, the
  `exclude_from_budget` / `exclude_from_totals` flags.

## Parked during discovery

Found while working the data; none belongs to this feature:

1. **Transfer categories** — Monarch and Lunch Money both support them; the
   owner has already improvised one. Separate discuss.
2. **Splitting one movement into two** — requested during the backfill (an
   Amazon charge that was half a gift and half personal). The app cannot do it;
   the split was applied by hand.
3. **Duplicate skipped charges** — the recurring engine produced two skipped
   rows for the same obligation on the same date (Claro 2026-01-28 as ids 1438
   and 1563; likewise Tigo, Ubidots and Keystone). Harmless to totals because
   they are skipped, but the engine should not do it.
4. **Negative amounts** — 16 expenses and 15 transfers are stored negative,
   while the model documents `amount` as positive cents. The owner uses them as
   refunds (`Smartfit -$70.000`, `Juca Sushi -$50.000`).
5. **Emoji collision** — 🎁 Bonos and 🎁 Gifts share an emoji, as do 💸
   Impuestos and the 💸 Income group.
