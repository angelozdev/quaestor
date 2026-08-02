# 0035. Passed due dates are offered for per-date acceptance, never backfilled silently

- **Status:** accepted
- **Date:** 2026-08-02
- **Deciders:** Angelo
- **Supersedes:** — (supersedes the silent-backfill half of `docs/decisions/product-decisions.md` § ADR-020; see Consequences)
- **Superseded by:** —

## Context and problem statement

`materialize_due` creates every occurrence with `due_date <= until_date` that
does not exist yet. It makes no distinction between a date that fell due while
the machine was off and a date that was already in the past the moment the
obligation was declared. Declaring Netflix at 25.900 on 2 August with a start
date of 5 January therefore takes 181.300 out of the balance on the next daily
run, unannounced, for seven months the user never agreed to.

Feature 007's AC-12 (approved 2026-08-02) requires those dates to be presented
one by one for acceptance, with nothing created until the user answers, and a
declined date never offered or created again.

## Decision drivers

- **The engine is the only surface that moves a balance with no user action.**
  Anything it does unasked has to have been agreed to at declaration time.
- **Catch-up after downtime must survive.** AC-9 keeps unattended
  materialization for an obligation that already existed — that is the whole
  point of a daily job that self-heals (ADR-0013).
- **The decision must outlive the session.** The next daily run cannot backfill
  a date whose answer is still outstanding, so "awaiting an answer" has to be
  recorded, not held in memory.
- **Industry precedent, checked rather than assumed.** Firefly III refuses a
  past first date outright and creates nothing; Actual Budget keeps schedules
  forward-only and warns that pulling in older movements throws the budget out;
  YNAB treats scheduling as future-only and puts history in via import. GnuCash
  is the outlier that does backfill — through its *Since Last Run* assistant,
  which lists every missed date and lets the user mark each Create / Postpone /
  Ignore.
- **The occurrence table already carries the right key.**
  `(recurring_id, due_date)` is unique, and materialization already skips any
  date that has an occurrence.

## Considered options

1. **A fourth occurrence status, `offered`.** Offering writes the occurrence in
   `offered`; accepting materializes it; declining moves it to `skipped`, which
   already blocks recreation.
2. **A separate "pending decision" table.** A new table keyed by
   `(recurring_id, due_date)` holding the outstanding offers, consulted by the
   daily run.
3. **Refuse a start date in the past outright** (the Firefly III line). No
   offer, no backfill; the user records history by hand.

## Decision outcome

Chosen option: **Option 1 — a fourth occurrence status, `offered`**, because it
gets the whole behaviour out of state the schema already has. The unique
`(recurring_id, due_date)` key is exactly the key an offer needs; the rule "a
date with an occurrence is never materialized again" is exactly the rule that
makes a pending offer safe from the daily run; and `skipped` already means
"this date is closed and no run brings it back", which is precisely what a
declined date is. The cost is two enum values and no new columns or tables.

Which dates get offered is decided at declaration: `create_recurring` takes a
`declared_on` (defaulting to today, not persisted). Dates before it are offered;
dates from it onward are the engine's to charge unattended. An obligation that
already existed is declared with `declared_on = start_date`, so nothing is
pending and AC-9's catch-up is untouched. Moving a start date backwards offers
the dates that edit opens and that already fell due.

### Pros and cons of the options

**Option 1 — a fourth occurrence status**
- Good, because it reuses the unique key, the idempotency rule and the terminal
  `skipped` state that already exist.
- Good, because no new table means no second source of truth about a due date.
- Good, because the offer survives a restart — it is a row, not session state.
- Bad, because `OccurrenceStatus` grows a value that only one flow writes, and
  every reader of occurrence status has to know it is not a charge.

**Option 2 — a separate pending-decision table**
- Good, because the offer is unmistakably not an occurrence.
- Bad, because it duplicates `(recurring_id, due_date)` across two tables and
  makes the daily run consult both to decide whether a date is free.
- Bad, because a declined date then has to be written into the occurrence table
  anyway, so the second table only ever holds transient rows.

**Option 3 — refuse past start dates**
- Good, because it is the simplest possible rule and the majority precedent.
- Bad, because it removes a capability the user asked for: declaring an
  obligation you have been paying for months and pulling that history in.
- Bad, because the workaround is entering months of movements by hand, which is
  the friction the whole feature exists to remove.

## Consequences

- Good: the engine never moves a balance for a date the user did not agree to,
  while the unattended catch-up that ADR-0013 relies on stays intact.
- Good: a declined date is permanently closed with the mechanism that already
  closes skipped dates — no new rule to keep in step.
- Good: the same three operations (offer, accept, decline) reach REST and MCP
  without a new resource, so AC-26's conversational path answers rather than
  defaulting either way.
- Bad / cost: `docs/decisions/product-decisions.md` § ADR-020 states due-driven
  materialization with no interactive step. Its due-driven core stands; the
  clause that every not-yet-materialized past date is created on the next run
  is superseded here. That file gets the matching entry — it has had no entry
  since 2026-07-03, and this decision does not add to that drift.
- Bad / cost: a migration is required for the `offered` enum value. Because
  these are native Postgres enums, `ALTER TYPE … ADD VALUE` has to run inside
  `op.get_context().autocommit_block()` — outside Alembic's transaction. A
  migration that gets this wrong passes the acceptance suite (SQLite stores
  enums as text) and fails only against production.
- Bad / cost: any code that counts "charges" must count `posted` and `planned`
  and exclude `offered`. The acceptance handlers already draw that line.

## Confirmation

Feature 007's acceptance spec, AC-12 (6 scenarios) and AC-26 (the "offered
rather than defaulting" scenario), plus AC-9's three scenarios as the guard that
unattended catch-up did not regress. Unit tests in
`backend/tests/services/test_occurrences.py` cover offer / accept-some /
accept-all / decline-all and the re-offer refusal. The invariant that only
`services/occurrences.py` writes a `RecurringOccurrence` is checked by
`arch-check` at CP8.
