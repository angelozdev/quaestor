# P3 Temporal Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Quaestor its temporal dimension — recurring obligations, one-off planned payments, the "to-pay" confirmation queue, and an atomic/idempotent monthly close — built on P0's `Transaction.status` without touching balance until confirmation.

**Architecture:** Two clocks (ADR-020/022). A daily **due-driven materialization** (`materialize_due`) turns each recurring item's concrete `due_date`s into transactions (auto→`posted`, manual→`planned`). A monthly **close** (`close_month`) runs a registered list of rollover hooks in one transaction. Both are services driven by P7's scheduler, never user tools. `confirm_payment` is the only `planned`→`posted` transition and fires post-confirm hooks so P4 can graft goal-contribution recording without P3 knowing about goals.

**Tech Stack:** Python ≥3.12, SQLModel/SQLAlchemy over SQLite, FastAPI (REST), FastMCP (MCP tools), pytest with in-memory SQLite. Package root: `backend/`.

## Global Constraints

These apply to **every** task. Exact values copied from the spec, P0 code, and the product decisions.

- **Money:** integer cents in the original currency, always positive. `to_base` is COP cents, **frozen** at registration via `domain.money.to_base_cents(amount_cents, fx_rate)`. Sign comes from the type via `domain.rules.delta_balance(tx_type, amount)` (income `+`, expense `-`), never from the amount.
- **Balance:** only `posted` transactions affect `Account.balance`. `planned` lives **only** in `to_pay`. `skipped` affects neither.
- **State machine:** `confirm_payment` is the **only** `planned`→`posted` transition. `skip_payment`/`skip_recurring` move `planned`→`skipped` (a terminal cancel, not "forward"). Nothing else moves status.
- **Idempotency:** recurring occurrences are unique by `(recurring_id, due_date)`. A repeated `materialize_due` or `close_month` must not duplicate rows. A missed day self-heals on the next run.
- **Atomicity:** `close_month` and `confirm_payment` run their mutations **and** their hooks in a single transaction; any failure rolls back the whole operation. Reuse `db.atomic(session)` or the explicit try/commit/except-rollback pattern from `services.transactions.transfer`.
- **Frequency (ADR-020):** due dates are `start_date + k × (interval_count × interval_unit)` for `interval_unit ∈ {day, week, month, year}`, `interval_count ≥ 1`, with **end-of-month clamping** for `month`/`year` (a day-31 anchor → 30/28), always anchored to `start_date.day` (never chained off a previously-clamped date).
- **Reuse, do not redefine:** consume P0's money/FX/sign rules. Resolve FX with `services.transactions._resolve_fx(session, currency, date, fx_rate)` (returns a `Decimal`; raises `MissingRate` for a non-COP date with no rate). Never duplicate money logic.
- **Service convention:** every service function takes `session` as its **first** parameter and commits internally (matching all existing P0/P1/P2 services). The spec lists params order-agnostically; follow the codebase convention.
- **Schema:** there is no Alembic. The schema is created by `SQLModel.metadata.create_all` inside `db.init_db`. New tables are created automatically; the new `Transaction.recurring_id` column lands in any freshly-created DB. Tests use a fresh in-memory DB per test (`tests/conftest.py`). For the dev `backend/quaestor.db`, delete and recreate it (clean start, ADR-009) — do **not** add migration tooling.
- **Language:** all code, identifiers, comments, and strings in English (ADR-0001).
- **Decisions:** respect the accepted product decisions in `docs/decisions/product-decisions.md` (ADR-006/007/012/015/017/020/022). Do not introduce new architecturally-significant technical decisions without an ADR in `docs/adr/` (CLAUDE.md). This plan introduces none beyond what those decisions already mandate.

---

## File Structure

**Modify:**
- `backend/src/quaestor/domain/models.py` — add `IntervalUnit`, `RecurringMode`, `OccurrenceStatus` enums; add `skipped` to `TxStatus`; add `RecurringItem` and `RecurringOccurrence` tables; add `Transaction.recurring_id`.
- `backend/src/quaestor/domain/rules.py` — add pure date generator `due_dates` + interval helpers.
- `backend/src/quaestor/domain/errors.py` — add `IllegalTransition`.
- `backend/src/quaestor/api/errors.py` — map `IllegalTransition` → HTTP 409.
- `backend/src/quaestor/mcp/format.py` — render temporal results; add `IllegalTransition` text.
- `backend/src/quaestor/mcp/registry.py` — add `register_temporal_tools` import/call wiring (the function lives in a new tools module).
- `backend/src/quaestor/mcp/server.py` — call `register_temporal_tools(mcp)` in `build_mcp`.
- `backend/src/quaestor/api/__init__.py` — include the new routers.
- `backend/src/quaestor/api/schemas.py` — add request/response models for recurring + planned + rollover.

**Create:**
- `backend/src/quaestor/services/recurring.py` — `create_recurring`, `list_recurring`, `materialize_due`, `skip_recurring`.
- `backend/src/quaestor/services/planned.py` — `plan_payment`, `confirm_payment`, `skip_payment`, `to_pay`, the post-confirm hook registry.
- `backend/src/quaestor/services/rollover.py` — `close_month`, `ensure_month_closed`, the rollover hook registry.
- `backend/src/quaestor/mcp/tools/temporal.py` — MCP input models + impls for the 7 user tools.
- `backend/src/quaestor/api/routers/recurring.py`, `planned.py`, `rollover.py` — thin REST adapters.

**Test:**
- `backend/tests/domain/test_recurrence.py`, `backend/tests/domain/test_recurring_models.py`
- `backend/tests/services/test_recurring.py`, `test_planned.py`, `test_rollover.py`
- `backend/tests/mcp/test_temporal.py`
- `backend/tests/api/test_recurring.py`, `test_planned.py`

**Conventions for every command in this plan:** run from `backend/`. Test runner is `uv run pytest`.

---

### Task 1: Domain — interval enum + `due_dates` generator

Pure functions, no DB. The whole frequency engine (ADR-020) lives here so it can be tested in isolation. `due_dates` takes primitives (not a `RecurringItem`) to keep `domain/rules.py` free of table dependencies; services pass the item's fields.

**Files:**
- Modify: `backend/src/quaestor/domain/models.py` (add `IntervalUnit` enum only)
- Modify: `backend/src/quaestor/domain/rules.py`
- Test: `backend/tests/domain/test_recurrence.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `IntervalUnit(str, Enum)` with members `day`, `week`, `month`, `year` (in `models.py`).
  - `due_dates(start_date: date, end_date: date | None, interval_unit: IntervalUnit, interval_count: int, since: date, until: date) -> list[date]` (in `rules.py`).
  - `_add_interval(anchor: date, unit: IntervalUnit, count: int, k: int) -> date` and `_add_months(anchor: date, months: int) -> date` helpers (in `rules.py`).

- [ ] **Step 1: Add the `IntervalUnit` enum to models.py**

In `backend/src/quaestor/domain/models.py`, after the `class TxType` block, add:

```python
class IntervalUnit(str, Enum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"
```

- [ ] **Step 2: Write the failing tests for `due_dates`**

Create `backend/tests/domain/test_recurrence.py`:

```python
from datetime import date

from quaestor.domain.models import IntervalUnit
from quaestor.domain.rules import due_dates


def test_monthly_due_dates_in_window():
    got = due_dates(
        date(2026, 1, 15), None, IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 4, 30),
    )
    assert got == [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)]


def test_biweekly_generates_several_in_a_month():
    got = due_dates(
        date(2026, 1, 1), None, IntervalUnit.week, 2,
        since=date(2026, 1, 1), until=date(2026, 2, 28),
    )
    assert got == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29), date(2026, 2, 12), date(2026, 2, 26)]


def test_every_three_months_quarterly():
    got = due_dates(
        date(2026, 1, 10), None, IntervalUnit.month, 3,
        since=date(2026, 1, 1), until=date(2026, 12, 31),
    )
    assert got == [date(2026, 1, 10), date(2026, 4, 10), date(2026, 7, 10), date(2026, 10, 10)]


def test_annual():
    got = due_dates(
        date(2024, 3, 5), None, IntervalUnit.year, 1,
        since=date(2024, 1, 1), until=date(2026, 12, 31),
    )
    assert got == [date(2024, 3, 5), date(2025, 3, 5), date(2026, 3, 5)]


def test_end_of_month_clamping_anchors_to_start_day():
    # day-31 anchor: Feb clamps to 28, but March returns to 31 (not chained off Feb)
    got = due_dates(
        date(2026, 1, 31), None, IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 4, 30),
    )
    assert got == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_leap_year_february_clamp():
    got = due_dates(
        date(2024, 1, 29), None, IntervalUnit.year, 1,
        since=date(2024, 1, 1), until=date(2025, 12, 31),
    )
    assert got == [date(2024, 1, 29), date(2025, 1, 29)]  # both valid; check Feb separately
    feb = due_dates(
        date(2024, 2, 29), None, IntervalUnit.year, 1,
        since=date(2024, 1, 1), until=date(2025, 12, 31),
    )
    assert feb == [date(2024, 2, 29), date(2025, 2, 28)]  # 2025 is not a leap year


def test_end_date_truncates_window():
    got = due_dates(
        date(2026, 1, 1), date(2026, 3, 1), IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 12, 31),
    )
    assert got == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_since_skips_earlier_occurrences():
    got = due_dates(
        date(2026, 1, 1), None, IntervalUnit.month, 1,
        since=date(2026, 3, 1), until=date(2026, 5, 31),
    )
    assert got == [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)]


def test_empty_when_start_after_until():
    assert due_dates(
        date(2027, 1, 1), None, IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 12, 31),
    ) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/domain/test_recurrence.py -v`
Expected: FAIL with `ImportError: cannot import name 'due_dates'`.

- [ ] **Step 4: Implement `due_dates` and helpers in rules.py**

In `backend/src/quaestor/domain/rules.py`, update the imports and append the generator. The new top of the file:

```python
"""Balance sign rules and the recurrence date engine (ADR-020)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from .models import IntervalUnit, TxType
```

Then append at the end of the file:

```python
def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(anchor: date, months: int) -> date:
    """anchor shifted by `months`, clamping the day to the target month's last day.

    Anchored to anchor.day every time (never chained), so Jan 31 -> Feb 28 -> Mar 31.
    """
    total = (anchor.year * 12 + (anchor.month - 1)) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(anchor.day, _last_day_of_month(year, month))
    return date(year, month, day)


def _add_interval(anchor: date, unit: IntervalUnit, count: int, k: int) -> date:
    """The k-th occurrence after `anchor` for interval (count x unit)."""
    n = count * k
    if unit == IntervalUnit.day:
        return anchor + timedelta(days=n)
    if unit == IntervalUnit.week:
        return anchor + timedelta(weeks=n)
    if unit == IntervalUnit.month:
        return _add_months(anchor, n)
    if unit == IntervalUnit.year:
        return _add_months(anchor, n * 12)
    raise ValueError(f"invalid interval_unit: {unit}")


def due_dates(
    start_date: date,
    end_date: date | None,
    interval_unit: IntervalUnit,
    interval_count: int,
    since: date,
    until: date,
) -> list[date]:
    """Due dates in [since, until] for interval (interval_count x interval_unit).

    Each due date is start_date + k x interval, with end-of-month clamping for
    month/year units. Respects end_date (inclusive). Returns dates ascending.
    """
    if interval_count < 1:
        raise ValueError("interval_count must be >= 1")
    results: list[date] = []
    k = 0
    while True:
        d = _add_interval(start_date, interval_unit, interval_count, k)
        if d > until:
            break
        if end_date is not None and d > end_date:
            break
        if d >= since:
            results.append(d)
        k += 1
    return results
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/domain/test_recurrence.py -v`
Expected: PASS (all 9 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/domain/models.py backend/src/quaestor/domain/rules.py backend/tests/domain/test_recurrence.py
git commit -m "feat(domain): add every-N recurrence date generator (ADR-020)"
```

---

### Task 2: Domain — recurring tables + Transaction.recurring_id + skipped status

**Files:**
- Modify: `backend/src/quaestor/domain/models.py`
- Test: `backend/tests/domain/test_recurring_models.py`

**Interfaces:**
- Consumes: `IntervalUnit` (Task 1), `TxType`, `TxStatus`.
- Produces:
  - `RecurringMode(str, Enum)`: `auto`, `manual`.
  - `OccurrenceStatus(str, Enum)`: `posted`, `planned`, `skipped`.
  - `TxStatus.skipped = "skipped"` (additive terminal state; affects neither balance nor `to_pay`).
  - `RecurringItem` table: `id`, `name`, `payee`, `type: TxType`, `mode: RecurringMode`, `amount: int`, `currency: str`, `category_id: int | None`, `account_id: int`, `interval_unit: IntervalUnit`, `interval_count: int`, `start_date: date`, `end_date: date | None`, `active: bool`.
  - `RecurringOccurrence` table: `id`, `recurring_id: int`, `due_date: date`, `status: OccurrenceStatus`, `transaction_id: int | None`, `created_at: datetime`; unique `(recurring_id, due_date)`.
  - `Transaction.recurring_id: int | None` (FK `recurring_item.id`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/domain/test_recurring_models.py`:

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    IntervalUnit,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    TxStatus,
    TxType,
)


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s


def test_skipped_status_exists():
    assert TxStatus.skipped.value == "skipped"


def test_create_recurring_item_and_occurrence(session):
    item = RecurringItem(
        name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=2_000_000, currency="COP", account_id=1,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.id is not None and item.active is True

    occ = RecurringOccurrence(
        recurring_id=item.id, due_date=date(2026, 1, 1), status=OccurrenceStatus.planned,
    )
    session.add(occ)
    session.commit()
    session.refresh(occ)
    assert occ.id is not None and occ.transaction_id is None


def test_unique_recurring_due_date(session):
    item = RecurringItem(
        name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", account_id=1,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    session.add(RecurringOccurrence(recurring_id=item.id, due_date=date(2026, 1, 5), status=OccurrenceStatus.planned))
    session.commit()
    session.add(RecurringOccurrence(recurring_id=item.id, due_date=date(2026, 1, 5), status=OccurrenceStatus.planned))
    with pytest.raises(IntegrityError):
        session.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/domain/test_recurring_models.py -v`
Expected: FAIL with `ImportError` (the new names don't exist yet).

- [ ] **Step 3: Add the enums and tables to models.py**

In `backend/src/quaestor/domain/models.py`:

Update the imports at the top to include `UniqueConstraint`:

```python
from sqlalchemy import Column, Numeric, UniqueConstraint
```

Add `skipped` to `TxStatus`:

```python
class TxStatus(str, Enum):
    planned = "planned"
    posted = "posted"
    skipped = "skipped"  # terminal cancel; affects neither balance nor to_pay
```

Add the two new enums after `IntervalUnit` (from Task 1):

```python
class RecurringMode(str, Enum):
    auto = "auto"
    manual = "manual"


class OccurrenceStatus(str, Enum):
    posted = "posted"
    planned = "planned"
    skipped = "skipped"
```

Add `recurring_id` to `Transaction` (next to `category_id`):

```python
    recurring_id: Annotated[Optional[int], Field(default=None, foreign_key="recurring_item.id")] = None
```

Add the two tables at the end of the file:

```python
class RecurringItem(SQLModel, table=True):
    __tablename__ = "recurring_item"
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    payee: str = ""
    type: TxType  # expense or income (validated in the service; never transfer)
    mode: RecurringMode
    amount: int  # centavos, original currency, positive (the default amount)
    currency: str
    category_id: Annotated[Optional[int], Field(default=None, foreign_key="category.id")] = None
    account_id: Annotated[int, Field(foreign_key="account.id")]
    interval_unit: IntervalUnit
    interval_count: int = 1
    start_date: date
    end_date: Optional[date] = None
    active: bool = True


class RecurringOccurrence(SQLModel, table=True):
    __tablename__ = "recurring_occurrence"
    __table_args__ = (
        UniqueConstraint("recurring_id", "due_date", name="uq_occurrence_recurring_due"),
    )
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    recurring_id: Annotated[int, Field(foreign_key="recurring_item.id", index=True)]
    due_date: date
    status: OccurrenceStatus
    transaction_id: Annotated[Optional[int], Field(default=None, foreign_key="transaction.id")] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/domain/test_recurring_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full domain + existing suite to catch regressions from the enum/column change**

Run: `uv run pytest tests/domain tests/services/test_transactions.py -v`
Expected: PASS (the additive `skipped` status and nullable `recurring_id` break nothing).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/domain/models.py backend/tests/domain/test_recurring_models.py
git commit -m "feat(domain): add RecurringItem/RecurringOccurrence + Transaction.recurring_id"
```

---

### Task 3: Domain + API — the `IllegalTransition` error

`confirm_payment`/`skip_payment` raise this when the target tx is not `planned`. It must exist before the planned services (Tasks 7–10) use it, and the API must map it (P1 surface). The MCP surface needs no change — `mcp.tools.core._as_text` already catches any `QuaestorError` and routes it through `format.domain_error_text`, which we extend in Task 12.

**Files:**
- Modify: `backend/src/quaestor/domain/errors.py`
- Modify: `backend/src/quaestor/api/errors.py`
- Test: `backend/tests/domain/test_errors_illegal_transition.py`

**Interfaces:**
- Consumes: `QuaestorError`.
- Produces: `IllegalTransition(QuaestorError)`; API status mapping `IllegalTransition → 409`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domain/test_errors_illegal_transition.py`:

```python
from quaestor.domain.errors import IllegalTransition, QuaestorError
from quaestor.api.errors import _STATUS


def test_illegal_transition_is_a_domain_error():
    assert issubclass(IllegalTransition, QuaestorError)


def test_illegal_transition_maps_to_409():
    assert _STATUS[IllegalTransition] == 409
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/domain/test_errors_illegal_transition.py -v`
Expected: FAIL with `ImportError: cannot import name 'IllegalTransition'`.

- [ ] **Step 3: Add the error and the API mapping**

In `backend/src/quaestor/domain/errors.py`, append:

```python
class IllegalTransition(QuaestorError):
    """A status transition that is not allowed (e.g. confirm/skip a non-planned tx)."""
```

In `backend/src/quaestor/api/errors.py`, import it and add it to `_STATUS`:

```python
from ..domain.errors import (
    IllegalTransition,
    MissingRate,
    NotFound,
    QuaestorError,
    TransferImbalance,
    ValidationError,
)
```

```python
_STATUS: dict[type[QuaestorError], int] = {
    ValidationError: 422,
    MissingRate: 409,
    TransferImbalance: 409,
    IllegalTransition: 409,
    NotFound: 404,
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/domain/test_errors_illegal_transition.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/errors.py backend/src/quaestor/api/errors.py backend/tests/domain/test_errors_illegal_transition.py
git commit -m "feat(domain): add IllegalTransition error + API 409 mapping"
```

---

### Task 4: Service — `create_recurring` + `list_recurring`

**Files:**
- Create: `backend/src/quaestor/services/recurring.py`
- Test: `backend/tests/services/test_recurring.py`

**Interfaces:**
- Consumes: `domain.models` (`RecurringItem`, `RecurringMode`, `IntervalUnit`, `TxType`, `Account`, `Category`), `domain.errors` (`ValidationError`, `NotFound`), `domain.money.is_supported`.
- Produces:
  - `create_recurring(session, name, payee, type, mode, amount, currency, category_id, account_id, interval_unit, interval_count, start_date, end_date=None) -> RecurringItem`
  - `list_recurring(session, active=None) -> list[RecurringItem]`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_recurring.py`:

```python
from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, IntervalUnit, RecurringMode, TxType
from quaestor.services import accounts, recurring


def _acc(session, currency="COP"):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=0)


def test_create_recurring_defaults_active(session):
    acc = _acc(session)
    item = recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense,
        mode=RecurringMode.auto, amount=2_000_000, currency="COP",
        category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    assert item.id is not None and item.active is True
    assert item.interval_unit == IntervalUnit.month


def test_create_recurring_rejects_transfer_type(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.transfer, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_bad_interval_count(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=0, start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_non_positive_amount(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=0, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_end_before_start(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=1,
            start_date=date(2026, 5, 1), end_date=date(2026, 1, 1),
        )


def test_create_recurring_unknown_account(session):
    with pytest.raises(NotFound):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=999,
            interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
        )


def test_list_recurring_filters_by_active(session):
    acc = _acc(session)
    a = recurring.create_recurring(
        session, name="A", payee="p", type=TxType.expense, mode=RecurringMode.auto,
        amount=1000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    b = recurring.create_recurring(
        session, name="B", payee="p", type=TxType.income, mode=RecurringMode.manual,
        amount=1000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.week, interval_count=2, start_date=date(2026, 1, 1),
    )
    b.active = False
    session.add(b)
    session.commit()
    assert {i.id for i in recurring.list_recurring(session)} == {a.id, b.id}
    assert {i.id for i in recurring.list_recurring(session, active=True)} == {a.id}
    assert {i.id for i in recurring.list_recurring(session, active=False)} == {b.id}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_recurring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.services.recurring'`.

- [ ] **Step 3: Implement `create_recurring` + `list_recurring`**

Create `backend/src/quaestor/services/recurring.py`:

```python
"""Recurring items: create/list, and the due-driven materialization (ADR-020)."""
from __future__ import annotations

from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    IntervalUnit,
    RecurringItem,
    RecurringMode,
    TxType,
)
from ..domain.money import is_supported


def _require_account(session: Session, account_id: int) -> Account:
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def create_recurring(
    session: Session,
    name: str,
    payee: str,
    type: TxType,
    mode: RecurringMode,
    amount: int,
    currency: str,
    category_id: int | None,
    account_id: int,
    interval_unit: IntervalUnit,
    interval_count: int,
    start_date: Date,
    end_date: Date | None = None,
) -> RecurringItem:
    """Create a recurring item. Validates frequency, money, and references.

    Raises:
        ValidationError: amount <= 0, unsupported currency, transfer type,
            interval_count < 1, end_date < start_date, unknown/archived category.
        NotFound: account does not exist.
    """
    type = TxType(type)
    mode = RecurringMode(mode)
    interval_unit = IntervalUnit(interval_unit)
    if type == TxType.transfer:
        raise ValidationError("recurring type must be expense or income, not transfer")
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    if interval_count < 1:
        raise ValidationError("interval_count must be >= 1")
    if end_date is not None and end_date < start_date:
        raise ValidationError("end_date must be on or after start_date")
    _require_account(session, account_id)
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
    item = RecurringItem(
        name=name,
        payee=payee or "",
        type=type,
        mode=mode,
        amount=amount,
        currency=currency,
        category_id=category_id,
        account_id=account_id,
        interval_unit=interval_unit,
        interval_count=interval_count,
        start_date=start_date,
        end_date=end_date,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_recurring(session: Session, active: bool | None = None) -> list[RecurringItem]:
    """List recurring items, optionally filtered by `active`, ordered by id."""
    stmt = select(RecurringItem)
    if active is not None:
        stmt = stmt.where(RecurringItem.active == active)
    return list(session.exec(stmt.order_by(RecurringItem.id)).all())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_recurring.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/recurring.py backend/tests/services/test_recurring.py
git commit -m "feat(services): add create_recurring and list_recurring"
```

---

### Task 5: Service — `materialize_due` (due-driven, auto/manual, idempotent)

The daily engine. For each active item it creates the occurrences with `due_date ≤ until_date` that don't yet exist: `auto` → a `posted` tx on its `due_date` + balance; `manual` → a `planned` tx, no balance. Idempotent by `(recurring_id, due_date)`. Commits once at the end (the scheduler populates FX before calling this, so `MissingRate` is not expected; if it occurs the whole run rolls back and self-heals next day).

**Files:**
- Modify: `backend/src/quaestor/services/recurring.py`
- Modify: `backend/tests/services/test_recurring.py`

**Interfaces:**
- Consumes: `rules.due_dates`, `transactions._resolve_fx`, `rules.delta_balance`, `money.to_base_cents`, `Transaction`, `TxStatus`, `Source`, `RecurringOccurrence`, `OccurrenceStatus`.
- Produces:
  - `materialize_due(session, until_date) -> list[RecurringOccurrence]` — the occurrences newly created this call.
  - `_create_occurrence_tx(session, item, due_date) -> RecurringOccurrence` (internal).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_recurring.py`:

```python
from quaestor.domain.models import OccurrenceStatus, Source, TxStatus
from quaestor.services import fx, transactions


def test_materialize_auto_posts_on_each_due_date(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=2_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    occs = recurring.materialize_due(session, date(2026, 3, 15))
    assert [o.due_date for o in occs] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    assert all(o.status == OccurrenceStatus.posted for o in occs)
    posted = transactions.list_transactions(session, status="posted")
    assert len(posted) == 3 and all(t.recurring_id is not None for t in posted)
    # auto posts on each real date and moves the balance by all three
    assert accounts_balance(session, acc.id) == -6_000_000


def accounts_balance(session, account_id):
    from quaestor.services import accounts
    return accounts.get_account(session, account_id).balance


def test_materialize_submonthly_generates_several_in_a_month(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Allowance", payee="Self", type=TxType.expense, mode=RecurringMode.auto,
        amount=10_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.week, interval_count=2, start_date=date(2026, 1, 1),
    )
    occs = recurring.materialize_due(session, date(2026, 1, 31))
    assert [o.due_date for o in occs] == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29)]


def test_materialize_manual_leaves_planned_without_balance(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 5),
    )
    occs = recurring.materialize_due(session, date(2026, 1, 31))
    assert len(occs) == 1 and occs[0].status == OccurrenceStatus.planned
    planned = transactions.list_transactions(session, status="planned")
    assert len(planned) == 1 and planned[0].date == date(2026, 1, 5)
    assert accounts_balance(session, acc.id) == 0  # planned never moves balance


def test_materialize_is_idempotent(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=2_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    first = recurring.materialize_due(session, date(2026, 2, 15))
    again = recurring.materialize_due(session, date(2026, 2, 15))
    assert len(first) == 2 and again == []  # nothing new on the second run
    assert len(transactions.list_transactions(session, status="posted")) == 2
    assert accounts_balance(session, acc.id) == -4_000_000


def test_materialize_missed_day_self_heals(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=1_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    recurring.materialize_due(session, date(2026, 1, 15))  # only January materialized
    occs = recurring.materialize_due(session, date(2026, 3, 15))  # catches Feb + Mar
    assert [o.due_date for o in occs] == [date(2026, 2, 1), date(2026, 3, 1)]


def test_materialize_skips_inactive_items(session):
    acc = _acc(session)
    item = recurring.create_recurring(
        session, name="Old", payee="x", type=TxType.expense, mode=RecurringMode.auto,
        amount=1000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    item.active = False
    session.add(item)
    session.commit()
    assert recurring.materialize_due(session, date(2026, 6, 1)) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_recurring.py -k materialize -v`
Expected: FAIL with `AttributeError: module 'quaestor.services.recurring' has no attribute 'materialize_due'`.

- [ ] **Step 3: Implement `materialize_due` and the tx-creation helper**

In `backend/src/quaestor/services/recurring.py`, extend the imports:

```python
from ..domain.models import (
    Account,
    Category,
    IntervalUnit,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported, to_base_cents
from ..domain.rules import delta_balance, due_dates
from . import transactions as _tx
```

Append these functions:

```python
def _existing_due_dates(session: Session, recurring_id: int) -> set[Date]:
    rows = session.exec(
        select(RecurringOccurrence.due_date).where(
            RecurringOccurrence.recurring_id == recurring_id
        )
    ).all()
    return set(rows)


def _create_occurrence_tx(
    session: Session, item: RecurringItem, due_date: Date
) -> RecurringOccurrence:
    """Create the tx + occurrence for one (item, due_date).

    auto  -> posted tx on due_date, balance moved, occurrence posted.
    manual-> planned tx on due_date, no balance, occurrence planned.
    Does NOT commit; the caller commits the whole batch.
    """
    rate = _tx._resolve_fx(session, item.currency, due_date, None)
    is_auto = item.mode == RecurringMode.auto
    tx = Transaction(
        date=due_date,
        payee=item.payee,
        notes=None,
        type=item.type,
        status=TxStatus.posted if is_auto else TxStatus.planned,
        amount=item.amount,
        currency=item.currency,
        fx_rate=rate,
        to_base=to_base_cents(item.amount, rate),
        account_id=item.account_id,
        category_id=item.category_id,
        recurring_id=item.id,
        source=Source.manual,
    )
    session.add(tx)
    if is_auto:
        acc = session.get(Account, item.account_id)
        acc.balance += delta_balance(item.type, item.amount)
        session.add(acc)
    session.flush()  # assign tx.id for the occurrence link
    occ = RecurringOccurrence(
        recurring_id=item.id,
        due_date=due_date,
        status=OccurrenceStatus.posted if is_auto else OccurrenceStatus.planned,
        transaction_id=tx.id,
    )
    session.add(occ)
    return occ


def materialize_due(session: Session, until_date: Date) -> list[RecurringOccurrence]:
    """Create every not-yet-materialized occurrence with due_date <= until_date.

    Due-driven (ADR-020): runs daily via the scheduler with until_date=today.
    Idempotent by (recurring_id, due_date). Returns the occurrences created now.
    On any error the whole batch rolls back (self-heals on the next run).

    Raises:
        MissingRate: a non-COP auto/manual item with no FX rate for a due_date.
    """
    created: list[RecurringOccurrence] = []
    try:
        for item in list_recurring(session, active=True):
            existing = _existing_due_dates(session, item.id)
            for d in due_dates(
                item.start_date, item.end_date, item.interval_unit,
                item.interval_count, item.start_date, until_date,
            ):
                if d in existing:
                    continue
                created.append(_create_occurrence_tx(session, item, d))
        session.commit()
    except Exception:
        session.rollback()
        raise
    for occ in created:
        session.refresh(occ)
    return created
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_recurring.py -v`
Expected: PASS (all recurring tests, including the 6 new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/recurring.py backend/tests/services/test_recurring.py
git commit -m "feat(services): add due-driven materialize_due (auto/manual, idempotent)"
```

---

### Task 6: Service — `skip_recurring`

Skips a single occurrence for a `due_date` (not the whole item — for that, set `active=False`). Creates the occurrence as `skipped` if it doesn't exist yet, or marks the existing one `skipped`; if a planned tx was already materialized for it, that tx is skipped too. After this, `materialize_due` leaves the date alone (the occurrence exists).

**Files:**
- Modify: `backend/src/quaestor/services/recurring.py`
- Modify: `backend/tests/services/test_recurring.py`

**Interfaces:**
- Consumes: `RecurringItem`, `RecurringOccurrence`, `OccurrenceStatus`, `Transaction`, `TxStatus`, `NotFound`.
- Produces: `skip_recurring(session, recurring_id, due_date) -> RecurringOccurrence`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_recurring.py`:

```python
def test_skip_recurring_before_materialization_blocks_it(session):
    acc = _acc(session)
    item = recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=1_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    occ = recurring.skip_recurring(session, item.id, date(2026, 2, 1))
    assert occ.status == OccurrenceStatus.skipped and occ.transaction_id is None
    occs = recurring.materialize_due(session, date(2026, 3, 15))
    # Jan and Mar materialize; Feb stays skipped and is not recreated
    assert [o.due_date for o in occs] == [date(2026, 1, 1), date(2026, 3, 1)]


def test_skip_recurring_after_manual_materialization_skips_the_planned_tx(session):
    acc = _acc(session)
    item = recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 5),
    )
    recurring.materialize_due(session, date(2026, 1, 31))
    assert len(transactions.list_transactions(session, status="planned")) == 1
    occ = recurring.skip_recurring(session, item.id, date(2026, 1, 5))
    assert occ.status == OccurrenceStatus.skipped
    assert transactions.list_transactions(session, status="planned") == []
    assert len(transactions.list_transactions(session, status="skipped")) == 1


def test_skip_recurring_unknown_item(session):
    with pytest.raises(NotFound):
        recurring.skip_recurring(session, 999, date(2026, 1, 1))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_recurring.py -k skip_recurring -v`
Expected: FAIL with `AttributeError: ... has no attribute 'skip_recurring'`.

- [ ] **Step 3: Implement `skip_recurring`**

Append to `backend/src/quaestor/services/recurring.py`:

```python
def skip_recurring(
    session: Session, recurring_id: int, due_date: Date
) -> RecurringOccurrence:
    """Mark (or create) the occurrence for (recurring_id, due_date) as skipped.

    A planned tx already materialized for that occurrence is skipped too, so it
    leaves to_pay. materialize_due will not recreate the date afterwards.

    Raises:
        NotFound: the recurring item does not exist.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    occ = session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.recurring_id == recurring_id,
            RecurringOccurrence.due_date == due_date,
        )
    ).first()
    if occ is None:
        occ = RecurringOccurrence(
            recurring_id=recurring_id,
            due_date=due_date,
            status=OccurrenceStatus.skipped,
        )
    else:
        occ.status = OccurrenceStatus.skipped
        if occ.transaction_id is not None:
            tx = session.get(Transaction, occ.transaction_id)
            if tx is not None and tx.status == TxStatus.planned:
                tx.status = TxStatus.skipped
                session.add(tx)
    session.add(occ)
    session.commit()
    session.refresh(occ)
    return occ
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_recurring.py -v`
Expected: PASS (all recurring tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/recurring.py backend/tests/services/test_recurring.py
git commit -m "feat(services): add skip_recurring (single occurrence)"
```

---

### Task 7: Service — `plan_payment` + `to_pay`

`plan_payment` creates a standalone `planned` expense (no `recurring_id`, no balance). `to_pay` is the single confirmation queue (ADR-007): all `planned` txs in `[since, until]`, ordered by date, plus the COP total.

**Files:**
- Create: `backend/src/quaestor/services/planned.py`
- Test: `backend/tests/services/test_planned.py`

**Interfaces:**
- Consumes: `transactions._resolve_fx`, `transactions.list_transactions`, `money.to_base_cents`, `money.is_supported`, `Transaction`, `TxType`, `TxStatus`, `Source`, `Account`, `Category`, errors.
- Produces:
  - `plan_payment(session, payee, amount, currency, due_date, account_id, category_id=None, notes=None) -> Transaction`
  - `to_pay(session, since, until) -> dict` with keys `items: list[Transaction]`, `total_base: int`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_planned.py`:

```python
from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, TxStatus, TxType
from quaestor.services import accounts, planned, transactions


def _acc(session, currency="COP", balance=0):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=balance)


def test_plan_payment_creates_planned_without_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session, payee="Friend", amount=80_000, currency="COP",
        due_date=date(2026, 6, 20), account_id=acc.id,
    )
    assert tx.status == TxStatus.planned and tx.type == TxType.expense
    assert tx.recurring_id is None
    assert accounts.get_account(session, acc.id).balance == 500_000  # untouched


def test_plan_payment_rejects_bad_amount(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        planned.plan_payment(
            session, payee="x", amount=0, currency="COP",
            due_date=date(2026, 6, 20), account_id=acc.id,
        )


def test_plan_payment_unknown_account(session):
    with pytest.raises(NotFound):
        planned.plan_payment(
            session, payee="x", amount=1000, currency="COP",
            due_date=date(2026, 6, 20), account_id=999,
        )


def test_to_pay_window_orders_and_totals(session):
    acc = _acc(session)
    planned.plan_payment(session, payee="A", amount=10_000, currency="COP",
                         due_date=date(2026, 6, 10), account_id=acc.id)
    planned.plan_payment(session, payee="B", amount=20_000, currency="COP",
                         due_date=date(2026, 6, 5), account_id=acc.id)
    planned.plan_payment(session, payee="C", amount=99_000, currency="COP",
                         due_date=date(2026, 7, 1), account_id=acc.id)  # outside window
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert [t.payee for t in result["items"]] == ["B", "A"]  # ordered by date
    assert result["total_base"] == 30_000


def test_to_pay_excludes_posted(session):
    acc = _acc(session, balance=1_000_000)
    transactions.record_expense(session, acc.id, 5_000, "COP", date(2026, 6, 10), "Posted")
    planned.plan_payment(session, payee="Planned", amount=7_000, currency="COP",
                         due_date=date(2026, 6, 11), account_id=acc.id)
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert [t.payee for t in result["items"]] == ["Planned"]
    assert result["total_base"] == 7_000


def test_to_pay_inverted_window_raises(session):
    with pytest.raises(ValidationError):
        planned.to_pay(session, date(2026, 6, 30), date(2026, 6, 1))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_planned.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.services.planned'`.

- [ ] **Step 3: Implement `plan_payment` + `to_pay`**

Create `backend/src/quaestor/services/planned.py`:

```python
"""Planned payments: the to-pay queue, plan/confirm/skip (ADR-007).

confirm_payment is the only planned -> posted transition and fires the
post-confirm hooks (the seam P4 uses to record goal contributions).
"""
from __future__ import annotations

from datetime import date as Date

from sqlmodel import Session

from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported, to_base_cents
from . import transactions as _tx


def _require_account(session: Session, account_id: int) -> Account:
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def plan_payment(
    session: Session,
    payee: str,
    amount: int,
    currency: str,
    due_date: Date,
    account_id: int,
    category_id: int | None = None,
    notes: str | None = None,
) -> Transaction:
    """Create a standalone `planned` expense due on `due_date`. No balance change.

    Raises:
        ValidationError: amount <= 0, unsupported currency, unknown/archived category.
        NotFound: account does not exist.
        MissingRate: non-COP with no rate for due_date.
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    _require_account(session, account_id)
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
    rate = _tx._resolve_fx(session, currency, due_date, None)
    tx = Transaction(
        date=due_date,
        payee=payee or "",
        notes=notes,
        type=TxType.expense,
        status=TxStatus.planned,
        amount=amount,
        currency=currency,
        fx_rate=rate,
        to_base=to_base_cents(amount, rate),
        account_id=account_id,
        category_id=category_id,
        source=Source.manual,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def to_pay(session: Session, since: Date, until: Date) -> dict:
    """The single confirmation queue: all `planned` txs in [since, until].

    Ordered by date. `total_base` is the sum of `to_base` (COP cents). Excludes
    `posted` and `skipped`.

    Raises:
        ValidationError: since > until (inverted window).
    """
    if since > until:
        raise ValidationError("to_pay window is inverted (since > until)")
    items = _tx.list_transactions(
        session, status="planned", date_from=since, date_to=until
    )
    total_base = sum(t.to_base for t in items)
    return {"items": items, "total_base": total_base}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_planned.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/planned.py backend/tests/services/test_planned.py
git commit -m "feat(services): add plan_payment and the to_pay queue"
```

---

### Task 8: Service — `confirm_payment` (expense/income) + post-confirm hooks + occurrence sync

`planned` → `posted`, applying a real `amount`/`date` if given, recomputing `to_base`, moving the balance. If the tx came from a manual occurrence, that occurrence is synced to `posted`. After posting — in the **same transaction** — the post-confirm hooks fire (the seam P4 uses). Any hook failure rolls back the whole confirmation. The transfer arm is added in Task 9.

**Files:**
- Modify: `backend/src/quaestor/services/planned.py`
- Modify: `backend/tests/services/test_planned.py`

**Interfaces:**
- Consumes: `transactions.get_transaction`, `transactions._resolve_fx`, `rules.delta_balance`, `money.to_base_cents`, `RecurringOccurrence`, `OccurrenceStatus`, `IllegalTransition`.
- Produces:
  - `POST_CONFIRM_HOOKS: list[Callable[[Transaction, Session], None]]`
  - `register_post_confirm_hook(fn: Callable[[Transaction, Session], None]) -> None`
  - `confirm_payment(session, tx_id, amount=None, date=None) -> Transaction`
  - `_sync_occurrence_posted(session, tx) -> None` (internal)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_planned.py`:

```python
from quaestor.domain.errors import IllegalTransition
from quaestor.domain.models import OccurrenceStatus, RecurringMode, IntervalUnit
from quaestor.services import recurring


def test_confirm_posts_and_moves_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Friend", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted
    assert accounts.get_account(session, acc.id).balance == 420_000


def test_confirm_with_adjusted_amount_recomputes_to_base_and_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Electric", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    confirmed = planned.confirm_payment(session, tx.id, amount=95_000, date=date(2026, 6, 22))
    assert confirmed.amount == 95_000 and confirmed.date == date(2026, 6, 22)
    assert confirmed.to_base == 95_000
    assert accounts.get_account(session, acc.id).balance == 405_000


def test_confirm_syncs_manual_occurrence_to_posted(session):
    acc = _acc(session, balance=1_000_000)
    item = recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 5),
    )
    recurring.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.confirm_payment(session, planned_tx.id, amount=53_000)
    occ = recurring.list_recurring(session)  # sanity: item still there
    from sqlmodel import select
    from quaestor.domain.models import RecurringOccurrence
    occ_row = session.exec(
        select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item.id)
    ).first()
    assert occ_row.status == OccurrenceStatus.posted
    assert accounts.get_account(session, acc.id).balance == 947_000


def test_confirm_non_planned_raises_illegal_transition(session):
    acc = _acc(session, balance=500_000)
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 1), "x")
    with pytest.raises(IllegalTransition):
        planned.confirm_payment(session, tx.id)


def test_confirm_unknown_tx_raises_not_found(session):
    with pytest.raises(NotFound):
        planned.confirm_payment(session, 999)


def test_post_confirm_hook_runs_in_same_transaction_and_failure_rolls_back(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Goal", amount=100_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)

    def boom(t, s):
        raise RuntimeError("hook failed")

    planned.POST_CONFIRM_HOOKS.append(boom)
    try:
        with pytest.raises(RuntimeError):
            planned.confirm_payment(session, tx.id)
    finally:
        planned.POST_CONFIRM_HOOKS.remove(boom)
    # rolled back: still planned, balance untouched
    reloaded = transactions.get_transaction(session, tx.id)
    assert reloaded.status == TxStatus.planned
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_post_confirm_hook_sees_posted_tx(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Goal", amount=100_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    seen = {}

    def record(t, s):
        seen["status"] = t.status

    planned.register_post_confirm_hook(record)
    try:
        planned.confirm_payment(session, tx.id)
    finally:
        planned.POST_CONFIRM_HOOKS.remove(record)
    assert seen["status"] == TxStatus.posted
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_planned.py -k "confirm or hook" -v`
Expected: FAIL with `AttributeError: ... has no attribute 'confirm_payment'`.

- [ ] **Step 3: Implement the hook registry, occurrence sync, and `confirm_payment`**

In `backend/src/quaestor/services/planned.py`, extend imports:

```python
from typing import Callable

from ..domain.errors import IllegalTransition, NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    OccurrenceStatus,
    RecurringOccurrence,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.rules import delta_balance
from sqlmodel import Session, select
```

(Replace the existing `from sqlmodel import Session` line with the `Session, select` import above, and merge the model imports.)

Add the registry near the top (after imports):

```python
POST_CONFIRM_HOOKS: list[Callable[[Transaction, Session], None]] = []


def register_post_confirm_hook(fn: Callable[[Transaction, Session], None]) -> None:
    """Register a hook fired inside confirm_payment's transaction, after posting."""
    POST_CONFIRM_HOOKS.append(fn)
```

Append the sync helper and `confirm_payment`:

```python
def _sync_occurrence_posted(session: Session, tx: Transaction) -> None:
    """If tx came from a manual occurrence, mark that occurrence posted."""
    occ = session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.transaction_id == tx.id
        )
    ).first()
    if occ is not None and occ.status != OccurrenceStatus.posted:
        occ.status = OccurrenceStatus.posted
        session.add(occ)


def confirm_payment(
    session: Session,
    tx_id: int,
    amount: int | None = None,
    date: Date | None = None,
) -> Transaction:
    """planned -> posted; the only such transition. Fires post-confirm hooks.

    Applies the real amount/date if provided, recomputes to_base, moves the
    balance, and syncs a manual occurrence to posted. A `transfer` tx is
    materialized into a real posted pair (Task 9). Everything (post + hooks)
    runs in one transaction; any failure rolls back.

    Raises:
        NotFound: the tx does not exist.
        IllegalTransition: the tx is not `planned`.
        ValidationError: a non-positive adjusted amount.
        MissingRate: a non-COP tx with no rate for its date.
    """
    tx = _tx.get_transaction(session, tx_id)
    if tx.status != TxStatus.planned:
        raise IllegalTransition(
            f"transaction {tx_id} is {tx.status.value}, not planned"
        )
    try:
        if tx.type == TxType.transfer:
            result = _materialize_planned_transfer(session, tx, amount, date)
        else:
            if amount is not None:
                tx.amount = amount
            if date is not None:
                tx.date = date
            if tx.amount <= 0:
                raise ValidationError("amount must be > 0")
            rate = _tx._resolve_fx(session, tx.currency, tx.date, None)
            tx.fx_rate = rate
            tx.to_base = to_base_cents(tx.amount, rate)
            acc = _require_account(session, tx.account_id)
            acc.balance += delta_balance(tx.type, tx.amount)
            tx.status = TxStatus.posted
            _sync_occurrence_posted(session, tx)
            session.add(tx)
            session.add(acc)
            result = tx
        for hook in POST_CONFIRM_HOOKS:
            hook(result, session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(result)
    return result
```

Note: `_materialize_planned_transfer` is referenced here but implemented in Task 9. Until then the transfer branch is unreachable in these tests (no planned transfers are created). If your runner imports lazily this is fine; if you prefer, add a temporary stub `def _materialize_planned_transfer(session, tx, amount, date): raise NotImplementedError` and replace it in Task 9. The Task 8 tests never hit it.

- [ ] **Step 4: Add the temporary stub so the module imports**

At the end of `backend/src/quaestor/services/planned.py`, add:

```python
def _materialize_planned_transfer(session, tx, amount, date):  # replaced in Task 9
    raise NotImplementedError("planned transfer materialization arrives in Task 9")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_planned.py -v`
Expected: PASS (all planned tests so far).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/services/planned.py backend/tests/services/test_planned.py
git commit -m "feat(services): add confirm_payment (expense/income) + post-confirm hooks"
```

---

### Task 9: Service — `confirm_payment` materializes a planned transfer

A `planned` tx of `type=transfer` is confirmed by materializing a real posted **pair** (a generic capability, not goal-specific — ADR-018 B2). Convention (ADR-015): the planned transfer row's `account_id` is the **destination**; the **source** is `Settings.default_source_account_id`. We post the original row as the destination leg and create the matching source leg, sharing a `transfer_group_id`, all inside `confirm_payment`'s single transaction (so the post-confirm hook still rolls back on failure). This replaces the Task 8 stub.

**Files:**
- Modify: `backend/src/quaestor/services/planned.py`
- Modify: `backend/tests/services/test_planned.py`

**Interfaces:**
- Consumes: `Settings`, `Account`, `rules.transfer_deltas`, `transactions._resolve_fx`, `money.to_base_cents`, `uuid`.
- Produces: `_materialize_planned_transfer(session, tx, amount, date) -> Transaction` (real implementation).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_planned.py`:

```python
def _planned_transfer(session, dst_account_id, amount=100_000, due=date(2026, 6, 20)):
    """Construct a planned transfer row directly (P4 normally creates these)."""
    from quaestor.domain.models import Transaction
    from decimal import Decimal
    tx = Transaction(
        date=due, payee="Savings goal", type=TxType.transfer, status=TxStatus.planned,
        amount=amount, currency="COP", fx_rate=Decimal("1"), to_base=amount,
        account_id=dst_account_id, source="manual",
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_confirm_planned_transfer_materializes_posted_pair(session):
    from quaestor.services import settings as settings_svc
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    tx = _planned_transfer(session, dst.id, amount=100_000)
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted and confirmed.transfer_group_id is not None
    assert accounts.get_account(session, src.id).balance == 900_000
    assert accounts.get_account(session, dst.id).balance == 100_000
    # exactly one posted pair sharing the group
    posted = transactions.list_transactions(session, status="posted", type=TxType.transfer)
    assert len(posted) == 2
    assert posted[0].transfer_group_id == posted[1].transfer_group_id


def test_confirm_planned_transfer_without_default_source_raises(session):
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    tx = _planned_transfer(session, dst.id)
    with pytest.raises(ValidationError):
        planned.confirm_payment(session, tx.id)
```

Note: this task relies on `services.settings.update_settings(session, default_source_account_id=...)`. Confirm that helper exists (P0/P1 `services/settings.py`); if its signature differs, set `Settings.default_source_account_id` directly in the test via the session instead.

- [ ] **Step 2: Verify the settings helper signature**

Run: `uv run python -c "from quaestor.services import settings; print([n for n in dir(settings) if not n.startswith('__')])"` from `backend/`.
Expected: a list containing `update_settings` (or similar). If absent, adjust the test's setup line to:

```python
    s = session.get(__import__('quaestor.domain.models', fromlist=['Settings']).Settings, 1)
    s.default_source_account_id = src.id
    session.add(s); session.commit()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_planned.py -k planned_transfer -v`
Expected: FAIL with `NotImplementedError` (the Task 8 stub).

- [ ] **Step 4: Replace the stub with the real implementation**

Extend imports in `backend/src/quaestor/services/planned.py`:

```python
import uuid

from ..domain.models import Settings  # add to the existing models import
from ..domain.rules import delta_balance, transfer_deltas  # add transfer_deltas
```

Replace the stub `_materialize_planned_transfer` with:

```python
def _materialize_planned_transfer(
    session: Session, tx: Transaction, amount: int | None, date: Date | None
) -> Transaction:
    """Turn a planned transfer into a real posted pair.

    tx.account_id is the destination (ADR-015); the source is the global
    Settings.default_source_account_id. The original row becomes the
    destination leg; a new source leg is created sharing a transfer_group_id.
    Does NOT commit (the caller's transaction owns the commit).
    """
    if amount is not None:
        tx.amount = amount
    if date is not None:
        tx.date = date
    if tx.amount <= 0:
        raise ValidationError("amount must be > 0")
    settings = session.get(Settings, 1)
    src_id = settings.default_source_account_id if settings else None
    if src_id is None:
        raise ValidationError("no default source account configured for transfers")
    if src_id == tx.account_id:
        raise ValidationError("source and destination cannot be the same account")
    src = _require_account(session, src_id)
    dst = _require_account(session, tx.account_id)
    if tx.currency != src.currency or tx.currency != dst.currency:
        raise ValidationError("transfer currency must match both accounts")
    rate = _tx._resolve_fx(session, tx.currency, tx.date, None)
    to_base = to_base_cents(tx.amount, rate)
    group = uuid.uuid4().hex
    d_from, d_to = transfer_deltas(tx.amount)
    from_leg = Transaction(
        date=tx.date,
        payee=tx.payee,
        notes=tx.notes,
        type=TxType.transfer,
        status=TxStatus.posted,
        amount=tx.amount,
        currency=tx.currency,
        fx_rate=rate,
        to_base=to_base,
        account_id=src_id,
        transfer_group_id=group,
        source=Source.manual,
    )
    tx.fx_rate = rate
    tx.to_base = to_base
    tx.transfer_group_id = group
    tx.status = TxStatus.posted
    src.balance += d_from
    dst.balance += d_to
    _sync_occurrence_posted(session, tx)
    session.add_all([from_leg, tx, src, dst])
    return tx
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_planned.py -v`
Expected: PASS (all planned tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/services/planned.py backend/tests/services/test_planned.py
git commit -m "feat(services): materialize planned transfers in confirm_payment (ADR-015/018)"
```

---

### Task 10: Service — `skip_payment`

Cancels a standalone `planned` tx (planned → skipped). If it came from an occurrence, the occurrence is marked `skipped` too. Skipping leaves `to_pay`; the balance never moves.

**Files:**
- Modify: `backend/src/quaestor/services/planned.py`
- Modify: `backend/tests/services/test_planned.py`

**Interfaces:**
- Consumes: `transactions.get_transaction`, `RecurringOccurrence`, `OccurrenceStatus`, `TxStatus`, `IllegalTransition`.
- Produces: `skip_payment(session, tx_id) -> Transaction`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_planned.py`:

```python
def test_skip_payment_cancels_standalone_planned(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Friend", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    skipped = planned.skip_payment(session, tx.id)
    assert skipped.status == TxStatus.skipped
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert result["items"] == []  # left the queue
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_skip_payment_marks_occurrence_skipped(session):
    acc = _acc(session, balance=1_000_000)
    item = recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 5),
    )
    recurring.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.skip_payment(session, planned_tx.id)
    from sqlmodel import select
    from quaestor.domain.models import RecurringOccurrence
    occ = session.exec(
        select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item.id)
    ).first()
    assert occ.status == OccurrenceStatus.skipped


def test_skip_payment_non_planned_raises(session):
    acc = _acc(session, balance=500_000)
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 1), "x")
    with pytest.raises(IllegalTransition):
        planned.skip_payment(session, tx.id)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_planned.py -k skip_payment -v`
Expected: FAIL with `AttributeError: ... has no attribute 'skip_payment'`.

- [ ] **Step 3: Implement `skip_payment`**

Append to `backend/src/quaestor/services/planned.py`:

```python
def skip_payment(session: Session, tx_id: int) -> Transaction:
    """Cancel a `planned` tx (planned -> skipped). Syncs its occurrence if any.

    Raises:
        NotFound: the tx does not exist.
        IllegalTransition: the tx is not `planned`.
    """
    tx = _tx.get_transaction(session, tx_id)
    if tx.status != TxStatus.planned:
        raise IllegalTransition(
            f"transaction {tx_id} is {tx.status.value}, not planned"
        )
    tx.status = TxStatus.skipped
    occ = session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.transaction_id == tx.id
        )
    ).first()
    if occ is not None:
        occ.status = OccurrenceStatus.skipped
        session.add(occ)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_planned.py -v`
Expected: PASS (all planned tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/planned.py backend/tests/services/test_planned.py
git commit -m "feat(services): add skip_payment (planned -> skipped)"
```

---

### Task 11: Service — `close_month` + `ensure_month_closed` + rollover hook registry

The monthly close (ADR-017/022). `close_month(period)` runs the registered rollover hooks in **one transaction** (full rollback on any failure). P3 registers **no** hooks of its own — it leaves the seam ready and empty (P4 registers `propose_goal_contributions`). `ensure_month_closed(today)` derives the calendar month from `today` and calls `close_month`; the scheduler runs it daily, so a missed close self-heals. With no hooks, the close is trivially idempotent; the tests verify the mechanism (ordering, atomicity, idempotency) using registered test hooks.

**Files:**
- Create: `backend/src/quaestor/services/rollover.py`
- Test: `backend/tests/services/test_rollover.py`

**Interfaces:**
- Consumes: `db.atomic`.
- Produces:
  - `ROLLOVER_HOOKS: list[Callable[[str, Session], None]]`
  - `register_rollover_hook(fn: Callable[[str, Session], None]) -> None`
  - `close_month(session, period: str) -> None` — `period` is `"YYYY-MM"`.
  - `ensure_month_closed(session, today: date) -> None`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_rollover.py`:

```python
from datetime import date

import pytest

from quaestor.services import rollover


def test_close_month_runs_hooks_in_registration_order(session):
    calls = []
    h1 = lambda period, s: calls.append(("h1", period))
    h2 = lambda period, s: calls.append(("h2", period))
    rollover.register_rollover_hook(h1)
    rollover.register_rollover_hook(h2)
    try:
        rollover.close_month(session, "2026-06")
    finally:
        rollover.ROLLOVER_HOOKS.remove(h1)
        rollover.ROLLOVER_HOOKS.remove(h2)
    assert calls == [("h1", "2026-06"), ("h2", "2026-06")]


def test_close_month_with_no_hooks_is_a_noop(session):
    rollover.close_month(session, "2026-06")  # must not raise


def test_close_month_atomicity_rolls_back_on_hook_failure(session):
    # Hooks must write DIRECTLY to the session (never call committing services),
    # so a later hook's failure rolls back the whole close.
    from quaestor.services import accounts
    from quaestor.domain.models import Account, AccountType

    def good(period, s):
        s.add(Account(name="Created by hook", type=AccountType.debit, currency="COP", balance=0))
        s.flush()  # visible within the transaction, not committed

    def bad(period, s):
        raise RuntimeError("hook blew up")

    rollover.register_rollover_hook(good)
    rollover.register_rollover_hook(bad)
    try:
        with pytest.raises(RuntimeError):
            rollover.close_month(session, "2026-06")
    finally:
        rollover.ROLLOVER_HOOKS.remove(good)
        rollover.ROLLOVER_HOOKS.remove(bad)
    # full rollback: the account added by `good` is gone
    assert accounts.list_accounts(session) == []


def test_close_month_idempotent_with_self_keyed_hook(session):
    # a hook idempotent by its own (key, period) must not duplicate on re-run
    state = {"created": set()}

    def once_per_period(period, s):
        if period in state["created"]:
            return
        state["created"].add(period)

    rollover.register_rollover_hook(once_per_period)
    try:
        rollover.close_month(session, "2026-06")
        rollover.close_month(session, "2026-06")
        rollover.close_month(session, "2026-06")
    finally:
        rollover.ROLLOVER_HOOKS.remove(once_per_period)
    assert state["created"] == {"2026-06"}


def test_ensure_month_closed_uses_current_calendar_month(session):
    seen = []
    rollover.register_rollover_hook(lambda period, s: seen.append(period))
    try:
        rollover.ensure_month_closed(session, date(2026, 6, 19))
    finally:
        rollover.ROLLOVER_HOOKS.pop()
    assert seen == ["2026-06"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_rollover.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.services.rollover'`.

- [ ] **Step 3: Implement `rollover.py`**

Create `backend/src/quaestor/services/rollover.py`:

```python
"""Monthly close (ADR-017/022): an atomic, idempotent run of rollover hooks.

P3 registers no hooks of its own (its temporal work is the daily materialize_due).
It leaves the seam ready and empty; P4 registers propose_goal_contributions via
register_rollover_hook without touching close_month. Each hook is
(period, session) -> None, runs in the same transaction, must be idempotent on
its own, and a failure in any hook aborts the whole close.
"""
from __future__ import annotations

from datetime import date as Date
from typing import Callable

from sqlmodel import Session

from ..db import atomic

ROLLOVER_HOOKS: list[Callable[[str, Session], None]] = []


def register_rollover_hook(fn: Callable[[str, Session], None]) -> None:
    """Register a hook fired by close_month, in registration order."""
    ROLLOVER_HOOKS.append(fn)


def close_month(session: Session, period: str) -> None:
    """Close the calendar month `period` ("YYYY-MM"): run all rollover hooks atomically.

    Runs hooks in registration order inside one transaction. Any hook failure
    rolls back the entire close. Idempotency is each hook's own responsibility
    (keyed by its (..., period)); re-running close_month must not duplicate.
    """
    with atomic(session):
        for hook in ROLLOVER_HOOKS:
            hook(period, session)


def ensure_month_closed(session: Session, today: Date) -> None:
    """Idempotent daily 'ensure': close the current calendar month.

    The scheduler (P7) calls this daily. On any day it closes today's month;
    because the registered hooks are idempotent, the repeated calls are no-ops
    and a missed day self-heals on the next run.
    """
    period = f"{today.year:04d}-{today.month:02d}"
    close_month(session, period)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_rollover.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/rollover.py backend/tests/services/test_rollover.py
git commit -m "feat(services): add close_month + ensure_month_closed + rollover hook seam"
```

---

### Task 12: MCP — the 7 user tools (P2 surface)

Expose the user-facing services as MCP tools, mirroring `mcp/tools/core.py`: one input model per tool, an `@_as_text`-wrapped impl that resolves names→ids and calls exactly one service, formatted output. `materialize_due`/`close_month` are **not** exposed (the scheduler runs them — ADR-017/020). Reuse `core._as_text`, `core._resolve_account`, `core._resolve_category`.

**Files:**
- Create: `backend/src/quaestor/mcp/tools/temporal.py`
- Modify: `backend/src/quaestor/mcp/format.py` (add renderers + `IllegalTransition` text)
- Modify: `backend/src/quaestor/mcp/registry.py` (add `register_temporal_tools` + `TEMPORAL_TOOL_NAMES`)
- Modify: `backend/src/quaestor/mcp/server.py` (call `register_temporal_tools`)
- Test: `backend/tests/mcp/test_temporal.py`

**Interfaces:**
- Consumes: `services.recurring`, `services.planned`, `core._as_text`, `core._resolve_account`, `core._resolve_category`, `format.*`.
- Produces:
  - `TEMPORAL_TOOL_NAMES = ("create_recurring", "list_recurring", "plan_payment", "confirm_payment", "skip_payment", "skip_recurring", "to_pay")`
  - `register_temporal_tools(mcp) -> None`
  - format renderers: `recurring_created`, `recurring_list`, `payment_planned`, `payment_confirmed`, `payment_skipped`, `recurring_skipped`, `to_pay_table`.

- [ ] **Step 1: Add the IllegalTransition branch + renderers to format.py**

In `backend/src/quaestor/mcp/format.py`, import the error and the new models:

```python
from ..domain.errors import (
    IllegalTransition,
    MissingRate,
    NotFound,
    QuaestorError,
    TransferImbalance,
    ValidationError,
)
from ..domain.models import (
    Account,
    Category,
    CategoryGroup,
    FxRate,
    RecurringItem,
    RecurringOccurrence,
    Tag,
    Transaction,
)
```

In `domain_error_text`, add an `IllegalTransition` branch before the `ValidationError` one:

```python
    if isinstance(exc, IllegalTransition):
        return f"Can't do that: {exc}."
```

Append the renderers:

```python
def recurring_created(item: RecurringItem) -> str:
    every = (
        f"{item.interval_count} {item.interval_unit.value}"
        if item.interval_count != 1
        else item.interval_unit.value
    )
    end = f", until {item.end_date.isoformat()}" if item.end_date else ""
    return (
        f"✅ Recurring **{item.name}** ({item.type.value}, {item.mode.value}) — "
        f"{money(item.amount, item.currency)} every {every}, "
        f"from {item.start_date.isoformat()}{end}. id={item.id}"
    )


def recurring_list(items: list[RecurringItem]) -> str:
    if not items:
        return "No recurring items."
    rows = ["| id | Name | Type | Mode | Amount | Every | Active |", "|---|---|---|---|---|---|---|"]
    for i in items:
        every = (
            f"{i.interval_count} {i.interval_unit.value}"
            if i.interval_count != 1
            else i.interval_unit.value
        )
        rows.append(
            f"| {i.id} | {i.name} | {i.type.value} | {i.mode.value} | "
            f"{cents_to_major(i.amount)} {i.currency} | {every} | "
            f"{'yes' if i.active else 'no'} |"
        )
    return "\n".join(rows)


def payment_planned(tx: Transaction) -> str:
    return (
        f"✅ Planned payment **{tx.payee}** — {money(tx.amount, tx.currency)} "
        f"due {tx.date.isoformat()}. id={tx.id} (not yet posted)"
    )


def payment_confirmed(tx: Transaction) -> str:
    return (
        f"✅ Confirmed **{tx.payee}** — {money(tx.amount, tx.currency)} "
        f"posted on {tx.date.isoformat()}. id={tx.id}"
    )


def payment_skipped(tx: Transaction) -> str:
    return f"✅ Skipped **{tx.payee}** — {money(tx.amount, tx.currency)}. id={tx.id}"


def recurring_skipped(occ: RecurringOccurrence) -> str:
    return (
        f"✅ Skipped the occurrence for recurring item {occ.recurring_id} "
        f"due {occ.due_date.isoformat()}."
    )


def to_pay_table(result: dict) -> str:
    items = result["items"]
    if not items:
        return "Nothing to pay in that window. 🎉"
    rows = ["| id | Due | Payee | Amount | Currency | COP |", "|---|---|---|---|---|---|"]
    for t in items:
        rows.append(
            f"| {t.id} | {t.date.isoformat()} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(t.to_base)} |"
        )
    rows.append("")
    rows.append(
        f"**To pay (COP): {cents_to_major(result['total_base'])}** · {len(items)} item(s)"
    )
    return "\n".join(rows)
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/mcp/test_temporal.py`:

```python
from datetime import date

from quaestor.mcp.tools import temporal
from quaestor.mcp.tools.temporal import (
    ConfirmPaymentInput,
    CreateRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
)
from quaestor.services import accounts


def _bank(session):
    return accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)


def test_create_recurring_tool(session):
    _bank(session)
    out = temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    assert "Rent" in out and "id=" in out


def test_create_recurring_unknown_account_returns_text(session):
    out = temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Nope", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    assert "not found" in out


def test_list_recurring_tool(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    out = temporal.list_recurring(session, ListRecurringInput())
    assert "Rent" in out


def test_plan_confirm_to_pay_skip_flow(session):
    _bank(session)
    planned_out = temporal.plan_payment(session, PlanPaymentInput(
        payee="Friend", amount=80_000, account="Bancolombia", due_date=date(2026, 6, 20),
    ))
    assert "Friend" in planned_out and "id=" in planned_out

    to_pay_out = temporal.to_pay(session, ToPayInput(since=date(2026, 6, 1), until=date(2026, 6, 30)))
    assert "Friend" in to_pay_out and "To pay (COP)" in to_pay_out

    # extract the planned tx id from the queue
    from quaestor.services import transactions
    tx_id = transactions.list_transactions(session, status="planned")[0].id
    confirmed = temporal.confirm_payment(session, ConfirmPaymentInput(tx_id=tx_id, amount=85_000))
    assert "Confirmed" in confirmed


def test_confirm_non_planned_returns_text(session):
    _bank(session)
    from quaestor.services import transactions
    tx = transactions.record_expense(session, 1, 1000, "COP", date(2026, 6, 1), "x")
    out = temporal.confirm_payment(session, ConfirmPaymentInput(tx_id=tx.id))
    assert "Can't do that" in out


def test_skip_payment_tool(session):
    _bank(session)
    temporal.plan_payment(session, PlanPaymentInput(
        payee="Friend", amount=80_000, account="Bancolombia", due_date=date(2026, 6, 20),
    ))
    from quaestor.services import transactions
    tx_id = transactions.list_transactions(session, status="planned")[0].id
    out = temporal.skip_payment(session, SkipPaymentInput(tx_id=tx_id))
    assert "Skipped" in out


def test_skip_recurring_tool(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Water", payee="Utility", type="expense", mode="manual",
        amount=50_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 5),
    ))
    from quaestor.services import recurring
    item_id = recurring.list_recurring(session)[0].id
    out = temporal.skip_recurring(session, SkipRecurringInput(
        recurring_id=item_id, due_date=date(2026, 1, 5),
    ))
    assert "Skipped" in out


def test_register_temporal_tools_exposes_all_seven():
    import asyncio
    from mcp.server.fastmcp import FastMCP
    from quaestor.mcp.registry import TEMPORAL_TOOL_NAMES, register_temporal_tools

    mcp = FastMCP("test")
    register_temporal_tools(mcp)
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == set(TEMPORAL_TOOL_NAMES)
    assert len(TEMPORAL_TOOL_NAMES) == 7
```

Note: `test_temporal.py` relies on `tests/mcp/conftest.py`'s `session` fixture. `record_expense(session, 1, ...)` uses account id 1 (the bank created by `_bank`).

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/mcp/test_temporal.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.mcp.tools.temporal'`.

- [ ] **Step 4: Implement `temporal.py`**

Create `backend/src/quaestor/mcp/tools/temporal.py`:

```python
"""MCP temporal tools (P3): recurring items + the to-pay confirmation queue.

Mirrors core.py: parse input, resolve names, call ONE service, format output.
materialize_due/close_month are NOT exposed (the scheduler runs them, ADR-017/020).
"""
from __future__ import annotations

from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.models import RecurringMode, TxType
from ...services import planned, recurring
from .. import format
from .core import _as_text, _resolve_account, _resolve_category


# ----- input models -----


class CreateRecurringInput(BaseModel):
    name: str = Field(description="Display name, e.g. 'Rent'")
    payee: str = Field(description="Payee/source, e.g. 'Landlord'")
    type: Literal["expense", "income"] = Field(description="expense or income")
    mode: Literal["auto", "manual"] = Field(
        description="auto posts on each due date; manual goes to to-pay for confirmation"
    )
    amount: int = Field(gt=0, description="Default amount in cents, original currency")
    account: str = Field(description="Account name")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    category: str | None = Field(default=None, description="Category name (optional)")
    interval_unit: Literal["day", "week", "month", "year"] = Field(
        description="Interval unit; combine with interval_count (e.g. 2 week = biweekly)"
    )
    interval_count: int = Field(default=1, ge=1, description="How many units per interval")
    start_date: Date = Field(description="Anchor date YYYY-MM-DD")
    end_date: Date | None = Field(default=None, description="Optional last date YYYY-MM-DD")


class ListRecurringInput(BaseModel):
    active: bool | None = Field(default=None, description="Filter by active state")


class PlanPaymentInput(BaseModel):
    payee: str = Field(description="Who you owe, e.g. 'Friend'")
    amount: int = Field(gt=0, description="Amount in cents, original currency")
    account: str = Field(description="Account the payment will come from")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    category: str | None = Field(default=None, description="Category name (optional)")
    due_date: Date = Field(description="When it is due, YYYY-MM-DD")
    notes: str | None = Field(default=None, description="Free-form notes (optional)")


class ConfirmPaymentInput(BaseModel):
    tx_id: int = Field(description="The planned transaction id (from to_pay)")
    amount: int | None = Field(default=None, gt=0, description="Real amount if it differs")
    date: Date | None = Field(default=None, description="Real date if it differs")


class SkipPaymentInput(BaseModel):
    tx_id: int = Field(description="The planned transaction id to cancel")


class SkipRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id")
    due_date: Date = Field(description="The single occurrence date to skip, YYYY-MM-DD")


class ToPayInput(BaseModel):
    since: Date = Field(description="Window start, YYYY-MM-DD")
    until: Date = Field(description="Window end, YYYY-MM-DD")


# ----- impls -----


@_as_text
def create_recurring(session: Session, inp: CreateRecurringInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    item = recurring.create_recurring(
        session,
        name=inp.name,
        payee=inp.payee,
        type=TxType(inp.type),
        mode=RecurringMode(inp.mode),
        amount=inp.amount,
        currency=inp.currency,
        category_id=category.id if category else None,
        account_id=account.id,
        interval_unit=inp.interval_unit,
        interval_count=inp.interval_count,
        start_date=inp.start_date,
        end_date=inp.end_date,
    )
    return format.recurring_created(item)


@_as_text
def list_recurring(session: Session, inp: ListRecurringInput) -> str:
    return format.recurring_list(recurring.list_recurring(session, active=inp.active))


@_as_text
def plan_payment(session: Session, inp: PlanPaymentInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    tx = planned.plan_payment(
        session,
        payee=inp.payee,
        amount=inp.amount,
        currency=inp.currency,
        due_date=inp.due_date,
        account_id=account.id,
        category_id=category.id if category else None,
        notes=inp.notes,
    )
    return format.payment_planned(tx)


@_as_text
def confirm_payment(session: Session, inp: ConfirmPaymentInput) -> str:
    tx = planned.confirm_payment(session, inp.tx_id, amount=inp.amount, date=inp.date)
    return format.payment_confirmed(tx)


@_as_text
def skip_payment(session: Session, inp: SkipPaymentInput) -> str:
    tx = planned.skip_payment(session, inp.tx_id)
    return format.payment_skipped(tx)


@_as_text
def skip_recurring(session: Session, inp: SkipRecurringInput) -> str:
    occ = recurring.skip_recurring(session, inp.recurring_id, inp.due_date)
    return format.recurring_skipped(occ)


@_as_text
def to_pay(session: Session, inp: ToPayInput) -> str:
    return format.to_pay_table(planned.to_pay(session, inp.since, inp.until))
```

- [ ] **Step 5: Wire the tools into the registry**

In `backend/src/quaestor/mcp/registry.py`, add the import block and the registration function. Add after the existing core imports:

```python
from .tools import temporal
from .tools.temporal import (
    ConfirmPaymentInput,
    CreateRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
)

TEMPORAL_TOOL_NAMES = (
    "create_recurring",
    "list_recurring",
    "plan_payment",
    "confirm_payment",
    "skip_payment",
    "skip_recurring",
    "to_pay",
)


def register_temporal_tools(mcp) -> None:
    """Register the 7 P3 temporal tools on the given FastMCP instance."""

    @mcp.tool(name="create_recurring", description="Create a recurring expense/income (every-N interval).")
    def create_recurring(item: CreateRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.create_recurring(session, item)

    @mcp.tool(name="list_recurring", description="List recurring items (optionally filter by active).")
    def list_recurring(filters: ListRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.list_recurring(session, filters)

    @mcp.tool(name="plan_payment", description="Plan a one-off future payment (lands in to-pay).")
    def plan_payment(payment: PlanPaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.plan_payment(session, payment)

    @mcp.tool(name="confirm_payment", description="Confirm a planned payment (planned -> posted).")
    def confirm_payment(confirmation: ConfirmPaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.confirm_payment(session, confirmation)

    @mcp.tool(name="skip_payment", description="Skip/cancel a planned payment.")
    def skip_payment(skip: SkipPaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.skip_payment(session, skip)

    @mcp.tool(name="skip_recurring", description="Skip a single occurrence of a recurring item.")
    def skip_recurring(skip: SkipRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.skip_recurring(session, skip)

    @mcp.tool(name="to_pay", description="What's still to pay in a date window (the confirmation queue).")
    def to_pay(window: ToPayInput) -> str:
        with Session(db.engine) as session:
            return temporal.to_pay(session, window)
```

- [ ] **Step 6: Call `register_temporal_tools` in the server**

In `backend/src/quaestor/mcp/server.py`, update the import and `build_mcp`:

```python
from .registry import register_core_tools, register_temporal_tools
```

```python
def build_mcp() -> FastMCP:
    """A FastMCP instance with the P2 core tools and P3 temporal tools registered."""
    mcp = FastMCP("Quaestor", json_response=True)
    register_core_tools(mcp)
    register_temporal_tools(mcp)
    return mcp
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/mcp/test_temporal.py -v`
Expected: PASS (9 tests).

- [ ] **Step 8: Run the whole MCP suite to confirm no regression**

Run: `uv run pytest tests/mcp -v`
Expected: PASS (core + temporal).

- [ ] **Step 9: Commit**

```bash
git add backend/src/quaestor/mcp/tools/temporal.py backend/src/quaestor/mcp/format.py backend/src/quaestor/mcp/registry.py backend/src/quaestor/mcp/server.py backend/tests/mcp/test_temporal.py
git commit -m "feat(mcp): add 7 temporal tools (recurring, plan/confirm/skip, to_pay)"
```

---

### Task 13: REST — `/recurring`, `/planned`, `/rollover` routers (P1 surface)

Thin adapters over the services, mirroring `routers/transactions.py`. `IllegalTransition` already maps to 409 (Task 3). `/rollover` is an internal admin/debug endpoint (the scheduler is the real driver); it stays protected like the rest.

**Files:**
- Modify: `backend/src/quaestor/api/schemas.py`
- Create: `backend/src/quaestor/api/routers/recurring.py`, `planned.py`, `rollover.py`
- Modify: `backend/src/quaestor/api/__init__.py`
- Test: `backend/tests/api/test_recurring.py`, `backend/tests/api/test_planned.py`

**Interfaces:**
- Consumes: `services.recurring`, `services.planned`, `services.rollover`, existing `TransactionOut`, `deps.get_session`.
- Produces:
  - Schemas: `RecurringCreate`, `RecurringOut`, `OccurrenceOut`, `SkipRecurringIn`, `PlanPaymentIn`, `ConfirmPaymentIn`, `ToPayOut`, `CloseMonthIn`.
  - Routers `recurring.router`, `planned.router`, `rollover.router`.

- [ ] **Step 1: Add the schemas**

Append to `backend/src/quaestor/api/schemas.py` (note `TransactionOut` is already defined above in the file):

```python
from ..domain.models import IntervalUnit, OccurrenceStatus, RecurringMode  # add to existing model imports


class RecurringCreate(BaseModel):
    name: str
    payee: str = ""
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str = "COP"
    category_id: int | None = None
    account_id: int
    interval_unit: IntervalUnit
    interval_count: int = 1
    start_date: Date
    end_date: Date | None = None


class RecurringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    payee: str
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str
    category_id: int | None
    account_id: int
    interval_unit: IntervalUnit
    interval_count: int
    start_date: Date
    end_date: Date | None
    active: bool


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recurring_id: int
    due_date: Date
    status: OccurrenceStatus
    transaction_id: int | None


class SkipRecurringIn(BaseModel):
    due_date: Date


class PlanPaymentIn(BaseModel):
    payee: str
    amount: int
    currency: str = "COP"
    due_date: Date
    account_id: int
    category_id: int | None = None
    notes: str | None = None


class ConfirmPaymentIn(BaseModel):
    amount: int | None = None
    date: Date | None = None


class ToPayOut(BaseModel):
    items: list[TransactionOut]
    total_base: int


class CloseMonthIn(BaseModel):
    period: str  # "YYYY-MM"
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/api/test_recurring.py`:

```python
from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=1_000_000)
        return acc.id


def test_create_and_list_recurring(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "Landlord", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["active"] is True

    r2 = client.get("/api/recurring", headers=auth)
    assert r2.status_code == 200
    assert [i["name"] for i in r2.json()] == ["Rent"]


def test_create_recurring_transfer_type_is_422(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "X", "payee": "Y", "type": "transfer", "mode": "auto",
        "amount": 1000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422


def test_skip_recurring_occurrence(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Water", "payee": "Utility", "type": "expense", "mode": "manual",
        "amount": 50_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-05",
    }
    rec_id = client.post("/api/recurring", json=body, headers=auth).json()["id"]
    r = client.post(f"/api/recurring/{rec_id}/skip", json={"due_date": "2026-01-05"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "skipped"


def test_recurring_requires_auth(client):
    assert client.get("/api/recurring").status_code == 401
```

Create `backend/tests/api/test_planned.py`:

```python
from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine, balance=1_000_000):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=balance)
        return acc.id


def test_plan_to_pay_confirm_flow(client, engine, auth):
    acc_id = _seed_account(engine)
    plan = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth)
    assert plan.status_code == 201, plan.text
    tx_id = plan.json()["id"]
    assert plan.json()["status"] == "planned"

    queue = client.get("/api/planned/to-pay", params={"since": "2026-06-01", "until": "2026-06-30"}, headers=auth)
    assert queue.status_code == 200
    assert queue.json()["total_base"] == 80_000
    assert [i["id"] for i in queue.json()["items"]] == [tx_id]

    confirm = client.post(f"/api/planned/{tx_id}/confirm", json={"amount": 85_000}, headers=auth)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "posted" and confirm.json()["amount"] == 85_000


def test_confirm_non_planned_is_409(client, engine, auth):
    acc_id = _seed_account(engine)
    # post a normal expense, then try to confirm it
    plan = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth)
    tx_id = plan.json()["id"]
    client.post(f"/api/planned/{tx_id}/confirm", json={}, headers=auth)  # now posted
    again = client.post(f"/api/planned/{tx_id}/confirm", json={}, headers=auth)
    assert again.status_code == 409


def test_skip_planned_payment(client, engine, auth):
    acc_id = _seed_account(engine)
    tx_id = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth).json()["id"]
    r = client.post(f"/api/planned/{tx_id}/skip", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "skipped"


def test_rollover_admin_endpoint_runs(client, auth):
    r = client.post("/api/rollover", json={"period": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["period"] == "2026-06"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/api/test_recurring.py tests/api/test_planned.py -v`
Expected: FAIL (404s — the routers aren't mounted yet).

- [ ] **Step 4: Implement the routers**

Create `backend/src/quaestor/api/routers/recurring.py`:

```python
"""Recurring REST router — thin adapter over services.recurring."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import recurring
from ..deps import get_session
from ..schemas import OccurrenceOut, RecurringCreate, RecurringOut, SkipRecurringIn

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=list[RecurringOut])
def list_recurring(active: bool | None = None, session: Session = Depends(get_session)):
    return recurring.list_recurring(session, active=active)


@router.post("", response_model=RecurringOut, status_code=201)
def create_recurring(body: RecurringCreate, session: Session = Depends(get_session)):
    return recurring.create_recurring(
        session,
        name=body.name,
        payee=body.payee,
        type=body.type,
        mode=body.mode,
        amount=body.amount,
        currency=body.currency,
        category_id=body.category_id,
        account_id=body.account_id,
        interval_unit=body.interval_unit,
        interval_count=body.interval_count,
        start_date=body.start_date,
        end_date=body.end_date,
    )


@router.post("/{recurring_id}/skip", response_model=OccurrenceOut)
def skip_recurring(
    recurring_id: int, body: SkipRecurringIn, session: Session = Depends(get_session)
):
    return recurring.skip_recurring(session, recurring_id, body.due_date)
```

Create `backend/src/quaestor/api/routers/planned.py`:

```python
"""Planned-payments REST router — thin adapter over services.planned."""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import planned
from ..deps import get_session
from ..schemas import ConfirmPaymentIn, PlanPaymentIn, ToPayOut, TransactionOut

router = APIRouter(prefix="/planned", tags=["planned"])


@router.get("/to-pay", response_model=ToPayOut)
def to_pay(since: Date, until: Date, session: Session = Depends(get_session)):
    return planned.to_pay(session, since, until)


@router.post("", response_model=TransactionOut, status_code=201)
def plan_payment(body: PlanPaymentIn, session: Session = Depends(get_session)):
    return planned.plan_payment(
        session,
        payee=body.payee,
        amount=body.amount,
        currency=body.currency,
        due_date=body.due_date,
        account_id=body.account_id,
        category_id=body.category_id,
        notes=body.notes,
    )


@router.post("/{tx_id}/confirm", response_model=TransactionOut)
def confirm_payment(
    tx_id: int, body: ConfirmPaymentIn, session: Session = Depends(get_session)
):
    return planned.confirm_payment(session, tx_id, amount=body.amount, date=body.date)


@router.post("/{tx_id}/skip", response_model=TransactionOut)
def skip_payment(tx_id: int, session: Session = Depends(get_session)):
    return planned.skip_payment(session, tx_id)
```

Create `backend/src/quaestor/api/routers/rollover.py`:

```python
"""Rollover REST router — internal admin/debug trigger for close_month.

The scheduler (P7) is the real driver (ADR-017); this endpoint exists for
manual/debug closes. It stays behind require_auth like the other routers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import rollover
from ..deps import get_session
from ..schemas import CloseMonthIn

router = APIRouter(prefix="/rollover", tags=["rollover"])


@router.post("")
def close_month(body: CloseMonthIn, session: Session = Depends(get_session)):
    rollover.close_month(session, body.period)
    return {"ok": True, "period": body.period}
```

- [ ] **Step 5: Mount the routers**

In `backend/src/quaestor/api/__init__.py`, inside `_include_routers`, add the imports and includes:

```python
    from .routers import (
        accounts,
        categories,
        category_groups,
        fx,
        planned,
        recurring,
        rollover,
        settings,
        tags,
        transactions,
    )
```

```python
    app.include_router(transactions.router, prefix="/api", dependencies=protected)
    app.include_router(recurring.router, prefix="/api", dependencies=protected)
    app.include_router(planned.router, prefix="/api", dependencies=protected)
    app.include_router(rollover.router, prefix="/api", dependencies=protected)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_recurring.py tests/api/test_planned.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/api/schemas.py backend/src/quaestor/api/routers/recurring.py backend/src/quaestor/api/routers/planned.py backend/src/quaestor/api/routers/rollover.py backend/src/quaestor/api/__init__.py backend/tests/api/test_recurring.py backend/tests/api/test_planned.py
git commit -m "feat(api): add /recurring, /planned, /rollover routers"
```

---

### Task 14: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire backend test suite**

Run: `uv run pytest -q`
Expected: PASS — all P0/P1/P2 tests plus every P3 test added in Tasks 1–13. No failures, no errors.

- [ ] **Step 2: Confirm the unique constraint is live**

Run: `uv run pytest tests/domain/test_recurring_models.py::test_unique_recurring_due_date -v`
Expected: PASS (the `(recurring_id, due_date)` `IntegrityError` is raised on the duplicate).

- [ ] **Step 3: Recreate the dev database (clean start, ADR-009)**

The persisted `backend/quaestor.db` predates the new `Transaction.recurring_id` column. `create_all` does not alter existing tables, so delete and let `init_db` rebuild it:

```bash
rm -f backend/quaestor.db
uv run python -c "from quaestor.db import init_db; init_db()"
```

Expected: a fresh `backend/quaestor.db` with all tables (run from `backend/`, or set `cwd` so the relative SQLite path resolves).

- [ ] **Step 4: Final commit (if Step 3 produced tracked changes)**

If `backend/quaestor.db` is tracked (check `git status`), do not commit the binary DB — confirm it is gitignored. Otherwise nothing to commit; P3 is complete.

---
