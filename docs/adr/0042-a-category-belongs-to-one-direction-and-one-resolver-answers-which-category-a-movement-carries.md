# 0042. A category belongs to one direction and one resolver answers which category a movement carries

- **Status:** proposed
- **Date:** 2026-08-03
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Quaestor carries two independent sources of truth for "does this money come in
or go out": `Transaction.type` and `Category.is_income`. Nothing stops them
from disagreeing, so a salary of $6.223.101 can be filed under 🍽️ Restaurantes
and drive that category's three-month average negative. Feature 003 will
compute funding rules from exactly those averages, silently.

At the same time, feature 008 adds three new checks (required, direction,
inline creation) to the category question — and that question is currently
answered by the same six-line block copy-pasted into **five** write paths:
`transactions._record`, `transactions.update_transaction`,
`recurring.create_recurring`, `recurring.update_recurring`,
`planned.plan_payment`. Adding three checks to five copies is how a rule
becomes five subtly different rules.

Prompted by `features/008-mandatory-categories/acs.md` (Decisions taken during
discovery, §1) and its AC-4, AC-5, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16.

## Decision drivers

- Production shows the owner already holds this line by hand: **467
  categorised movements, 0 direction contradictions.** The app should hold what
  the owner holds.
- AC-14 requires the same refusal from the app, the API and the agent — so the
  rule must sit at or below the single point all three already pass through.
- AC-4 wants the mistake prevented, not rejected: 🍽️ Restaurantes should not be
  *offered* when recording a salary.
- AC-5 requires creating a missing category without leaving the movement form,
  in one action, without losing what was typed. The real case that forced it:
  four `4x1000` charges (Colombia's financial transaction tax) fit none of the
  owner's 34 categories.
- Whatever answers "which category?" must be reusable by feature 003.

## Considered options

1. **Untyped categories; validate nothing about direction** (Firefly III's
   model — constrain budgets instead).
2. **Typed categories, checks duplicated in each of the five write paths.**
3. **Typed categories, one resolver in `services/categories.py` that every
   write path calls.**
4. **No income categories at all** (YNAB's model — every inflow lands in
   "Ready to Assign").

## Decision outcome

Chosen option: **3 — typed categories with a single resolver.**

### The direction rule

A category belongs to one direction. Recording money coming in offers only
income categories; recording money going out offers only expense categories.
A salary cannot be filed under 🍽️ Restaurantes because 🍽️ Restaurantes is not
among the options — not because it is rejected afterwards.

The industry splits on this, and the split was surveyed before deciding
(recorded in full in `acs.md`):

| System | How it types categories |
|---|---|
| YNAB | No income categories at all; inflows go to "Ready to Assign", and categorising an inflow into a spending category *subtracts* from that category's spending — documented as an error to avoid |
| Actual Budget | Exactly one income group, undeletable |
| Monarch | Three fixed types (Income, Expenses, Transfers), unchangeable |
| Lunch Money | `Treat as income` on the category; the category, not the sign, classifies — but never restricts which category you may pick |
| Firefly III | Categories untyped; the expense-only constraint sits on *budgets* |

Quaestor's `Category` is Lunch Money's field for field (`is_income`,
`exclude_from_budget`, `exclude_from_totals`). But Quaestor also has
`Transaction.type`, which Lunch Money does not — so it can express a
contradiction none of the reference systems can, and closing it is a
Quaestor-specific decision rather than a copy of anyone's model.

The predicate itself is a pure function in `domain/rules.py` — no session, no
model, testable alone, and the form feature 003 will read.

### The resolver

`services/categories.py` grows one function that every write path calls:

```python
def resolve_for_movement(session, tx_type, category_id=None, new_category=None) -> int | None
```

It returns the category id to store, or raises. It is the single answer to
"which category does this movement carry?":

| Input | Outcome | AC |
|---|---|---|
| `tx_type` is `transfer` with any category | refused; returns `None` | AC-3 |
| neither `category_id` nor `new_category` | refused: the category is missing | AC-1, AC-2, AC-6, AC-7 |
| both | refused as ambiguous | — |
| `new_category` | created with `is_income = (tx_type == income)`; refused if an active category holds the name; if an **archived** one does, refused with an offer to restore it | AC-5, AC-12, AC-13 |
| `category_id` | must exist, not be archived, and match the movement's direction | AC-15, AC-16 |

`AC-11` (a category cannot be stripped off a movement that already has one)
falls out of routing `update_transaction` through the same function: clearing
is "neither given" on an expense, which the first rule already refuses.

**AC-14 comes free.** The app, the REST API and the MCP tools already funnel
through `services/`. There is no fourth door to guard.

The offering (AC-4, AC-10, AC-12) is a filter argument on the existing read —
`list_categories(session, include_archived=False, is_income=None)`, surfaced as
`GET /categories?is_income=true` — not a new function.

### Pros and cons of the options

**1 — Untyped categories**
- Good, because it is the smallest change and matches Firefly III.
- Bad, because it leaves the contradiction expressible, and feature 003 reads
  the averages it corrupts.

**2 — Typed, duplicated in five paths**
- Good, because no new module boundary, and each path reads standalone.
- Bad, because the existing six-line block is already duplicated five times and
  this triples its size; the five copies would drift.

**3 — Typed, one resolver (chosen)**
- Good, because the rule has one definition, one place to test, and one place
  for feature 003 to read.
- Bad, because a write path now depends on `services/categories.py` —
  `transactions.py` and `planned.py` gain a sibling-service import.

**4 — No income categories**
- Good, because it removes the contradiction by removing one side of it.
- Bad, because it discards the owner's existing 💼 Salary and the seven income
  categories created during the 2026-08-02 backfill, and answers "where did
  this money come from?" with nothing.

## Consequences

- Good: a salary filed under a spending category is refused on every surface,
  and the wrong option is never offered on the form.
- Good: five copies of the category check collapse into one call.
- Good: feature 003's funding rules read a direction-consistent average, so an
  income of $6.223.101 can no longer drive an expense category negative.
- Good: the `4x1000` case is solved without leaving the movement form.
- Bad / cost: `services/transactions.py` and `services/planned.py` now import
  `services/categories.py`. Accepted: the alternative is the rule living in
  five places.
- Bad / cost: category creation acquires a uniqueness rule it never had.
  Production already carries one violating pair (`🛡️ Auto Insurance` exists
  twice, one archived) — which is precisely why AC-13 offers to restore the
  archived match instead of refusing flatly.
- Bad / cost: the frontend category select must be re-queried when the
  movement's type changes, and `allowNullLabel="Sin categoría"` is removed from
  `transaction-create-dialog.tsx`. That option *is* the gap.
- Neutral: `Category.is_income` already exists and production is already
  consistent, so no data migration is needed for the direction rule itself.

## Confirmation

`features/008-mandatory-categories/spec.md`: AC-4 (3 scenarios), AC-5 (3),
AC-10 (2), AC-11 (2), AC-12 (2), AC-13 (2), AC-14 (3), AC-15 (3), AC-16 (2).

AC-14's three scenarios call the MCP tool bodies directly, beneath the
`_as_text` wrapper, so the assistant path is proven to refuse rather than merely
to format a refusal. Mutation testing is opted in for `domain/rules.py` and
`services/categories.py` — the resolver is the single point of enforcement, so
a surviving mutant there is a hole in the whole rule.
