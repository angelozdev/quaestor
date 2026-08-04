# 0043. A fund replaces the envelope and the goal, and its balance is derived

- **Status:** proposed
- **Date:** 2026-08-04
- **Deciders:** Angelo
- **Supersedes:** 0006 (both halves — its goals write API and its budget
  envelope write API), 0005 in part (the goal clause of the uniform
  soft-delete lifecycle)
- **Superseded by:** —

## Context and problem statement

Quaestor carries two mechanisms for the same intention. An **envelope**
(`Budget`: category, month, amount) sets money aside for a category with
rollover. A **goal** (`Goal` + `GoalContribution`) sets money aside for a
purpose and counts progress from contribution rows against a savings account it
forces the user to link. Feature 003 collapses them into one noun, the fund.

Production proves the mismatch rather than predicting it:

- **Zero `Budget` rows have ever existed.** Not one envelope was created in the
  app's history, so the envelope surface has no users and no data to migrate.
- **One `Goal`, zero `GoalContribution` rows**, and it is wrong in exactly the
  way the design predicts: `Korea` shows `$0 of $10.000.000` while the account
  it was forced to link holds `$14.659.572`. Progress counts contribution rows,
  not the balance of the account the goal demanded. The owner's own correction
  during AC discovery — *"olvida la cuenta"* — is this feature's thesis: the
  $10.000.000 exist and have simply never been registered.

Both reference implementations agree. YNAB and Actual Budget have no goals
feature at all: a goal is one target type among several on a category, and
neither involves an account. Monarch does tie goals to accounts, but Monarch is
a net-worth tracker that already ingests bank balances.

The open question this ADR answers is not *whether* to merge them but **what a
fund stores**. A fund must report what it asks this month and what it holds; the
naive shape stores a running balance and mutates it on every movement.

Prompted by `features/003-sinking-funds/` (acs.md AC-1, AC-8, AC-13, AC-19,
AC-21, AC-25, AC-26; spec.md, 92 scenarios).

## Decision drivers

- **The rule is the number — there is no monthly ritual** (feature.md decision
  2). YNAB and Actual both require a monthly button that distributes money into
  categories. The owner's envelope history is empty; any design needing a
  recurring manual action ends up empty again. A configured fund must cost zero
  clicks per month forever.
- **Nothing is frozen** (acs.md decision 6, AC-16). Every figure in Quaestor is
  already derived from what is known now, including past months. A stored
  balance is a snapshot, and snapshots drift from the rules that produced them.
- **No fund↔account coupling.** The coupling is the defect this feature exists
  to remove (AC-19).
- **Product ADR-005 survives unchanged**: overspend eats the pool, a fund never
  carries a negative balance forward (AC-13).
- The schema change must survive an app that is wrong or bypassed, per the
  posture ADR-0041 set for feature 008.

## Considered options

1. **A `fund` row with a stored `balance` column**, mutated by every expense in
   its category and by a month-close job that adds the monthly ask.
2. **A `fund` row plus one `fund_month` row per (fund, month)**, storing what
   was asked and what was held — the YNAB/Actual model, where an assignment is a
   stored fact.
3. **A `fund` row storing only the rule, with the balance derived by a forward
   fold** over the spending the month aggregate already loads, anchored by a
   single owner-stated opening figure.

## Decision outcome

Chosen option: **3 — the rule is stored, the balance is derived**, because it is
the only one of the three that satisfies "no monthly ritual" and "nothing is
frozen" at once. Options 1 and 2 both need a job or a click to advance the
balance each month, and both let the stored figure disagree with the rule that
produced it.

`fund` holds one row per expense category (unique), carrying: the rule
(`fixed` | `average` | `from-recurring` | `target-by-date`), the rule's own
parameters (fixed amount, average window in months, target amount and target
month), the start month, whether it accumulates, and the anchor described
below. It holds **no balance and no account reference**.

The fold, from the fund's start month forward:

```
holds(M)     = max( opening(M) − spent(M), 0 )
opening(M+1) = max( opening(M) + asks(M) − spent(M), 0 )   # accumulating
opening(M+1) = 0                                            # resetting
```

`spent(M)` is the category's posted expense total for the month, which
`MonthAggregate._spent_by_cat_month` already holds for all of history.

**What the fund asks is one formula for all four rules**: *what is still missing
÷ the months from this one through the month before the charge*, floored at one
month. The dated rules (`from-recurring`, `target-by-date`) supply a charge
month; the undated ones (`fixed`, `average`) do not and so divide by one.

Two consequences fall out rather than being coded:

- **AC-6 — the month the charge lands does not contribute.** By that month the
  fund is already whole, so *what is missing* is zero and it asks zero. No
  special case.
- **An obligation due this month asks for its full amount.** Zero months remain,
  the floor makes it one, and the fund needs the money now. Same formula.

### The anchor, and why it is not a snapshot

One stored pair — `(anchor_month, anchor_amount)` — states what the fund held at
the start of a month. It is written at creation (AC-19: *"the owner may type
what the fund already holds"*) and rewritten when the owner corrects it. The
fold starts from it instead of from zero.

This is a **statement by the owner**, not a computed figure, which is why it does
not contradict AC-16. Nothing in the app ever writes it; nothing reads it from
an account. AC-19's second and third scenarios pin exactly that: a $9.000.000
savings account sitting beside the fund changes nothing, before or after.

### What this deletes

`Budget`, `set_budget`, the `assign_budget` MCP tool and the budgets screen go
with `Goal`, `GoalContribution`, `Transaction.goal_id`, `services/goals.py`, its
router, `goals_reads`, the `propose_goal_contributions` rollover hook and the
goals screen.

Deleting the envelope alongside the goal is not scope creep: a `fixed`
accumulating fund **is** an envelope. Keeping both would leave two ways to
depress the same headline — which is the shape of consolidation defect C14,
where `set_budget` accepts an envelope on an income category and depresses
safe-to-spend permanently with no way to clear it. AC-22 is that refusal on the
surface that replaces it.

### Pros and cons of the options

**1 — stored balance, mutated**
- Good, because reading what a fund holds is a single column read.
- Bad, because it needs a month-close job to add the monthly ask, which is the
  ritual feature.md decision 2 rules out.
- Bad, because the stored figure and the rule drift the moment either changes,
  and Quaestor has no reconciliation surface to notice.
- Bad, because it reintroduces per-movement writes on a read path that ADR-0028
  deliberately made bounded and read-only.

**2 — one row per (fund, month)**
- Good, because it matches YNAB and Actual, where what was assigned in August is
  a stored fact, and a screenshot of August always matches the app.
- Bad, because it needs the same monthly ritual to create the rows.
- Bad, because it contradicts AC-16, which the owner chose knowingly: switching
  a recurring item off today changes August's figure too.
- Bad, because it stores 12 rows a year per fund to hold information that is
  already computable from the rule.

**3 — rule stored, balance derived (chosen)**
- Good, because a configured fund costs zero clicks per month, forever.
- Good, because the fold reuses data the month aggregate already loads: no new
  history query.
- Good, because product ADR-005 (no negative rollover) is the `max(…, 0)` in the
  fold, not a second mechanism.
- Bad, because a screenshot of August's number will not always match the app
  later. Stated as the accepted cost in AC-16.
- Bad, because the fold is O(funds × months since the earliest start). At the
  real scale — 7 funds, 12 months — that is 84 in-memory steps, but it grows
  without bound over years and will eventually want a bounded window.

## Consequences

- **Good:** one noun replaces two, and the account coupling that broke the Korea
  goal is gone by construction — `fund` has no account column to misuse.
- **Good:** nothing to migrate. Zero `Budget` rows have ever existed, one `Goal`
  with zero contributions, and the owner has explicitly chosen not to migrate it
  (acs.md decision 9): the moment they sit down to register the money is the
  moment they create the fund.
- **Good:** consolidation C14 closes as a side effect, and consolidation task 14
  (goals ATDD coverage, cancelled 2026-08-02) can be deleted.
- **Bad / cost:** this is a **destructive migration on real data** — three tables
  and one column dropped, plus the three unconfirmed goal proposals AC-27
  removes. It runs behind a fresh `just backup` and explicit human
  authorisation (charter §7, ADR-0030), with the steps in
  `features/003-sinking-funds/runbook.md`.
- **Bad / cost:** ADR-0006 is superseded in full, and it was the ADR that
  established REST↔MCP parity for the planning surface. The parity requirement
  itself is unaffected (charter §2, ADR-0009) and is re-satisfied by the fund
  tools; only the tools it named go away.
- **Bad / cost:** the fold's growth over years, above.

### A declared boundary: a fund is deleted, not archived

Charter §3 makes soft-delete + restore the uniform lifecycle for masters
(ADR-0005). A fund is **hard-deleted** (`delete_fund`, AC-21's *"the owner
deletes the fund first"*).

This is a boundary, not an oversight. A fund is a rule attached to a category,
not a master record: it has no history of its own, its balance is derived, and
an archived fund would still have to answer "what do you ask this month?" with
something. Accounts, categories, tags and recurring items keep soft-delete
unchanged. Written here so nobody "fixes" it later without knowing it was
chosen.

## Confirmation

- `features/003-sinking-funds/spec.md`, 92 scenarios, run by
  `./run-acceptance-tests.sh`. The fold is pinned by AC-11 (a fund emptied by
  the charge it saved for holds `0.00`, not this month's ask), AC-13 (an
  overspent fund falls to zero, not below) and AC-19 (the opening figure counts
  toward what the fund still needs, and an account beside it changes nothing).
- The absence of an account is asserted directly: `the fund on "X" names no
  account` (AC-26).
- The deletions are asserted from the records after the migration: `the records
  hold no goal`, and the outstanding queue no longer shows the proposals
  (AC-26, AC-27).
- Product-side: `docs/decisions/product-decisions.md` § ADR-003 (safe-to-spend
  as unassigned money) is replaced, § ADR-006 (goals) removed, § ADR-002
  (envelopes + rollover) amended. § ADR-004 is **not** superseded — see
  ADR-0044, which builds its never-implemented reconciliation clause.
