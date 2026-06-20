# P4 Budgets + Goals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the hybrid budget (per-category envelopes with rollover + a global safe-to-spend) and fixed-amount savings goals (defined + open-ended) as pure-domain math plus DB-backed services, wired into P3's rollover/post-confirm seams.

**Architecture:** Pure computation lives in `domain/rules.py` (envelope/safe-to-spend/goal math, no DB). Output DTOs are frozen dataclasses in `domain/dtos.py`. Services in `services/budgets.py` and `services/goals.py` query the DB, call the pure functions, and own their transactions. Goal contributions are internal transfers triggered by confirmation: `propose_goal_contributions` (P3 rollover hook) creates `planned` transfers carrying `goal_id`; `record_confirmed_contribution` (P3 post-confirm hook) records the `GoalContribution` when P3's `confirm_payment` materializes that transfer. `services/bootstrap.py` registers both hooks, called from `db.init_db`.

**Tech Stack:** Python 3.12, SQLModel/SQLAlchemy, SQLite (in-memory for tests), pytest.

## Global Constraints

- **English only** in all code, comments, identifiers (ADR-0001).
- **Money is integer COP cents.** Budgets and goal contributions are base currency (COP); no FX handling in P4 logic (`to_base` already frozen on every tx).
- **No migration framework exists.** P0 builds the schema via `SQLModel.metadata.create_all` in `db.init_db`. "Migration" in this plan means **adding the SQLModel models** (`Budget`, `Goal`, `GoalContribution`) and the **`Transaction.goal_id` column**; `create_all` materializes them for fresh and in-memory DBs. A manual `ALTER TABLE` for an existing persistent DB is out of scope (no Alembic to hang it on).
- **Pure rules touch no DB.** Functions in `domain/rules.py` receive already-queried primitives and return DTOs/ints.
- **Services own transactions.** A service either commits its own unit of work or runs inside a caller's transaction. **Hooks write directly to the session and never call committing services** (P3 convention: a later hook failure must roll back the whole close / confirm).
- **Typed domain errors** from `domain/errors.py`: `ValidationError`, `NotFound`. P1/P2 map them; P4 only raises them.
- **Public service signatures** are consumed by P1/P2/P5 — keep them exactly as in "Public interface". The one benign addition is an optional `today: date | None = None` keyword on `goals_progress` (defaults to `date.today()`) so date-dependent logic is testable; P1/P2 omit it.

---

## File Structure

- `backend/src/quaestor/domain/models.py` (modify) — add `Budget`, `Goal`, `GoalContribution`, enums `GoalStatus`, `ContributionSource`; add `goal_id` column to `Transaction`.
- `backend/src/quaestor/domain/dtos.py` (create) — frozen dataclasses `BudgetStatus`, `CommittedItem`, `SafeToSpend`, `GoalProgress`.
- `backend/src/quaestor/domain/rules.py` (modify) — add `month_bounds`, `prev_year_month`, `envelope_status_calc`, `safe_to_spend_calc`, `goal_progress_calc`.
- `backend/src/quaestor/services/budgets.py` (create) — `set_budget`, `budget_status`, `safe_to_spend` + private query helpers.
- `backend/src/quaestor/services/goals.py` (create) — `create_goal`, `goal_contribution`, `goals_progress`, `propose_goal_contributions`, `record_confirmed_contribution` + private helpers.
- `backend/src/quaestor/services/bootstrap.py` (create) — `register_goal_hooks` (idempotent).
- `backend/src/quaestor/db.py` (modify) — call `register_goal_hooks()` from `init_db`.
- Tests: `tests/domain/test_budget_goal_models.py`, `tests/domain/test_budget_rules.py`, `tests/domain/test_safe_to_spend_rules.py`, `tests/domain/test_goal_rules.py`, `tests/services/test_budgets.py`, `tests/services/test_goals.py`, `tests/services/test_goal_hooks.py`.

All commands run from `backend/` unless noted.

---

### Task 1: Domain models — Budget, Goal, GoalContribution, Transaction.goal_id

**Files:**
- Modify: `backend/src/quaestor/domain/models.py`
- Test: `backend/tests/domain/test_budget_goal_models.py`

**Interfaces:**
- Consumes: existing `Account`, `Category`, `Transaction` tables and `SQLModel` base.
- Produces:
  - `GoalStatus(str, Enum)`: `active`, `reached`, `paused`.
  - `ContributionSource(str, Enum)`: `confirmed`, `manual`.
  - `Budget(id, category_id: int FK category.id, year_month: str, amount_assigned: int)` — unique `(category_id, year_month)`.
  - `Goal(id, name: str, target_amount: int|None, deadline: date|None, monthly_amount: int, savings_account_id: int FK account.id, status: GoalStatus)`.
  - `GoalContribution(id, goal_id: int FK goal.id, date: date, amount: int, source: ContributionSource, transaction_id: int|None FK transaction.id)` — index `(goal_id, date)`.
  - `Transaction.goal_id: int|None FK goal.id` (default None).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domain/test_budget_goal_models.py`:

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    Account,
    AccountType,
    Budget,
    ContributionSource,
    Goal,
    GoalContribution,
    GoalStatus,
    Transaction,
    TxType,
)


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s


def test_budget_unique_per_category_and_month(session):
    session.add(Budget(category_id=1, year_month="2026-06", amount_assigned=100_000))
    session.commit()
    session.add(Budget(category_id=1, year_month="2026-06", amount_assigned=50_000))
    with pytest.raises(IntegrityError):
        session.commit()


def test_goal_defaults_to_active_and_allows_nullable_target(session):
    acc = Account(name="Savings", type=AccountType.savings, currency="COP")
    session.add(acc)
    session.commit()
    goal = Goal(name="Trip", monthly_amount=200_000, savings_account_id=acc.id)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    assert goal.status == GoalStatus.active
    assert goal.target_amount is None and goal.deadline is None


def test_goal_contribution_links_goal_and_transaction(session):
    acc = Account(name="Savings", type=AccountType.savings, currency="COP")
    session.add(acc)
    session.commit()
    goal = Goal(name="Trip", monthly_amount=200_000, savings_account_id=acc.id)
    session.add(goal)
    session.commit()
    c = GoalContribution(
        goal_id=goal.id, date=date(2026, 6, 30), amount=200_000,
        source=ContributionSource.confirmed, transaction_id=None,
    )
    session.add(c)
    session.commit()
    rows = session.exec(select(GoalContribution).where(GoalContribution.goal_id == goal.id)).all()
    assert len(rows) == 1 and rows[0].source == ContributionSource.confirmed


def test_transaction_has_goal_id_column(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    session.add(acc)
    session.commit()
    goal = Goal(name="Trip", monthly_amount=200_000, savings_account_id=acc.id)
    session.add(goal)
    session.commit()
    from decimal import Decimal
    tx = Transaction(
        date=date(2026, 6, 30), type=TxType.transfer, amount=200_000, currency="COP",
        fx_rate=Decimal("1"), to_base=200_000, account_id=acc.id, goal_id=goal.id,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    assert tx.goal_id == goal.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/domain/test_budget_goal_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'Budget'` (and friends).

- [ ] **Step 3: Add the models**

In `backend/src/quaestor/domain/models.py`, change the SQLAlchemy import line and add the new enums/tables. Update the existing import:

```python
from sqlalchemy import Column, Index, Numeric, UniqueConstraint
```

Add `goal_id` to the existing `Transaction` class (place it right after the `recurring_id` field):

```python
    goal_id: Annotated[Optional[int], Field(default=None, foreign_key="goal.id")] = None
```

Append these new enums and tables at the end of the file:

```python
class GoalStatus(str, Enum):
    active = "active"
    reached = "reached"
    paused = "paused"


class ContributionSource(str, Enum):
    confirmed = "confirmed"  # proposed by rollover, confirmed in To-pay
    manual = "manual"  # standalone contribution


class Budget(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("category_id", "year_month", name="uq_budget_category_month"),
    )
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    category_id: Annotated[int, Field(foreign_key="category.id")]
    year_month: str  # "YYYY-MM"
    amount_assigned: int = 0  # COP cents, >= 0


class Goal(SQLModel, table=True):
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    target_amount: Optional[int] = None  # COP cents; None => open-ended
    deadline: Optional[date] = None  # None => open-ended
    monthly_amount: int  # COP cents, > 0, fixed
    savings_account_id: Annotated[int, Field(foreign_key="account.id")]
    status: GoalStatus = GoalStatus.active


class GoalContribution(SQLModel, table=True):
    __tablename__ = "goal_contribution"
    __table_args__ = (
        Index("ix_goal_contribution_goal_date", "goal_id", "date"),
    )
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    goal_id: Annotated[int, Field(foreign_key="goal.id")]
    date: date
    amount: int  # COP cents
    source: ContributionSource
    transaction_id: Annotated[Optional[int], Field(default=None, foreign_key="transaction.id")] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/domain/test_budget_goal_models.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/models.py backend/tests/domain/test_budget_goal_models.py
git commit -m "feat(domain): add Budget, Goal, GoalContribution models + Transaction.goal_id"
```

---

### Task 2: Pure rules — period helpers + envelope_status_calc (BudgetStatus DTO)

**Files:**
- Create: `backend/src/quaestor/domain/dtos.py`
- Modify: `backend/src/quaestor/domain/rules.py`
- Test: `backend/tests/domain/test_budget_rules.py`

**Interfaces:**
- Produces:
  - `BudgetStatus` dataclass: `category_id, year_month, assigned, rollover_in, spent, available, pct_used, status` (status is `"over"` | `"under"`).
  - `month_bounds(year_month: str) -> tuple[date, date]` — first and last calendar day of the month.
  - `prev_year_month(year_month: str) -> str` — previous `"YYYY-MM"`.
  - `envelope_status_calc(category_id: int, year_month: str, assigned: int, rollover_in: int, spent: int) -> BudgetStatus` — `available = rollover_in + assigned - spent`; `pct_used = round(spent / (rollover_in + assigned) * 100)` (0 if denominator 0); `status = "over"` iff `spent > rollover_in + assigned`.

- [ ] **Step 1: Write the failing test**

Create `backend/src/quaestor/domain/dtos.py`:

```python
"""Output DTOs returned by budget/goal services (not DB models)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BudgetStatus:
    category_id: int
    year_month: str
    assigned: int
    rollover_in: int
    spent: int
    available: int
    pct_used: int
    status: str  # "over" | "under"


@dataclass(frozen=True)
class CommittedItem:
    kind: str  # "recurring" | "planned"
    name: str
    date: date
    amount: int  # COP cents


@dataclass(frozen=True)
class SafeToSpend:
    year_month: str
    income_forecast: int
    committed: int
    assigned_envelopes: int
    free: int
    committed_breakdown: list  # list[CommittedItem]


@dataclass(frozen=True)
class GoalProgress:
    goal_id: int
    name: str
    type: str  # "defined" | "open-ended"
    monthly_amount: int
    saved: int
    target_amount: int | None = None
    deadline: date | None = None
    monthly_required: int | None = None
    on_track: bool | None = None
    eta: date | None = None
    remaining: int | None = None
```

Create `backend/tests/domain/test_budget_rules.py`:

```python
from datetime import date

from quaestor.domain.rules import (
    envelope_status_calc,
    month_bounds,
    prev_year_month,
)


def test_month_bounds_handles_february_and_year():
    assert month_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_bounds("2026-12") == (date(2026, 12, 1), date(2026, 12, 31))


def test_prev_year_month_wraps_january():
    assert prev_year_month("2026-06") == "2026-05"
    assert prev_year_month("2026-01") == "2025-12"


def test_envelope_available_and_status_under():
    s = envelope_status_calc("1", "2026-06", assigned=100_000, rollover_in=20_000, spent=30_000)
    assert s.available == 90_000
    assert s.pct_used == 25  # round(30000 / 120000 * 100)
    assert s.status == "under"


def test_envelope_over_when_spent_exceeds_assigned_plus_rollover():
    s = envelope_status_calc("1", "2026-06", assigned=50_000, rollover_in=0, spent=60_000)
    assert s.available == -10_000
    assert s.status == "over"


def test_envelope_zero_denominator_does_not_divide():
    s = envelope_status_calc("1", "2026-06", assigned=0, rollover_in=0, spent=0)
    assert s.pct_used == 0
    assert s.status == "under"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/domain/test_budget_rules.py -q`
Expected: FAIL — `ImportError: cannot import name 'envelope_status_calc'`.

- [ ] **Step 3: Add the pure functions**

In `backend/src/quaestor/domain/rules.py`, add an import for the DTO near the top (after the existing `from .models import ...` line):

```python
from .dtos import BudgetStatus
```

Append at the end of `rules.py`:

```python
def month_bounds(year_month: str) -> tuple[date, date]:
    """First and last calendar day of a "YYYY-MM" string."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    return date(year, month, 1), date(year, month, _last_day_of_month(year, month))


def prev_year_month(year_month: str) -> str:
    """The "YYYY-MM" of the previous calendar month."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def envelope_status_calc(
    category_id: int, year_month: str, assigned: int, rollover_in: int, spent: int
) -> BudgetStatus:
    """Envelope math: available, pct_used, over/under (ADR-003/005). Pure."""
    denom = rollover_in + assigned
    available = denom - spent
    pct_used = round(spent / denom * 100) if denom > 0 else 0
    status = "over" if spent > denom else "under"
    return BudgetStatus(
        category_id=category_id, year_month=year_month, assigned=assigned,
        rollover_in=rollover_in, spent=spent, available=available,
        pct_used=pct_used, status=status,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/domain/test_budget_rules.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/dtos.py backend/src/quaestor/domain/rules.py backend/tests/domain/test_budget_rules.py
git commit -m "feat(domain): add period helpers, envelope_status_calc, output DTOs"
```

---

### Task 3: Pure rules — safe_to_spend_calc

**Files:**
- Modify: `backend/src/quaestor/domain/rules.py`
- Test: `backend/tests/domain/test_safe_to_spend_rules.py`

**Interfaces:**
- Produces: `safe_to_spend_calc(income_forecast: int, committed: int, assigned_envelopes: int, unbudgeted_spending: int, overspend: int) -> int` — returns `free = income_forecast - committed - assigned_envelopes - unbudgeted_spending - overspend`. Pure; the cascade inputs are computed by the service (Task 7).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domain/test_safe_to_spend_rules.py`:

```python
from quaestor.domain.rules import safe_to_spend_calc


def test_cascade_subtracts_every_term():
    free = safe_to_spend_calc(
        income_forecast=1_000_000,
        committed=300_000,
        assigned_envelopes=200_000,
        unbudgeted_spending=100_000,
        overspend=50_000,
    )
    assert free == 350_000


def test_cascade_can_go_negative():
    free = safe_to_spend_calc(
        income_forecast=100_000, committed=200_000,
        assigned_envelopes=0, unbudgeted_spending=0, overspend=0,
    )
    assert free == -100_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/domain/test_safe_to_spend_rules.py -q`
Expected: FAIL — `ImportError: cannot import name 'safe_to_spend_calc'`.

- [ ] **Step 3: Add the pure function**

Append to `backend/src/quaestor/domain/rules.py`:

```python
def safe_to_spend_calc(
    income_forecast: int,
    committed: int,
    assigned_envelopes: int,
    unbudgeted_spending: int,
    overspend: int,
) -> int:
    """Safe-to-spend headline cascade (ADR-003/005/014/016). Pure.

    free = income_forecast - committed - assigned_envelopes
           - unbudgeted_spending - overspend
    """
    return (
        income_forecast
        - committed
        - assigned_envelopes
        - unbudgeted_spending
        - overspend
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/domain/test_safe_to_spend_rules.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/rules.py backend/tests/domain/test_safe_to_spend_rules.py
git commit -m "feat(domain): add safe_to_spend_calc cascade"
```

---

### Task 4: Pure rules — goal_progress_calc

**Files:**
- Modify: `backend/src/quaestor/domain/rules.py`
- Test: `backend/tests/domain/test_goal_rules.py`

**Interfaces:**
- Produces: `goal_progress_calc(goal_id: int, name: str, monthly_amount: int, saved: int, target_amount: int | None, deadline: date | None, today: date) -> GoalProgress`.
  - **open-ended** (no target, no deadline): `type="open-ended"`, only `saved`; `monthly_required/on_track/eta/remaining/target_amount/deadline` are None.
  - **defined**: `remaining = max(target_amount - saved, 0)`; `months_left = max(1, (deadline.y*12+deadline.m) - (today.y*12+today.m))`; `monthly_required = ceil(remaining / months_left)`; `on_track = monthly_amount >= monthly_required`; `eta = today` if `remaining == 0` else `_add_months(today, ceil(remaining / monthly_amount))`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domain/test_goal_rules.py`:

```python
from datetime import date

from quaestor.domain.rules import goal_progress_calc

TODAY = date(2026, 6, 19)


def test_open_ended_reports_only_saved():
    g = goal_progress_calc(1, "Buffer", monthly_amount=100_000, saved=450_000,
                           target_amount=None, deadline=None, today=TODAY)
    assert g.type == "open-ended"
    assert g.saved == 450_000
    assert g.monthly_required is None and g.on_track is None and g.eta is None
    assert g.remaining is None


def test_defined_on_track_with_eta():
    g = goal_progress_calc(1, "Trip", monthly_amount=200_000, saved=200_000,
                           target_amount=1_200_000, deadline=date(2026, 12, 1), today=TODAY)
    assert g.type == "defined"
    assert g.remaining == 1_000_000
    assert g.monthly_required == 166_667  # ceil(1_000_000 / 6)
    assert g.on_track is True
    assert g.eta == date(2026, 11, 19)  # today + ceil(1_000_000/200_000)=5 months


def test_defined_behind_when_monthly_amount_too_small():
    g = goal_progress_calc(1, "Trip", monthly_amount=100_000, saved=200_000,
                           target_amount=1_200_000, deadline=date(2026, 12, 1), today=TODAY)
    assert g.on_track is False
    assert g.eta == date(2027, 4, 19)  # today + ceil(1_000_000/100_000)=10 months


def test_defined_past_deadline_clamps_months_left_to_one():
    g = goal_progress_calc(1, "Trip", monthly_amount=100_000, saved=200_000,
                           target_amount=1_200_000, deadline=date(2026, 1, 1), today=TODAY)
    assert g.monthly_required == 1_000_000  # remaining / 1


def test_defined_reached_when_saved_meets_target():
    g = goal_progress_calc(1, "Trip", monthly_amount=200_000, saved=1_200_000,
                           target_amount=1_200_000, deadline=date(2026, 12, 1), today=TODAY)
    assert g.remaining == 0
    assert g.monthly_required == 0
    assert g.on_track is True
    assert g.eta == TODAY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/domain/test_goal_rules.py -q`
Expected: FAIL — `ImportError: cannot import name 'goal_progress_calc'`.

- [ ] **Step 3: Add the pure function**

In `backend/src/quaestor/domain/rules.py`, extend the DTO import:

```python
from .dtos import BudgetStatus, GoalProgress
```

Append to `rules.py`:

```python
def goal_progress_calc(
    goal_id: int,
    name: str,
    monthly_amount: int,
    saved: int,
    target_amount: int | None,
    deadline: date | None,
    today: date,
) -> GoalProgress:
    """Goal status math (fixed monthly amount). Pure.

    Defined iff both target_amount and deadline are set; open-ended iff neither
    (the only-one case is rejected upstream in create_goal).
    """
    if target_amount is None or deadline is None:
        return GoalProgress(
            goal_id=goal_id, name=name, type="open-ended",
            monthly_amount=monthly_amount, saved=saved,
        )
    remaining = max(target_amount - saved, 0)
    months_left = (deadline.year * 12 + deadline.month) - (today.year * 12 + today.month)
    if months_left < 1:
        months_left = 1
    monthly_required = -(-remaining // months_left)  # ceil division
    on_track = monthly_amount >= monthly_required
    if remaining == 0:
        eta = today
    else:
        eta = _add_months(today, -(-remaining // monthly_amount))
    return GoalProgress(
        goal_id=goal_id, name=name, type="defined", monthly_amount=monthly_amount,
        saved=saved, target_amount=target_amount, deadline=deadline,
        monthly_required=monthly_required, on_track=on_track, eta=eta, remaining=remaining,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/domain/test_goal_rules.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/rules.py backend/tests/domain/test_goal_rules.py
git commit -m "feat(domain): add goal_progress_calc (defined + open-ended)"
```

---

### Task 5: Budget service — set_budget (upsert)

**Files:**
- Create: `backend/src/quaestor/services/budgets.py`
- Test: `backend/tests/services/test_budgets.py`

**Interfaces:**
- Consumes: `Budget`, `Category` models; `ValidationError`, `NotFound`.
- Produces: `set_budget(session, category_id: int, year_month: str, amount_assigned: int) -> Budget` — upserts the `(category_id, year_month)` envelope. Raises `ValidationError` on malformed `year_month` or `amount_assigned < 0`; `NotFound` on unknown `category_id`. Also the module-private `_validate_year_month(year_month)` used by later tasks.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_budgets.py`:

```python
from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.services import budgets, categories


def _cat(session, **kwargs):
    return categories.create_category(session, name=kwargs.pop("name", "Food"), **kwargs)


def test_set_budget_creates_envelope(session):
    cat = _cat(session)
    b = budgets.set_budget(session, cat.id, "2026-06", 300_000)
    assert b.id is not None
    assert b.category_id == cat.id and b.year_month == "2026-06"
    assert b.amount_assigned == 300_000


def test_set_budget_upserts_same_category_month(session):
    cat = _cat(session)
    first = budgets.set_budget(session, cat.id, "2026-06", 300_000)
    second = budgets.set_budget(session, cat.id, "2026-06", 450_000)
    assert second.id == first.id
    assert second.amount_assigned == 450_000


def test_set_budget_rejects_negative_amount(session):
    cat = _cat(session)
    with pytest.raises(ValidationError):
        budgets.set_budget(session, cat.id, "2026-06", -1)


def test_set_budget_rejects_malformed_year_month(session):
    cat = _cat(session)
    with pytest.raises(ValidationError):
        budgets.set_budget(session, cat.id, "2026-13", 100_000)
    with pytest.raises(ValidationError):
        budgets.set_budget(session, cat.id, "June", 100_000)


def test_set_budget_unknown_category_raises_not_found(session):
    with pytest.raises(NotFound):
        budgets.set_budget(session, 999, "2026-06", 100_000)
```

The `session` fixture comes from `backend/tests/conftest.py` (already present). Confirm `categories.create_category(session, name=...)` exists; if its signature differs, adapt `_cat` to it (it must return a `Category` with `.id`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_budgets.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'quaestor.services.budgets'`.

- [ ] **Step 3: Create the service**

Create `backend/src/quaestor/services/budgets.py`:

```python
"""Hybrid budget services: envelopes with rollover + global safe-to-spend (ADR-002/003/005)."""
from __future__ import annotations

import re

from sqlmodel import Session, select

from ..domain.dtos import BudgetStatus, CommittedItem, SafeToSpend
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Budget,
    Category,
    RecurringItem,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_base_cents
from ..domain.rules import (
    due_dates,
    envelope_status_calc,
    month_bounds,
    prev_year_month,
    safe_to_spend_calc,
)
from . import transactions as _tx

_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_year_month(year_month: str) -> None:
    if not _YEAR_MONTH_RE.match(year_month):
        raise ValidationError(f"malformed year_month (expected YYYY-MM): {year_month!r}")


def set_budget(
    session: Session, category_id: int, year_month: str, amount_assigned: int
) -> Budget:
    """Upsert a category's envelope for a month.

    Raises:
        ValidationError: malformed year_month or amount_assigned < 0.
        NotFound: the category does not exist.
    """
    _validate_year_month(year_month)
    if amount_assigned < 0:
        raise ValidationError("amount_assigned must be >= 0")
    if session.get(Category, category_id) is None:
        raise NotFound(f"category {category_id} not found")
    budget = session.exec(
        select(Budget).where(
            Budget.category_id == category_id, Budget.year_month == year_month
        )
    ).first()
    if budget is None:
        budget = Budget(
            category_id=category_id, year_month=year_month, amount_assigned=amount_assigned
        )
    else:
        budget.amount_assigned = amount_assigned
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget
```

> Note: the imports include names (`CommittedItem`, `SafeToSpend`, `RecurringItem`, `Transaction`, `TxStatus`, `TxType`, `to_base_cents`, `due_dates`, `envelope_status_calc`, `safe_to_spend_calc`, `_tx`) used by Tasks 6 and 7. They are imported now so later tasks only append functions. Unused-import lint will clear once Tasks 6–7 land; this is intentional to keep the import block stable.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_budgets.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/budgets.py backend/tests/services/test_budgets.py
git commit -m "feat(services): add set_budget (envelope upsert)"
```

---

### Task 6: Budget service — budget_status (envelope with rollover)

**Files:**
- Modify: `backend/src/quaestor/services/budgets.py`
- Test: `backend/tests/services/test_budgets.py` (append)

**Interfaces:**
- Consumes: `set_budget`, `_validate_year_month`, `envelope_status_calc`, `month_bounds`, `prev_year_month` (Tasks 2/5).
- Produces:
  - `budget_status(session, category_id: int, year_month: str) -> BudgetStatus`.
  - private `_spent(session, category_id, year_month) -> int` — Σ `to_base` of `expense`+`posted` in the month/category across **all accounts**; **0** if the category has `exclude_from_budget` or `exclude_from_totals`.
  - private `_assigned(session, category_id, year_month) -> int` — the envelope's `amount_assigned` or 0.
  - private `_available(session, category_id, year_month) -> int` — `rollover_in + assigned - spent`, recursing into prior months; base case 0 when a month has neither assignment nor spending.
- `rollover_in(month) = max(_available(prev_month), 0)` (ADR-005: positive carries, negative resets).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_budgets.py`:

```python
from quaestor.services import accounts, transactions
from quaestor.domain.models import AccountType


def _acc(session, balance=10_000_000):
    return accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=balance)


def test_budget_status_sums_only_expense_posted_in_month_category(session):
    cat = _cat(session)
    other = _cat(session, name="Other")
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-06", 100_000)
    transactions.record_expense(session, acc.id, 20_000, "COP", date(2026, 6, 10), "x", category_id=cat.id)
    transactions.record_expense(session, acc.id, 5_000, "COP", date(2026, 7, 1), "next month", category_id=cat.id)
    transactions.record_expense(session, acc.id, 9_000, "COP", date(2026, 6, 12), "other cat", category_id=other.id)
    transactions.record_income(session, acc.id, 50_000, "COP", date(2026, 6, 12), "salary", category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.spent == 20_000
    assert s.assigned == 100_000
    assert s.available == 80_000
    assert s.status == "under"


def test_budget_status_ignores_planned(session):
    from quaestor.services import planned
    cat = _cat(session)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-06", 100_000)
    planned.plan_payment(session, payee="p", amount=40_000, currency="COP",
                         due_date=date(2026, 6, 15), account_id=acc.id, category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.spent == 0


def test_budget_status_respects_exclude_flags(session):
    cat = _cat(session, exclude_from_budget=True)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-06", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 10), "x", category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.spent == 0


def test_budget_status_positive_rollover_carries_over(session):
    cat = _cat(session)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 5, 10), "may", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    transactions.record_expense(session, acc.id, 20_000, "COP", date(2026, 6, 10), "jun", category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.rollover_in == 70_000  # max(100k - 30k, 0)
    assert s.available == 100_000  # 70k + 50k - 20k


def test_budget_status_negative_rollover_resets_to_zero(session):
    cat = _cat(session)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 150_000, "COP", date(2026, 5, 10), "overspent", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.rollover_in == 0  # max(-50k, 0)
```

Add this helper import alias at the top of the test module (one line, near the other imports) so the tests read cleanly:

```python
from quaestor.services.budgets import budget_status as budget_status_for
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_budgets.py -q`
Expected: FAIL — `ImportError: cannot import name 'budget_status'` (the alias import fails).

- [ ] **Step 3: Add budget_status and helpers**

Append to `backend/src/quaestor/services/budgets.py`:

```python
def _assigned(session: Session, category_id: int, year_month: str) -> int:
    budget = session.exec(
        select(Budget).where(
            Budget.category_id == category_id, Budget.year_month == year_month
        )
    ).first()
    return budget.amount_assigned if budget is not None else 0


def _spent(session: Session, category_id: int, year_month: str) -> int:
    """Sum of expense+posted to_base for the month/category, across all accounts.

    Returns 0 when the category opts out via exclude_from_budget/exclude_from_totals.
    """
    cat = session.get(Category, category_id)
    if cat is None:
        raise NotFound(f"category {category_id} not found")
    if cat.exclude_from_budget or cat.exclude_from_totals:
        return 0
    start, end = month_bounds(year_month)
    rows = session.exec(
        select(Transaction).where(
            Transaction.category_id == category_id,
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    return sum(t.to_base for t in rows)


def _available(session: Session, category_id: int, year_month: str) -> int:
    """rollover_in + assigned - spent, recursing into prior months.

    Base case: a month with no assignment and no spending contributes 0 and
    stops the recursion (no infinite climb into the past).
    """
    assigned = _assigned(session, category_id, year_month)
    spent = _spent(session, category_id, year_month)
    if assigned == 0 and spent == 0:
        return 0
    rollover_in = max(_available(session, category_id, prev_year_month(year_month)), 0)
    return rollover_in + assigned - spent


def budget_status(session: Session, category_id: int, year_month: str) -> BudgetStatus:
    """Envelope status with rollover for a category/month.

    Raises:
        ValidationError: malformed year_month.
        NotFound: the category does not exist.
    """
    _validate_year_month(year_month)
    if session.get(Category, category_id) is None:
        raise NotFound(f"category {category_id} not found")
    assigned = _assigned(session, category_id, year_month)
    spent = _spent(session, category_id, year_month)
    rollover_in = max(_available(session, category_id, prev_year_month(year_month)), 0)
    return envelope_status_calc(category_id, year_month, assigned, rollover_in, spent)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_budgets.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/budgets.py backend/tests/services/test_budgets.py
git commit -m "feat(services): add budget_status with rollover + exclude flags"
```

---

### Task 7: Budget service — safe_to_spend (cascade)

**Files:**
- Modify: `backend/src/quaestor/services/budgets.py`
- Test: `backend/tests/services/test_budgets.py` (append)

**Interfaces:**
- Consumes: `safe_to_spend_calc`, `due_dates`, `month_bounds`, `prev_year_month`, `_spent`, `_available`, `_assigned` (Tasks 2/3/6); `_tx._resolve_fx`, `to_base_cents`.
- Produces: `safe_to_spend(session, year_month: str) -> SafeToSpend`. The cascade buckets are split with **no overlap**: envelope categories affect only `assigned_envelopes` + `overspend`; non-envelope categories affect only `committed` + `unbudgeted_spending`. This makes confirming/posting an obligation move it between `committed` and `unbudgeted` of equal value (the ADR-014 double-count guard), and `committed` projects the whole month via `due_dates` (ADR-020 due-driven stability).

**Bucket rules (encoded by the helpers):**
- `income_forecast` = Σ over active income `RecurringItem`s of `to_base(amount)` per `due_date` in month.
- `committed` = Σ active expense `RecurringItem`s **in non-envelope categories** projected via `due_dates` (regardless of materialization) + Σ standalone (`recurring_id IS NULL`) `planned` txs in month **in non-envelope categories** (includes proposed goal-contribution transfers, which carry no category).
- `assigned_envelopes` = Σ `Budget.amount_assigned` for the month.
- `unbudgeted_spending` = Σ `to_base` of `posted` `expense` txs in month with `recurring_id IS NULL`, in categories that have **no envelope** and are not `exclude_*` (category `None` counts as unbudgeted).
- `overspend` = Σ over the month's `Budget`s of `max(_spent - (amount_assigned + rollover_in), 0)`.

> Scope note: a confirmed goal-contribution transfer leaves `committed` (planned→posted transfer) and is not an expense, so it does not reappear in another bucket — confirming a *contribution* may raise safe-to-spend (the money is now allocated to savings). This v1 behavior is intentional and is **not** asserted by the double-count tests, which cover expense obligations and auto-recurring posting per the spec's "done" criteria.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_budgets.py`:

```python
from quaestor.services import planned, recurring, settings as settings_svc
from quaestor.domain.models import IntervalUnit, RecurringMode, TxType


def _income(session, acc, amount=1_000_000, start=date(2026, 6, 1)):
    return recurring.create_recurring(
        session, name="Salary", payee="Job", type=TxType.income, mode=RecurringMode.manual,
        amount=amount, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=start,
    )


def test_safe_to_spend_basic_cascade(session):
    acc = _acc(session)
    cat = _cat(session)
    _income(session, acc)  # 1,000,000 forecast
    budgets.set_budget(session, cat.id, "2026-06", 300_000)
    planned.plan_payment(session, payee="Rent", amount=200_000, currency="COP",
                         due_date=date(2026, 6, 15), account_id=acc.id)  # no category -> committed
    sts = budgets.safe_to_spend(session, "2026-06")
    assert sts.income_forecast == 1_000_000
    assert sts.committed == 200_000
    assert sts.assigned_envelopes == 300_000
    assert sts.free == 500_000
    assert any(ci.kind == "planned" for ci in sts.committed_breakdown)


def test_safe_to_spend_optional_envelopes_do_not_subtract_twice(session):
    acc = _acc(session)
    env = _cat(session, name="Groceries")
    unb = _cat(session, name="Fun")
    _income(session, acc)
    budgets.set_budget(session, env.id, "2026-06", 200_000)
    transactions.record_expense(session, acc.id, 150_000, "COP", date(2026, 6, 10), "in envelope", category_id=env.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 11), "no envelope", category_id=unb.id)
    sts = budgets.safe_to_spend(session, "2026-06")
    # envelope spend claimed by assignment (200k), only unbudgeted 100k extra
    assert sts.free == 700_000  # 1,000,000 - 0 - 200,000 - 100,000 - 0


def test_safe_to_spend_double_count_guard_auto_recurring(session):
    acc = _acc(session)
    _income(session, acc)
    recurring.create_recurring(
        session, name="Netflix", payee="Netflix", type=TxType.expense, mode=RecurringMode.auto,
        amount=250_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 5),
    )
    free_before = budgets.safe_to_spend(session, "2026-06").free
    recurring.materialize_due(session, date(2026, 6, 30))  # posts the recurring tx
    free_after = budgets.safe_to_spend(session, "2026-06").free
    assert free_before == 750_000 == free_after  # posting doesn't move it


def test_safe_to_spend_due_driven_stability_manual(session):
    acc = _acc(session)
    _income(session, acc)
    recurring.create_recurring(
        session, name="Gym", payee="Gym", type=TxType.expense, mode=RecurringMode.manual,
        amount=80_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 20),
    )
    recurring.materialize_due(session, date(2026, 6, 5))  # nothing due yet
    free_day5 = budgets.safe_to_spend(session, "2026-06").free
    recurring.materialize_due(session, date(2026, 6, 25))  # now a planned occurrence exists
    free_day25 = budgets.safe_to_spend(session, "2026-06").free
    assert free_day5 == 920_000 == free_day25  # committed projects the month regardless


def test_safe_to_spend_confirm_planned_does_not_move_it(session):
    acc = _acc(session)
    _income(session, acc)
    tx = planned.plan_payment(session, payee="Vet", amount=120_000, currency="COP",
                              due_date=date(2026, 6, 15), account_id=acc.id)  # no category
    free_before = budgets.safe_to_spend(session, "2026-06").free
    planned.confirm_payment(session, tx.id)  # planned expense -> posted unbudgeted
    free_after = budgets.safe_to_spend(session, "2026-06").free
    assert free_before == 880_000 == free_after


def test_safe_to_spend_overspend_reduces_pool_and_rollover_protects(session):
    acc = _acc(session)
    cat = _cat(session, name="Dining")
    _income(session, acc)
    # May builds rollover_in for June: assigned 100k, spent 30k -> available 70k
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 5, 10), "may", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    # June overspends: spent 200k vs assigned 50k + rollover 70k = 120k -> overspend 80k
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 10), "jun", category_id=cat.id)
    sts = budgets.safe_to_spend(session, "2026-06")
    assert sts.free == 870_000  # 1,000,000 - 0 - 50,000 - 0 - 80,000


def test_safe_to_spend_rollover_protects_against_false_overspend(session):
    acc = _acc(session)
    cat = _cat(session, name="Dining")
    _income(session, acc)
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 5, 10), "may", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 10), "jun", category_id=cat.id)
    sts = budgets.safe_to_spend(session, "2026-06")
    # spent 100k <= assigned 50k + rollover 70k = 120k -> overspend 0
    assert sts.free == 950_000  # 1,000,000 - 0 - 50,000 - 0 - 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_budgets.py -q`
Expected: FAIL — `AttributeError: module 'quaestor.services.budgets' has no attribute 'safe_to_spend'`.

- [ ] **Step 3: Add safe_to_spend and cascade helpers**

Append to `backend/src/quaestor/services/budgets.py`:

```python
def _has_envelope(session: Session, category_id: int, year_month: str) -> bool:
    return session.exec(
        select(Budget).where(
            Budget.category_id == category_id, Budget.year_month == year_month
        )
    ).first() is not None


def _income_forecast(session: Session, start, end) -> int:
    total = 0
    items = session.exec(
        select(RecurringItem).where(
            RecurringItem.active == True,  # noqa: E712
            RecurringItem.type == TxType.income,
        )
    ).all()
    for item in items:
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, start, end,
        ):
            rate = _tx._resolve_fx(session, item.currency, d, None)
            total += to_base_cents(item.amount, rate)
    return total


def _committed(session: Session, year_month: str, start, end) -> tuple[int, list]:
    """Projected month obligations in non-envelope categories, counted once."""
    total = 0
    breakdown: list[CommittedItem] = []
    items = session.exec(
        select(RecurringItem).where(
            RecurringItem.active == True,  # noqa: E712
            RecurringItem.type == TxType.expense,
        )
    ).all()
    for item in items:
        if item.category_id is not None and _has_envelope(session, item.category_id, year_month):
            continue
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, start, end,
        ):
            rate = _tx._resolve_fx(session, item.currency, d, None)
            amount = to_base_cents(item.amount, rate)
            total += amount
            breakdown.append(CommittedItem(kind="recurring", name=item.name, date=d, amount=amount))
    planned_txs = session.exec(
        select(Transaction).where(
            Transaction.status == TxStatus.planned,
            Transaction.recurring_id == None,  # noqa: E711
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    for tx in planned_txs:
        if tx.category_id is not None and _has_envelope(session, tx.category_id, year_month):
            continue
        total += tx.to_base
        breakdown.append(CommittedItem(kind="planned", name=tx.payee, date=tx.date, amount=tx.to_base))
    return total, breakdown


def _unbudgeted_spending(session: Session, year_month: str, start, end) -> int:
    total = 0
    rows = session.exec(
        select(Transaction).where(
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
            Transaction.recurring_id == None,  # noqa: E711
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    for tx in rows:
        if tx.category_id is None:
            total += tx.to_base
            continue
        cat = session.get(Category, tx.category_id)
        if cat is not None and (cat.exclude_from_budget or cat.exclude_from_totals):
            continue
        if _has_envelope(session, tx.category_id, year_month):
            continue
        total += tx.to_base
    return total


def _sum_assigned(session: Session, year_month: str) -> int:
    rows = session.exec(
        select(Budget.amount_assigned).where(Budget.year_month == year_month)
    ).all()
    return sum(rows)


def _sum_overspend(session: Session, year_month: str) -> int:
    total = 0
    budgets_ = session.exec(
        select(Budget).where(Budget.year_month == year_month)
    ).all()
    for b in budgets_:
        spent = _spent(session, b.category_id, year_month)
        rollover_in = max(_available(session, b.category_id, prev_year_month(year_month)), 0)
        over = spent - (b.amount_assigned + rollover_in)
        if over > 0:
            total += over
    return total


def safe_to_spend(session: Session, year_month: str) -> SafeToSpend:
    """Global safe-to-spend headline + breakdown (ADR-003/005/014/016).

    Raises:
        ValidationError: malformed year_month.
    """
    _validate_year_month(year_month)
    start, end = month_bounds(year_month)
    income = _income_forecast(session, start, end)
    committed, breakdown = _committed(session, year_month, start, end)
    assigned = _sum_assigned(session, year_month)
    unbudgeted = _unbudgeted_spending(session, year_month, start, end)
    overspend = _sum_overspend(session, year_month)
    free = safe_to_spend_calc(income, committed, assigned, unbudgeted, overspend)
    return SafeToSpend(
        year_month=year_month, income_forecast=income, committed=committed,
        assigned_envelopes=assigned, free=free, committed_breakdown=breakdown,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_budgets.py -q`
Expected: PASS (17 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/budgets.py backend/tests/services/test_budgets.py
git commit -m "feat(services): add safe_to_spend cascade (envelopes, committed, overspend)"
```

---

### Task 8: Goal service — create_goal

**Files:**
- Create: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py`

**Interfaces:**
- Produces: `create_goal(session, name: str, monthly_amount: int, savings_account_id: int, target_amount: int | None = None, deadline: date | None = None) -> Goal`.
  - Defined iff `target_amount` **and** `deadline`; open-ended iff neither; exactly one → `ValidationError`.
  - `monthly_amount <= 0` → `ValidationError`; `target_amount <= 0` (when given) → `ValidationError`.
  - `savings_account_id` must exist, be `type=savings`, not `archived` — else `ValidationError`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_goals.py`:

```python
from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, GoalStatus
from quaestor.services import accounts, goals


def _savings(session, archived=False):
    acc = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    if archived:
        accounts.archive_account(session, acc.id)
    return acc


def test_create_defined_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000,
                          savings_account_id=sav.id, target_amount=1_200_000,
                          deadline=date(2026, 12, 1))
    assert g.id is not None and g.status == GoalStatus.active
    assert g.target_amount == 1_200_000 and g.deadline == date(2026, 12, 1)


def test_create_open_ended_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    assert g.target_amount is None and g.deadline is None


def test_create_goal_only_target_raises(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000,
                          savings_account_id=sav.id, target_amount=500_000)


def test_create_goal_only_deadline_raises(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000,
                          savings_account_id=sav.id, deadline=date(2026, 12, 1))


def test_create_goal_rejects_non_positive_monthly(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=0, savings_account_id=sav.id)


def test_create_goal_rejects_non_savings_account(session):
    acc = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=0)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=acc.id)


def test_create_goal_rejects_archived_savings(session):
    sav = _savings(session, archived=True)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=sav.id)


def test_create_goal_rejects_unknown_account(session):
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=999)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'quaestor.services.goals'`.

- [ ] **Step 3: Create the service**

Create `backend/src/quaestor/services/goals.py`:

```python
"""Savings goals: create, standalone contribution, progress, and the P3 hook seam (ADR-006/007)."""
from __future__ import annotations

import uuid
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.dtos import GoalProgress
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    AccountType,
    ContributionSource,
    Goal,
    GoalContribution,
    GoalStatus,
    Settings,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_base_cents
from ..domain.rules import goal_progress_calc, month_bounds, transfer_deltas
from . import transactions as _tx


def create_goal(
    session: Session,
    name: str,
    monthly_amount: int,
    savings_account_id: int,
    target_amount: int | None = None,
    deadline: Date | None = None,
) -> Goal:
    """Create a savings goal (defined if target+deadline; open-ended if neither).

    Raises:
        ValidationError: monthly_amount <= 0; only one of target/deadline given;
            target_amount <= 0; savings account missing, not savings, or archived.
    """
    if monthly_amount <= 0:
        raise ValidationError("monthly_amount must be > 0")
    has_target = target_amount is not None
    has_deadline = deadline is not None
    if has_target != has_deadline:
        raise ValidationError(
            "a defined goal needs both target_amount and deadline; "
            "an open-ended goal needs neither"
        )
    if has_target and target_amount <= 0:
        raise ValidationError("target_amount must be > 0")
    acc = session.get(Account, savings_account_id)
    if acc is None:
        raise ValidationError(f"savings account {savings_account_id} does not exist")
    if acc.type != AccountType.savings:
        raise ValidationError(f"account {savings_account_id} is not a savings account")
    if acc.archived:
        raise ValidationError(f"savings account {savings_account_id} is archived")
    goal = Goal(
        name=name, monthly_amount=monthly_amount, savings_account_id=savings_account_id,
        target_amount=target_amount, deadline=deadline, status=GoalStatus.active,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal
```

> Note: the import block carries names used by Tasks 9–12 (`uuid`, `select`, `GoalProgress`, `ContributionSource`, `GoalContribution`, `Settings`, `Source`, `Transaction`, `TxStatus`, `TxType`, `to_base_cents`, `goal_progress_calc`, `month_bounds`, `transfer_deltas`, `_tx`, `NotFound`). Intentionally imported now so later tasks only append functions.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(services): add create_goal (defined + open-ended)"
```

---

### Task 9: Goal service — goal_contribution (standalone, atomic)

**Files:**
- Modify: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py` (append)

**Interfaces:**
- Produces:
  - `goal_contribution(session, goal_id: int, amount: int, date: date) -> GoalContribution` — `source=manual`; performs the internal transfer (`Settings.default_source_account_id` → goal's savings account) **and** records the contribution in **one** transaction (atomic). Flips a defined goal to `reached` when `saved >= target`.
  - private `_saved(session, goal_id) -> int` and `_maybe_mark_reached(session, goal)` (reused by Tasks 10/12).
- The transfer legs are built inline (mirroring P3's `_materialize_planned_transfer`) so the transfer and the `GoalContribution` commit together; `transactions.transfer` is not used here because it commits on its own and would break atomicity.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_goals.py`:

```python
from quaestor.domain.models import TxType
from quaestor.services import settings as settings_svc, transactions


def _funded(session):
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    return src, sav


def test_goal_contribution_creates_manual_contribution_and_transfer(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    c = goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    assert c.source.value == "manual" and c.amount == 150_000
    assert c.transaction_id is not None
    assert accounts.get_account(session, src.id).balance == 850_000
    assert accounts.get_account(session, sav.id).balance == 150_000


def test_goal_contribution_is_not_expense_or_income(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    assert transactions.list_transactions(session, type=TxType.expense) == []
    assert transactions.list_transactions(session, type=TxType.income) == []
    transfers = transactions.list_transactions(session, type=TxType.transfer, status="posted")
    assert len(transfers) == 2


def test_goal_contribution_without_default_source_is_atomic(session):
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    from sqlmodel import select
    from quaestor.domain.models import GoalContribution
    assert session.exec(select(GoalContribution)).all() == []  # nothing recorded


def test_goal_contribution_reaching_target_marks_reached(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=300_000, deadline=date(2026, 12, 1))
    goals.goal_contribution(session, g.id, 300_000, date(2026, 6, 15))
    from quaestor.domain.models import Goal, GoalStatus
    assert session.get(Goal, g.id).status == GoalStatus.reached


def test_goal_contribution_rejects_bad_amount_and_unknown_goal(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 0, date(2026, 6, 15))
    with pytest.raises(NotFound):
        goals.goal_contribution(session, 999, 100_000, date(2026, 6, 15))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: FAIL — `AttributeError: module 'quaestor.services.goals' has no attribute 'goal_contribution'`.

- [ ] **Step 3: Add goal_contribution and reached helpers**

Append to `backend/src/quaestor/services/goals.py`:

```python
def _saved(session: Session, goal_id: int) -> int:
    rows = session.exec(
        select(GoalContribution.amount).where(GoalContribution.goal_id == goal_id)
    ).all()
    return sum(rows)


def _maybe_mark_reached(session: Session, goal: Goal) -> None:
    """Flip a defined goal to reached once its contributions meet target. No-op otherwise.

    Relies on autoflush: any contribution added earlier in this transaction is
    visible to the _saved query.
    """
    if goal.target_amount is None:
        return
    if _saved(session, goal.id) >= goal.target_amount:
        goal.status = GoalStatus.reached
        session.add(goal)


def goal_contribution(
    session: Session, goal_id: int, amount: int, date: Date
) -> GoalContribution:
    """Standalone manual contribution: internal transfer + GoalContribution, atomic.

    Raises:
        ValidationError: amount <= 0; no default source account; same source/dest;
            missing/archived source or savings account; currency mismatch.
        NotFound: the goal does not exist.
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise NotFound(f"goal {goal_id} not found")
    dst = session.get(Account, goal.savings_account_id)
    if dst is None or dst.archived:
        raise ValidationError("goal savings account is missing or archived")
    settings = session.get(Settings, 1)
    src_id = settings.default_source_account_id if settings else None
    if src_id is None:
        raise ValidationError("no default source account configured for transfers")
    if src_id == dst.id:
        raise ValidationError("source and destination cannot be the same account")
    src = session.get(Account, src_id)
    if src is None or src.archived:
        raise ValidationError(f"source account {src_id} is missing or archived")
    if src.currency != dst.currency:
        raise ValidationError("transfer currency must match both accounts")
    rate = _tx._resolve_fx(session, dst.currency, date, None)
    base = to_base_cents(amount, rate)
    group = uuid.uuid4().hex
    d_from, d_to = transfer_deltas(amount)
    try:
        leg_from = Transaction(
            date=date, payee=f"Goal: {goal.name}", type=TxType.transfer,
            status=TxStatus.posted, amount=amount, currency=dst.currency, fx_rate=rate,
            to_base=base, account_id=src.id, transfer_group_id=group, source=Source.manual,
        )
        leg_to = Transaction(
            date=date, payee=f"Goal: {goal.name}", type=TxType.transfer,
            status=TxStatus.posted, amount=amount, currency=dst.currency, fx_rate=rate,
            to_base=base, account_id=dst.id, transfer_group_id=group, source=Source.manual,
        )
        src.balance += d_from
        dst.balance += d_to
        session.add_all([leg_from, leg_to, src, dst])
        session.flush()  # assign leg_to.id for the contribution link
        contribution = GoalContribution(
            goal_id=goal.id, date=date, amount=base,
            source=ContributionSource.manual, transaction_id=leg_to.id,
        )
        session.add(contribution)
        _maybe_mark_reached(session, goal)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(contribution)
    return contribution
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: PASS (13 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(services): add standalone goal_contribution (atomic transfer + record)"
```

---

### Task 10: Goal service — goals_progress

**Files:**
- Modify: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py` (append)

**Interfaces:**
- Produces: `goals_progress(session, goal_ids: list[int] | None = None, today: date | None = None) -> list[GoalProgress]`. With `goal_ids=None` returns all **active** goals; with explicit `goal_ids` returns those goals regardless of status. `today` defaults to `date.today()` (P1/P2 omit it; tests pass it for determinism). `saved` per goal = Σ its `GoalContribution.amount` (via `_saved`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_goals.py`:

```python
def test_goals_progress_open_ended_reports_saved(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    goals.goal_contribution(session, g.id, 250_000, date(2026, 6, 1))
    [p] = goals.goals_progress(session, today=date(2026, 6, 19))
    assert p.type == "open-ended" and p.saved == 250_000
    assert p.monthly_required is None


def test_goals_progress_defined_reports_on_track_and_eta(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=1_200_000, deadline=date(2026, 12, 1))
    goals.goal_contribution(session, g.id, 200_000, date(2026, 6, 1))
    [p] = goals.goals_progress(session, today=date(2026, 6, 19))
    assert p.type == "defined" and p.remaining == 1_000_000
    assert p.monthly_required == 166_667 and p.on_track is True
    assert p.eta == date(2026, 11, 19)


def test_goals_progress_default_lists_only_active(session):
    src, sav = _funded(session)
    active = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    paused = goals.create_goal(session, name="B", monthly_amount=100_000, savings_account_id=sav.id)
    from quaestor.domain.models import Goal, GoalStatus
    session.get(Goal, paused.id).status = GoalStatus.paused
    session.commit()
    ids = [p.goal_id for p in goals.goals_progress(session, today=date(2026, 6, 19))]
    assert ids == [active.id]


def test_goals_progress_explicit_ids_include_inactive(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    from quaestor.domain.models import Goal, GoalStatus
    session.get(Goal, g.id).status = GoalStatus.paused
    session.commit()
    ids = [p.goal_id for p in goals.goals_progress(session, goal_ids=[g.id], today=date(2026, 6, 19))]
    assert ids == [g.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: FAIL — `AttributeError: module 'quaestor.services.goals' has no attribute 'goals_progress'`.

- [ ] **Step 3: Add goals_progress**

Append to `backend/src/quaestor/services/goals.py`:

```python
def goals_progress(
    session: Session,
    goal_ids: list[int] | None = None,
    today: Date | None = None,
) -> list[GoalProgress]:
    """Progress of each goal (all active ones if goal_ids=None).

    today defaults to date.today(); pass it explicitly for deterministic tests.
    """
    if today is None:
        today = Date.today()
    stmt = select(Goal)
    if goal_ids is not None:
        stmt = stmt.where(Goal.id.in_(goal_ids))
    else:
        stmt = stmt.where(Goal.status == GoalStatus.active)
    goals_ = session.exec(stmt.order_by(Goal.id)).all()
    return [
        goal_progress_calc(
            goal.id, goal.name, goal.monthly_amount, _saved(session, goal.id),
            goal.target_amount, goal.deadline, today,
        )
        for goal in goals_
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: PASS (17 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(services): add goals_progress (active default, explicit ids)"
```

---

### Task 11: Goal service — propose_goal_contributions (rollover hook)

**Files:**
- Modify: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py` (append)

**Interfaces:**
- Produces: `propose_goal_contributions(period: str, session) -> list[Transaction]`. For each **active** goal with **no** existing transaction carrying its `goal_id` in `period`, creates a `planned` `type=transfer` tx: `account_id = savings_account_id` (the destination — P3's `confirm_payment` pulls the source from `Settings`), `goal_id` set, `amount = monthly_amount`, `date = ` last day of `period`. **Does not commit** (runs inside `close_month`'s transaction; the function only `session.add`s — P3 convention). Returns the created txs (the registered hook's return value is ignored by `close_month`). Idempotent per `(goal_id, period)`; `paused`/`reached` goals skipped; an archived savings account raises `ValidationError` (aborts the close).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_goals.py`:

```python
from quaestor.domain.models import Goal, GoalStatus, Transaction, TxStatus


def _planned_transfers(session):
    return [
        t for t in transactions.list_transactions(session, type=TxType.transfer, status="planned")
    ]


def test_propose_creates_planned_transfer_per_active_goal(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    txs = _planned_transfers(session)
    assert len(txs) == 1
    tx = txs[0]
    assert tx.goal_id == g.id and tx.amount == 200_000
    assert tx.account_id == sav.id and tx.date == date(2026, 6, 30)
    # no balance moved by a proposal
    assert accounts.get_account(session, src.id).balance == 1_000_000
    assert accounts.get_account(session, sav.id).balance == 0


def test_propose_skips_paused_and_reached(session):
    src, sav = _funded(session)
    goals.create_goal(session, name="Active", monthly_amount=100_000, savings_account_id=sav.id)
    paused = goals.create_goal(session, name="Paused", monthly_amount=100_000, savings_account_id=sav.id)
    reached = goals.create_goal(session, name="Reached", monthly_amount=100_000, savings_account_id=sav.id)
    session.get(Goal, paused.id).status = GoalStatus.paused
    session.get(Goal, reached.id).status = GoalStatus.reached
    session.commit()
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    txs = _planned_transfers(session)
    assert len(txs) == 1 and txs[0].payee == "Goal: Active"


def test_propose_is_idempotent_per_goal_period(session):
    src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    goals.propose_goal_contributions("2026-06", session)  # re-run
    session.commit()
    assert len(_planned_transfers(session)) == 1


def test_propose_archived_savings_raises(session):
    src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    accounts.archive_account(session, sav.id)
    with pytest.raises(ValidationError):
        goals.propose_goal_contributions("2026-06", session)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: FAIL — `AttributeError: module 'quaestor.services.goals' has no attribute 'propose_goal_contributions'`.

- [ ] **Step 3: Add propose_goal_contributions**

Append to `backend/src/quaestor/services/goals.py`:

```python
def propose_goal_contributions(period: str, session: Session) -> list[Transaction]:
    """Rollover hook: create one `planned` transfer per active goal (no money moved).

    Idempotent per (goal_id, period): skips a goal that already has any transaction
    carrying its goal_id dated within the period (planned, posted, or skipped), so
    daily re-runs of close_month never duplicate a proposal.

    Does NOT commit — close_month owns the transaction. Writes directly to session.

    Raises:
        ValidationError: a goal's savings account is missing or archived.
    """
    start, end = month_bounds(period)
    created: list[Transaction] = []
    goals_ = session.exec(select(Goal).where(Goal.status == GoalStatus.active)).all()
    for goal in goals_:
        existing = session.exec(
            select(Transaction).where(
                Transaction.goal_id == goal.id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).first()
        if existing is not None:
            continue
        dst = session.get(Account, goal.savings_account_id)
        if dst is None:
            raise ValidationError(f"goal {goal.id} savings account is missing")
        if dst.archived:
            raise ValidationError(f"goal {goal.id} savings account is archived")
        rate = _tx._resolve_fx(session, dst.currency, end, None)
        tx = Transaction(
            date=end, payee=f"Goal: {goal.name}", type=TxType.transfer,
            status=TxStatus.planned, amount=goal.monthly_amount, currency=dst.currency,
            fx_rate=rate, to_base=to_base_cents(goal.monthly_amount, rate),
            account_id=goal.savings_account_id, goal_id=goal.id, source=Source.manual,
        )
        session.add(tx)
        created.append(tx)
    return created
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: PASS (21 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(services): add propose_goal_contributions rollover hook (idempotent)"
```

---

### Task 12: Goal service — record_confirmed_contribution (post-confirm hook)

**Files:**
- Modify: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py` (append)

**Interfaces:**
- Produces: `record_confirmed_contribution(tx, session) -> GoalContribution | None`. If `tx.goal_id` is set, records `GoalContribution(source=confirmed, amount=tx.to_base, transaction_id=tx.id)` and flips a defined goal to `reached` when met; otherwise no-op returning `None`. **Does not commit** — it runs inside `confirm_payment`'s transaction (P3 fires it after posting). `confirm_payment` materializes the `planned` transfer into a real posted pair before calling this hook, so the money has already moved.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_goals.py`:

```python
from quaestor.services import planned


@pytest.fixture
def goal_post_confirm_hook():
    # Idempotent: from Task 13 onward init_db registers this hook globally, so only
    # add it here when absent (and only remove what this fixture added). This keeps
    # exactly one registration -> the hook fires once -> one contribution per confirm.
    hook = goals.record_confirmed_contribution
    added = hook not in planned.POST_CONFIRM_HOOKS
    if added:
        planned.register_post_confirm_hook(hook)
    try:
        yield
    finally:
        if added:
            planned.POST_CONFIRM_HOOKS.remove(hook)


def test_record_confirmed_contribution_unit(session):
    from decimal import Decimal
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    tx = Transaction(date=date(2026, 6, 30), type=TxType.transfer, status=TxStatus.posted,
                     amount=200_000, currency="COP", fx_rate=Decimal("1"), to_base=200_000,
                     account_id=sav.id, goal_id=g.id)
    session.add(tx)
    session.flush()
    c = goals.record_confirmed_contribution(tx, session)
    session.commit()
    assert c is not None and c.source.value == "confirmed"
    assert c.amount == 200_000 and c.transaction_id == tx.id
    assert len(session.exec(select(GoalContribution)).all()) == 1


def test_record_confirmed_contribution_noop_without_goal_id(session):
    from decimal import Decimal
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    src, sav = _funded(session)
    tx = Transaction(date=date(2026, 6, 30), type=TxType.transfer, status=TxStatus.posted,
                     amount=100_000, currency="COP", fx_rate=Decimal("1"), to_base=100_000,
                     account_id=sav.id)
    session.add(tx)
    session.flush()
    assert goals.record_confirmed_contribution(tx, session) is None
    session.commit()
    assert session.exec(select(GoalContribution)).all() == []


def test_confirm_proposal_records_contribution(session, goal_post_confirm_hook):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.confirm_payment(session, tx.id)
    [c] = session.exec(select(GoalContribution)).all()
    assert c.source.value == "confirmed" and c.amount == 200_000 and c.transaction_id == tx.id
    assert accounts.get_account(session, src.id).balance == 800_000
    assert accounts.get_account(session, sav.id).balance == 200_000


def test_confirm_with_smaller_amount_adjusts_contribution(session, goal_post_confirm_hook):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.confirm_payment(session, tx.id, amount=120_000)
    [c] = session.exec(select(GoalContribution)).all()
    assert c.amount == 120_000
    assert accounts.get_account(session, sav.id).balance == 120_000


def test_skip_proposal_contributes_nothing(session, goal_post_confirm_hook):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.skip_payment(session, tx.id)
    assert session.exec(select(GoalContribution)).all() == []
    assert accounts.get_account(session, sav.id).balance == 0


def test_confirm_reaching_target_marks_reached(session, goal_post_confirm_hook):
    from quaestor.domain.models import Goal, GoalStatus
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=200_000, deadline=date(2026, 12, 1))
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.confirm_payment(session, tx.id)
    assert session.get(Goal, g.id).status == GoalStatus.reached
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: FAIL — `AttributeError: module 'quaestor.services.goals' has no attribute 'record_confirmed_contribution'`.

- [ ] **Step 3: Add record_confirmed_contribution**

Append to `backend/src/quaestor/services/goals.py`:

```python
def record_confirmed_contribution(tx: Transaction, session: Session) -> GoalContribution | None:
    """Post-confirm hook: record a confirmed GoalContribution for a goal transfer.

    No-op (returns None) when tx carries no goal_id. Does NOT commit — runs inside
    confirm_payment's transaction, which has already materialized the real transfer.
    """
    if tx.goal_id is None:
        return None
    goal = session.get(Goal, tx.goal_id)
    if goal is None:
        return None
    contribution = GoalContribution(
        goal_id=goal.id, date=tx.date, amount=tx.to_base,
        source=ContributionSource.confirmed, transaction_id=tx.id,
    )
    session.add(contribution)
    _maybe_mark_reached(session, goal)
    return contribution
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_goals.py -q`
Expected: PASS (27 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(services): add record_confirmed_contribution post-confirm hook"
```

---

### Task 13: Bootstrap — register hooks in P3's seams + wire into init_db

**Files:**
- Create: `backend/src/quaestor/services/bootstrap.py`
- Modify: `backend/src/quaestor/db.py`
- Test: `backend/tests/services/test_goal_hooks.py`

**Interfaces:**
- Consumes: `propose_goal_contributions`, `record_confirmed_contribution` (Tasks 11/12); P3's `register_rollover_hook`/`ROLLOVER_HOOKS` and `register_post_confirm_hook`/`POST_CONFIRM_HOOKS`.
- Produces: `register_goal_hooks() -> None` — idempotent registration of both hooks. Called from `db.init_db` (lazy import to avoid the `services → db` import cycle), so the API lifespan and the MCP server both get the wiring, and per-test `init_db` calls never duplicate.

> Cross-cutting effect: after this task the goal hooks are registered for every session that runs `init_db`. Existing P3 tests stay green because both hooks are no-ops without goals: `propose_goal_contributions` finds no active goals (creates nothing) and `record_confirmed_contribution` returns early for txs without `goal_id`. The full-suite run in Step 6 confirms this.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_goal_hooks.py`:

```python
from datetime import date

from sqlmodel import select

from quaestor.domain.models import AccountType, GoalContribution, TxStatus, TxType
from quaestor.services import accounts, goals, planned, rollover, settings as settings_svc, transactions
from quaestor.services.bootstrap import register_goal_hooks


def _funded(session):
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    return src, sav


def test_init_db_registers_goal_hooks_once(session):
    # conftest's init_db already ran register_goal_hooks; re-running must not duplicate
    register_goal_hooks()
    register_goal_hooks()
    assert rollover.ROLLOVER_HOOKS.count(goals.propose_goal_contributions) == 1
    assert planned.POST_CONFIRM_HOOKS.count(goals.record_confirmed_contribution) == 1


def test_close_month_then_confirm_full_cycle(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    # close_month fires the registered rollover hook -> a planned proposal lands
    rollover.close_month(session, "2026-06")
    planned_txs = transactions.list_transactions(session, type=TxType.transfer, status="planned")
    assert len(planned_txs) == 1 and planned_txs[0].goal_id == g.id
    # re-running close_month does not duplicate the proposal
    rollover.close_month(session, "2026-06")
    assert len(transactions.list_transactions(session, type=TxType.transfer, status="planned")) == 1
    # confirming fires the registered post-confirm hook -> contribution recorded
    planned.confirm_payment(session, planned_txs[0].id)
    [c] = session.exec(select(GoalContribution)).all()
    assert c.source.value == "confirmed" and c.amount == 200_000
    assert accounts.get_account(session, src.id).balance == 800_000
    assert accounts.get_account(session, sav.id).balance == 200_000
    # re-running close_month after confirmation still does not re-propose for the period
    rollover.close_month(session, "2026-06")
    assert len(session.exec(select(GoalContribution)).all()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_goal_hooks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'quaestor.services.bootstrap'`.

- [ ] **Step 3: Create bootstrap and wire init_db**

Create `backend/src/quaestor/services/bootstrap.py`:

```python
"""P4 seam registration: wire goal hooks into P3's rollover/post-confirm seams.

Called by db.init_db so the API (lifespan) and the MCP server share one wiring.
Idempotent: re-running init_db (e.g. once per test) never duplicates a hook.
"""
from __future__ import annotations


def register_goal_hooks() -> None:
    from .goals import propose_goal_contributions, record_confirmed_contribution
    from .planned import POST_CONFIRM_HOOKS, register_post_confirm_hook
    from .rollover import ROLLOVER_HOOKS, register_rollover_hook

    if propose_goal_contributions not in ROLLOVER_HOOKS:
        register_rollover_hook(propose_goal_contributions)
    if record_confirmed_contribution not in POST_CONFIRM_HOOKS:
        register_post_confirm_hook(record_confirmed_contribution)
```

In `backend/src/quaestor/db.py`, extend `init_db` to register the hooks (lazy import inside the function to avoid the `services → db` cycle). Replace the existing `init_db` body:

```python
def init_db(target_engine: Engine = engine) -> None:
    SQLModel.metadata.create_all(target_engine)
    with Session(target_engine) as s:
        if s.get(Settings, 1) is None:
            s.add(Settings(id=1, base_currency="COP"))
            s.commit()
    from .services.bootstrap import register_goal_hooks
    register_goal_hooks()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_goal_hooks.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/bootstrap.py backend/src/quaestor/db.py backend/tests/services/test_goal_hooks.py
git commit -m "feat(services): register goal hooks in P3 seams via init_db bootstrap"
```

- [ ] **Step 6: Full-suite regression run**

Run: `cd backend && python -m pytest -q`
Expected: PASS — the entire suite (P0–P4) green. Pay attention to `tests/services/test_rollover.py` and `tests/services/test_planned.py`: they must still pass with the goal hooks globally registered (both hooks are no-ops without goals/`goal_id`). If any P3 test fails, the goal hooks are not behaving as no-ops — fix the hook, not the P3 test.

---

## Self-Review

**1. Spec coverage**

- `Budget`, `Goal`, `GoalContribution` models + `Transaction.goal_id` → Task 1.
- `set_budget`, `budget_status` (rollover, exclude flags), `safe_to_spend` (cascade) → Tasks 5–7.
- `create_goal`, `goal_contribution` (standalone), `goals_progress` → Tasks 8–10.
- Defined goal math (monthly_required/on_track/eta) + open-ended → Tasks 4, 10.
- `propose_goal_contributions` (rollover hook, idempotent) + `record_confirmed_contribution` (post-confirm hook) → Tasks 11–12.
- Seam registration in bootstrap → Task 13.
- Pure rules (`envelope_status_calc`, `safe_to_spend_calc`, `goal_progress_calc`) → Tasks 2–4.
- Errors (`ValidationError`/`NotFound`) exercised in Tasks 5, 6, 8, 9, 11.
- "Done" test bullets — envelope rollover/exclude/zero-denominator (Task 6), cascade/optional-envelopes/double-count/due-driven-stability/overspend (Task 7), defined/open-ended/reached (Tasks 4, 10), standalone contribution atomic (Task 9), propose+confirm flexible/idempotent/skip/adjust (Tasks 11–13).
- **Out of scope** (correctly absent): goals as % of income; recurring/`planned` mechanics (P3, consumed only); reports/markdown (P5); REST routers and MCP tools (P1/P2 — P4 delivers the services, no routers/tools here).

**2. Placeholder scan** — no `TBD`/`handle edge cases`/"similar to Task N"; every code step carries full code.

**3. Type consistency** — DTO field names match across `dtos.py`, the pure calcs, and the services (`assigned`, `rollover_in`, `available`, `pct_used`, `status`; `income_forecast`, `committed`, `assigned_envelopes`, `free`, `committed_breakdown`; `type`, `monthly_required`, `on_track`, `eta`, `remaining`). Hook signatures match P3's seams exactly (`(period, session)` and `(tx, session)`). `_saved`/`_maybe_mark_reached` defined in Task 9, reused by Tasks 10/12. `_spent`/`_available`/`_assigned` defined in Task 6, reused by Task 7.

**Known v1 scoping (intentional, not gaps):**
- No Alembic; "migration" = model defs + `create_all` (see Global Constraints). An `ALTER` for a pre-existing persistent DB is deferred.
- Confirming a goal-contribution *transfer* can raise safe-to-spend (it leaves `committed` and is not an expense). The double-count guarantee is scoped to expense obligations and auto-recurring posting, matching the spec's "done" criteria; not asserted otherwise.
- `goals_progress` gains an optional `today` keyword for deterministic tests; the public positional signature is unchanged for P1/P2.
