# 0041. Category presence is a type-discriminated constraint, not a blanket NOT NULL

- **Status:** accepted
- **Date:** 2026-08-03
- **Deciders:** Angelo
- **Supersedes:** — (this ADR supersedes no technical decision; the product
  clause it rests on, ADR-024's "optional category when recording", is
  superseded by `docs/decisions/product-decisions.md` § ADR-036)
- **Superseded by:** —

## Context and problem statement

Feature 008 makes a category mandatory on every expense and income. The
guarantee has to survive the application being wrong or bypassed, so it belongs
in the schema and not only in `services/`. But `transaction` holds three kinds
of row under one type column, and the third one inverts the rule: all 39
transfers in production are correctly uncategorised and must stay that way,
because categorising a transfer counts the same money twice — once moving into
the emergency fund, again when it is finally spent out of it.

A naive `ALTER TABLE transaction ALTER COLUMN category_id SET NOT NULL` would
close the gap and break every transfer in the same statement. This ADR records
how the constraint is shaped, where it is declared, and what it deliberately
does *not* enforce.

Prompted by `features/008-mandatory-categories/` (acs.md AC-17, AC-18;
spec.md AC-17 four scenarios). Measured gap that motivated the feature: 131
uncategorised movements, $2.072.854 COP + US$7.486,68 in expenses and
$7.003.101 COP + US$10.495,55 in income invisible to every report.

## Decision drivers

- The 39 existing transfers must survive the migration untouched.
- Acceptance tests migrate an in-memory **SQLite** database to head
  (`db.py::init_db` → `alembic upgrade head`), while production is **Postgres
  18**. One constraint definition has to work on both.
- SQLite cannot `ALTER TABLE ADD CONSTRAINT`; adding a CHECK to an existing
  table requires a table rebuild.
- The model and the schema must not be able to drift — `domain/models.py` is
  what every developer reads, Alembic is what the database actually has.
- The migration must not land on dirty data: a constraint violation raised by
  the driver mid-upgrade is an unreadable failure on a half-applied schema.

## Considered options

1. **Blanket `NOT NULL` on `transaction.category_id`.**
2. **Type-discriminated `CHECK`, declared on the model and installed by an
   Alembic revision.**
3. **No database constraint — enforce only in `services/`.**
4. **A database trigger that also validates the category's direction.**

## Decision outcome

Chosen option: **2 — a type-discriminated CHECK**, because it is the only
option that states the actual rule (presence depends on the kind of movement)
in the one place that cannot be bypassed, on both engines, without a trigger.

```sql
CHECK (
  (type IN ('expense','income') AND category_id IS NOT NULL)
  OR (type = 'transfer' AND category_id IS NULL)
)
```

Three things follow from it:

**Declared twice, on purpose.** The constraint lives in
`Transaction.__table_args__` *and* in Alembic revision `0010`. Alembic is the
source of truth for the schema (`db.py`), but a constraint only Alembic knows
about is invisible to whoever reads the model. Both must be present, and a
mismatch is caught by the acceptance suite, which builds its schema through
migrations and then exercises it through the models.

**Installed via `op.batch_alter_table`.** On Postgres this emits a plain
`ALTER TABLE ... ADD CONSTRAINT`; on SQLite it rebuilds the table. Without it,
revision `0010` would raise on every acceptance scenario.

**Guarded before it is applied.** Revision `0010` first counts uncategorised
expenses and incomes and raises with the count and the kind ("1 expense is
still uncategorised") before touching the schema. The upgrade either lands on
clean data or does not land — and the refusal is a sentence, not an integrity
error.

`downgrade()` drops the constraint. Unlike revision `0009`, nothing is lost by
reversing this one.

### The boundary: presence, not direction

The constraint pins **presence**. It does not check that an income's category
is an income category — that stays a service-layer refusal (ADR-0042).
Enforcing direction in the database would need either a trigger or a
denormalised copy of `category.is_income` on every transaction row, and the
acceptance criteria only ask the records to refuse an uncategorised movement
and a categorised transfer.

`recurring_item.category_id` becomes a plain `NOT NULL` in the same revision.
A recurring item is only ever an expense or an income — `create_recurring`
already refuses `transfer` — so it needs no discrimination. This is what makes
AC-6's guarantee structural rather than well-behaved: `occurrences.
_create_occurrence_tx` copies `item.category_id` onto every charge it creates,
and a NOT NULL source cannot produce a NULL copy.

### Pros and cons of the options

**1 — Blanket NOT NULL**
- Good, because it is one line and every engine supports it directly.
- Bad, because it makes all 39 existing transfers unstorable, and would force
  either inventing a category for them or abandoning the constraint entirely.

**2 — Type-discriminated CHECK (chosen)**
- Good, because it states the real rule, holds against raw SQL, and covers the
  transfer case in the same expression.
- Bad, because it is duplicated (model + revision), and the SQLite rebuild
  costs a table copy on every test database build.

**3 — Services only**
- Good, because zero migration risk and no engine differences.
- Bad, because the guarantee then depends on the code being correct, which is
  exactly what AC-17 refuses to assume. The 131-row gap was produced by code
  that was working as written.

**4 — Trigger validating direction too**
- Good, because it would close AC-15 in the database as well.
- Bad, because triggers differ between SQLite and Postgres, are invisible to
  the model, and no acceptance criterion asks for it.

## Consequences

- Good: an uncategorised expense or income cannot exist, whoever writes it —
  the app, the API, the agent, a hand-written `INSERT`, or a future importer.
- Good: transfers keep their meaning, and the constraint documents why.
- Good: the pre-flight guard turns a migration failure into a readable
  sentence, so a dirty upgrade is diagnosable without reading Alembic output.
- Bad / cost: every write path must resolve a category before insert —
  ~139 existing backend test call sites record money without one and need a
  category threaded through (see ADR-0042 for the single resolver they call).
- Bad / cost: the SQLite table rebuild runs once per test database. Budgeted in
  `features/008-mandatory-categories/plan.md` as "no regression > 20% on the
  full acceptance suite".
- Bad / cost: the constraint cannot be applied to production until the data is
  clean. It already is (backfilled 2026-08-02, 131 rows resolved), but the
  guard stays because a future restore from an old dump would need it.

## Confirmation

`features/008-mandatory-categories/spec.md` AC-17 (four scenarios) forces raw
`INSERT`s past the services layer and asserts the records refuse an
uncategorised expense, an uncategorised income and a categorised transfer,
while holding an uncategorised transfer. AC-18 (three scenarios) asserts the
upgrade refuses over dirty data and names the count and kind. AC-19 asserts
every pre-upgrade movement keeps the category it had.

Those tests build their schema by running Alembic to head, so a constraint
missing from the revision fails them; the rest of the suite exercises the same
database through the models, so a constraint missing from
`Transaction.__table_args__` shows up as a model/schema divergence.
