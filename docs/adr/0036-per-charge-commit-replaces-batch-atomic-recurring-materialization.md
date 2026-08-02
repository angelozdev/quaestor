# 0036. Per-charge commit replaces batch-atomic recurring materialization

- **Status:** accepted
- **Date:** 2026-08-02
- **Deciders:** Angelo
- **Supersedes:** — (supersedes the batch-rollback half of `docs/decisions/product-decisions.md` § ADR-020; see Consequences)
- **Superseded by:** —

## Context and problem statement

`materialize_due` wraps the whole daily batch in one transaction and rolls all
of it back on any error. One obligation pointing at an account the user archived
is enough to cost every other obligation its day — silently, and again every day
until someone notices. The engine runs unattended in the FastAPI lifespan, so
"someone notices" can be weeks.

Feature 007's AC-24 and AC-22 (approved 2026-08-02) require that the healthy
obligations still land, that the failure be reported naming the obligation, and
that each charge stay all-or-nothing on its own.

## Decision drivers

- **A batch is not a unit of meaning.** Netflix and Claro have nothing to do
  with Spotify; no invariant makes them succeed or fail together.
- **A charge IS a unit of meaning.** The movement, the balance change and the
  occurrence row have to land together or not at all, or the account and the
  obligation start contradicting each other.
- **Failure must be visible.** Today the run raises and `run_daily` reports
  nothing about which item broke.
- **The test surface is SQLite, production is Postgres.** Any isolation
  mechanism that behaves differently across the two is worse than useless: it
  would pass the acceptance suite and be false in production, or the reverse.
- **Scale is tens of charges a day, not thousands.** Commit count is not a real
  constraint here.

## Considered options

1. **A SAVEPOINT per item** via `Session.begin_nested()`, keeping one outer
   transaction for the run.
2. **One commit per charge.** Each `(item, due_date)` is its own transaction;
   failures are collected into a report and the run continues.
3. **Two passes** — validate every item first, then materialize only the ones
   that passed, still batch-atomic.

## Decision outcome

Chosen option: **Option 2 — one commit per charge**, because it is the only
option whose behaviour is identical on both database engines the project runs.

Option 1 is the textbook answer and it is unusable here. SQLAlchemy's own SQLite
dialect documentation states that under the `pysqlite` driver in its default
mode, "as the SAVEPOINT statement does not imply a BEGIN, a new SAVEPOINT
emitted before a BEGIN will function on its own but fails to participate in the
enclosing transaction, meaning a ROLLBACK of the transaction will not rollback
elements that were part of a released savepoint." The acceptance suite runs
host-side on in-memory SQLite with exactly that driver (`db._sqlite_engine`,
default connect args), so per-item isolation would be real in production and
fake in the tests meant to prove it. The documented workaround — setting
`isolation_level = None` on connect and emitting `BEGIN` from a `begin` event —
changes the transactional behaviour of the entire application to solve one
module's problem.

`materialize_due` therefore returns a `MaterializationReport(created, failures)`
instead of a list, and `run_daily` propagates the failures into its report dict.
Each `RunFailure` names the obligation and the reason.

### Pros and cons of the options

**Option 1 — SAVEPOINT per item**
- Good, because the run stays one transaction and the commit count stays at one.
- Good, because it is the pattern SQLAlchemy documents for exactly this shape.
- Bad, because it is non-functional under the default pysqlite driver, which is
  the driver every acceptance and unit test uses.
- Bad, because making it functional means changing global transaction handling
  for the whole application.

**Option 2 — one commit per charge**
- Good, because Postgres and SQLite behave identically; the tests prove what
  they claim.
- Good, because the atomic unit matches the unit of meaning AC-24 states:
  "each charge lands whole — its record and its balance movement together, or
  neither".
- Good, because a failed charge leaves no occurrence, so the date is still free
  and the next run picks it up once the cause is fixed.
- Bad, because a run is no longer a single transaction: a crash mid-run leaves
  some charges committed. That is the intended behaviour, not a regression —
  those charges are correct and the rest are retried tomorrow.
- Bad, because commit count grows from 1 to one per charge.

**Option 3 — validate then materialize**
- Good, because it keeps one transaction and catches the common failure.
- Bad, because it only catches failures a validation pass can predict; anything
  failing at write time still costs the whole batch.
- Bad, because it duplicates the write path's rules in a second place that can
  drift.

## Consequences

- Good: one unchargeable obligation costs itself and nothing else, and says so
  by name in the daily report.
- Good: the retry story is free — a failure writes no occurrence, so the date
  remains due and the next run tries again.
- Good: AC-22 falls out of the same mechanism; an archived account is just a
  failure reason.
- Bad / cost: `docs/decisions/product-decisions.md` § ADR-020 describes the
  daily materialization as a single batch. Its due-driven core and its
  `(recurring_id, due_date)` idempotency stand; the batch-rollback consequence
  is superseded here.
- Bad / cost: a catch-up over a long outage now issues one commit per date. The
  budget in `plan.md` sets 5 s for 365 dates; if it is ever approached, the
  fallback is one commit per obligation, which still satisfies AC-24's
  per-obligation isolation.
- Bad / cost: `materialize_due`'s return type changes, so `jobs/daily.py` and
  every other caller move with it.

## Confirmation

Feature 007's acceptance spec, AC-24 (3 scenarios: the healthy ones land, the
failure is reported by name, the broken one is picked up once fixed) and AC-22
(2 scenarios). Unit tests in `backend/tests/services/test_occurrences.py` place
a broken obligation between two healthy ones and assert both the balances and
the report contents. `backend/tests/jobs/test_daily.py` asserts the failures
reach the daily report dict. Mutation testing is opted in for
`services/occurrences.py` at CP8 (the manifest default is `opt_in`).
