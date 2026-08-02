---
title: "Recurring engine with due-driven materialization"
slug: recurring-engine
number: 007
status: done
autonomy_level: medium
branch: recurring-engine
area: planning
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: recurring
relevant_adrs: [0005, 0013, 0034]
created: 2026-08-02
intake: onboarding
---

# Recurring engine with due-driven materialization

## Outcome

The user declares an obligation or income that repeats on a fixed cadence once,
and the app produces every occurrence on its own from then on: in `auto` mode
the transaction is posted and the account balance moves without any user
action; in `manual` mode a planned transaction lands in the to-pay queue for
confirmation. Running the engine twice on one day changes nothing, a machine
that was off for days catches up on the next run, and the user can skip a
single date, edit the item without rewriting history, or deactivate it while
keeping everything already materialized.

## Scope

- Create a recurring item: name, payee, expense or income (never transfer),
  `auto`/`manual` mode, positive amount in a currency matching the account,
  optional category, account, cadence (every N days/weeks/months/years), start
  date and optional end date.
- Cadence arithmetic: due dates are `start_date + k x interval`, inclusive of
  `end_date`, with end-of-month clamping for month/year units (a 31st start
  yields the 28th/29th in February).
- Due-driven materialization: `materialize_due(until_date)` creates every
  not-yet-materialized occurrence with `due_date <= until_date`, idempotent by
  `(recurring_id, due_date)`, self-healing after missed days, whole batch
  rolled back on any error. Runs daily from the scheduler with `today`.
- Mode split at materialization: `auto` posts the transaction and applies
  `delta_balance` to the account; `manual` writes a `planned` transaction and a
  `planned` occurrence, moving no balance. Incomes are always `auto` (AC-6,
  target — a manual income produces a planned income that feature 006 keeps out
  of the queue, so nobody can ever resolve it).
- Due dates already passed at declaration or after a `start_date` edit are
  offered for per-date acceptance instead of being backfilled silently (AC-12,
  target); a declined date is permanent and never re-offered.
- An item whose last due date has passed switches itself off (AC-13, target);
  resuming a paused item does not recover the paused stretch (AC-17, target).
- Skipping refuses a date already charged and a date the item never falls due on
  (AC-20/AC-21, target); an account archived after declaration stops the charges
  and is reported (AC-22, target).
- Deleting an engine-created transaction closes that due date as `skipped`
  instead of leaving the occurrence pointing at a deleted row (AC-28, target) —
  the correction path AC-20 sends the user to.
- The occurrence side of an undone skip: `restore_payment` returns the
  occurrence to `planned` (AC-27, accept — shipped and correct, previously
  unasserted).
- A failure on one item no longer costs the whole run: the rest still land and
  the failure is reported (AC-24, target). Each charge stays all-or-nothing.
- A charge made by the engine is identifiable as recurring in the movements list
  and names its obligation (AC-25, target).
- Edit: `type` and `currency` are immutable; every other field changes only
  future un-materialized occurrences — already-materialized ones keep the
  amount and date they were created with.
- Soft lifecycle (ADR-0005): deactivate stops future materialization while
  existing occurrences survive; restore is an idempotent re-activation.
- Skip a single `(item, due_date)`: marks the occurrence `skipped`, downgrades
  a linked `planned` transaction to `skipped` so it leaves to-pay, creates the
  occurrence row when none exists yet, and blocks re-materialization of that
  date.
- Listing and filtering by `active`, with an inactive toggle on the page.
- Surfaces: `Recurrentes` page (create/edit dialogs, deactivate, restore, skip
  dialog), REST router `/api/recurring`, MCP tools `create_recurring`,
  `list_recurring`, `update_recurring`, `skip_recurring`, `archive_recurring`,
  `restore_recurring`.

Out of scope, asserted only as seams (this engine feeds them; their behaviour
belongs to their own features):

- Confirming or skipping a planned payment from the queue — feature
  `planned-payments-to-pay` (006, done). This feature owns only the occurrence
  side of the skip sync.
- The FX fetch and month-close steps that share the daily job — features
  `multi-currency-fx` / `daily-scheduler-job` (task 9) and
  `month-close-rollover` (task 4).
- Budget envelope consumption by materialized transactions — feature
  `budgets-envelopes` (paused pending the sinking-funds redesign).
- A `Por cobrar` view for expected incoming money — surfaced at AC discovery and
  parked for its own `discuss`. AC-6 removes the urgency by forcing incomes to
  `auto`, so no expected income is left unresolvable.

## Method

Clean-room first, diff second (user decision at intake):

1. Design the acceptance criteria as if the feature did not exist — from
   product behaviour, not from `services/recurring.py`. No reading the
   implementation while deciding what the engine *should* do.
2. Then contrast the clean-room criteria against the shipped behaviour.
3. Every divergence is an explicit decision: fix the code (AC marked
   `target`), or accept the shipped behaviour and record why. No divergence is
   left implicit, and no AC is reverse-engineered from the code by default.

Known intake candidates for divergence, to be judged in step 2, not assumed:
`update_recurring` accepts a `start_date` change that can retro-open dates
already passed; `end_date` never deactivates the item; an `auto` item posts and
moves balance with no user-visible trace of it having happened; skipping a date
that was already materialized as `posted` leaves the balance moved.

## Source links

- `.engineer/consolidation.md` — consolidation task 3 (inventory row 5,
  `recurring-engine`).
- Design specs (pre-DAE): `docs/superpowers/specs/2026-06-16-P3-temporal-engine-design.md`,
  `docs/superpowers/plans/2026-06-19-P3-temporal-engine.md`.
- `docs/adr/0005-soft-delete-and-restore-as-the-uniform-lifecycle-for-goals-recurring-and-masters.md`,
  `docs/adr/0013-daily-scheduler-as-a-thin-sidecar.md`,
  `docs/adr/0034-skipping-a-planned-payment-is-reversible.md`.

## Code co-locations

- Backend: `backend/src/quaestor/services/recurring.py`,
  `backend/src/quaestor/domain/rules.py` (`due_dates`, `_add_interval`,
  end-of-month clamp), `backend/src/quaestor/domain/models.py`
  (`RecurringItem`, `RecurringOccurrence`, `RecurringMode`, `IntervalUnit`,
  `OccurrenceStatus`), `backend/src/quaestor/api/routers/recurring.py`,
  `backend/src/quaestor/jobs/daily.py`,
  `backend/src/quaestor/mcp/registry.py`, `backend/src/quaestor/mcp/format.py`.
- Frontend: `frontend/app/(app)/recurring/page.tsx`,
  `frontend/app/(app)/recurring/recurring.schema.ts`,
  `frontend/lib/api/recurring.ts`.

## Notes

Shipped before DAE adoption; formalized 2026-08-02 as consolidation task 3.
Follows `006-planned-payments-to-pay`, which owns the confirm/skip queue this
engine feeds; the two touch through `RecurringOccurrence.transaction_id` and
the `planned -> skipped` sync.

The engine is the only surface that moves an account balance with no user
action (`auto` mode), which raises the cost of any undetected divergence.

`ADR-020` cited in the module docstrings is pre-DAE numbering for the temporal
engine design, not `docs/adr/0020-security-hardening-...`; do not follow that
reference by number.

ACs discovered 2026-08-02 under the Method above: 28 criteria drafted from
product behaviour, then diffed against the engine. Ten divergences, all resolved
as fix — AC-6, 12, 13, 17, 20, 21, 22, 24, 25, 28. Everything else accepted as
shipped. The four intake candidates all landed as fixes, and the diff found six
more. AC-21 and AC-22 came from the diff rather than from a question and were
ratified separately; AC-27 and AC-28 came from the `consistency-check` edit pass
the same day. The closed-month worry was checked rather
than assumed: `close_month` freezes nothing, so backfilled charges keep their
real dates. AC-12's per-date acceptance follows GnuCash's *Since Last Run*
pattern; Firefly III, Actual Budget and YNAB all refuse backfill outright.

