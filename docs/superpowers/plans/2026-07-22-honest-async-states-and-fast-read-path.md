# Honest Async States + Fast Read Path — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the budgets, reports, and dashboard pages render honest loading/error/empty/success states, and make the monthly read-path issue a fixed number of queries with bounded row transfer.

**Architecture:** Backend introduces one cohesive `MonthAggregate` loader that bulk-loads a month's data in ~8 queries — full expense history arrives as `GROUP BY` sums (rows ≈ categories × active months), full transaction rows only for a two-month window — and computes all aggregates (including rollover, as an iterative memoized fold) in memory; `reports`/`budgets` services become thin orchestrators over it, with response schemas unchanged. Frontend introduces one `QueryBoundary` component that owns async-state selection against TanStack Query v5 semantics (data-first: a failed background refetch never hides loaded data), plus upgraded `EmptyState`/skeleton primitives, and migrates the three pages onto it.

**Tech Stack:** Backend — Python, FastAPI, SQLModel/SQLAlchemy, Alembic, pytest, `uv`. Frontend — Next.js 16, React 19, TanStack Query v5, Tailwind v4, Vitest + Testing Library, Biome, **pnpm (ADR-0003 — never npm)**.

## Global Constraints

- Backend tests run on in-memory SQLite; production runs Postgres. **No engine-specific SQL.** Month bucketing uses SQLAlchemy `extract("year"/"month", ...)`, which compiles to `EXTRACT` on Postgres and `strftime` on SQLite. No recursive CTEs, no raw `strftime`/`to_char`.
- **API response contracts do not change** (`MonthlyReportOut`, `SafeToSpendOut`, `BudgetLineOut`, `CommittedItemOut` in `backend/src/quaestor/api/schemas.py`).
- Pure calculators in `backend/src/quaestor/domain/rules.py` (`envelope_status_calc`, `safe_to_spend_calc`) are not modified.
- `frontend/ui/` is app-agnostic (ADR-0002): it must not import app/domain code or `@tanstack/react-query`. `QueryBoundary` and app skeletons live in `frontend/components/`.
- Backend test command: `cd backend && uv run pytest -q`. Frontend test command: `cd frontend && pnpm test` (`vitest run`). Frontend lint/format: `cd frontend && pnpm check` (Biome). **ADR-0003: pnpm is the sole frontend package manager — no `npm`/`npx` anywhere in this plan's execution.**
- The backend has **no linter** (dev deps are pytest only) — when a task says to clean up unused imports, do it by hand and rely on `uv run pytest -q` catching import errors.
- Rollover semantics must stay identical to the current recursion in `services/budgets.py::_available`: `available(m) = 0` when `assigned(m)==0 and spent(m)==0` (and this month passes **no** rollover forward — the gap reset), else `max(available(prev_month), 0) + assigned(m) - spent(m)`.
- **Known, accepted linearities** (documented in the spec; not bugs): one FX lookup per non-COP recurring due date (`_resolve_fx`), one query per active goal (`goals_progress`), one account lookup per account with pending items. The query-count seeds include recurring items and goals so the asserted bounds cover these paths.

---

## Phase A — Backend: bounded read path

### Task A1: Record ADRs

**Files:**
- Create: `docs/adr/00NN-bounded-query-read-path.md` (number auto-assigned)
- Create: `docs/adr/00NN-frontend-async-state-contract.md` (number auto-assigned)
- Modify: `docs/adr/README.md` (index rows, updated by the script)

**Interfaces:**
- Consumes: nothing.
- Produces: two accepted ADRs referenced by later tasks.

- [ ] **Step 1: Generate the backend ADR file**

Run (the adr skill's documented invocation is `uv run`, not bare `python` — macOS may have no `python` on PATH):
```bash
cd /Users/angelozdev/me/quaestor && \
  uv run .claude/skills/adr/scripts/new_adr.py "Bounded-query read path for monthly aggregates"
```
Expected: prints the created path under `docs/adr/`, e.g. `docs/adr/0028-bounded-query-read-path-for-monthly-aggregates.md`.

- [ ] **Step 2: Fill the backend ADR**

Edit the generated file so the sections read:
- **Context:** The running API points at remote Render Postgres, so every distinct SELECT is a network round-trip. The dominant cost is `services/budgets.py::_available` recursing month-by-month (2 queries per frame per category); `list_budgets` runs it per category, `reports.py::_envelope_lines` re-runs `budget_status` (recursion included) per budget, `safe_to_spend::_sum_overspend` walks it again, and `_has_envelope` issues one query per recurring/planned/unbudgeted transaction. (Repeated `session.get(Category, id)` in loops is mostly served by SQLAlchemy's per-Session identity map — it is *not* the driver.) `monthly_report` composes all of it → multi-second hangs.
- **Decision:** Load a month's data via one `MonthAggregate` unit in a fixed ~8 queries: expense history as one `GROUP BY (category_id, year, month)` sum query (engine-agnostic via SQLAlchemy `extract`), full transaction rows only for the two-month window `[prev month, report month]`, plus categories/groups/budgets/recurring/planned. Rollover becomes an iterative, memoized forward fold over in-memory sums — identical semantics, including the gap-month reset. Services orchestrate over it; response schemas and pure calculators are unchanged. One supporting index: `Transaction(type, status, date)`.
- **Alternatives rejected:** (1) SQL-native recursive-CTE rollover — breaks the in-memory SQLite test suite and couples logic to the engine. (2) Materialized/cached monthly snapshots — adds cache-invalidation coupling; premature. (3) Loading all transaction rows into memory — replaces unbounded query count with unbounded row transfer.
- **Consequences:** Read-path query count becomes O(1) in transactions and months of history; row transfer is bounded by categories × active months plus two months of rows. Query-count tests (seeded with multi-month budgets, goals, and recurring items) guard regression. Known linearities remain in small user-curated sets: FX per non-COP due date, one query per goal, pendings per account. `budget_status` (write path: `PUT /api/budgets`, MCP planning tool) now costs a fixed ~8 queries versus 3 + 2×(active months) before — a wash or win beyond ~2 months of history. Honest limitation: the ~8 loads run under READ COMMITTED as separate statements, so a concurrent write (ADR-0024) can skew one aggregate against another within one response; accepted for this app and recorded here.

- [ ] **Step 3: Generate and fill the frontend ADR**

Run:
```bash
cd /Users/angelozdev/me/quaestor && \
  uv run .claude/skills/adr/scripts/new_adr.py "Frontend async-state contract via QueryBoundary"
```
Then edit it: **Context** — pages hand-roll `isPending`/`isError`/`data`; `budgets/page.tsx` forgot the loading branch and rendered blank; reports sections vanish on `length === 0`; `EmptyState` is bare text; the dashboard duplicates `Skeleton` and renders "No disponible" for an error. **Decision** — a single `components/query-boundary.tsx` owns state selection against TanStack Query v5 semantics: data-first (data present → render it; if `isError` too, keep data visible and show a compact retry alert — a failed background refetch must not destroy visible data), else error → `ErrorState`+retry, else pending → skeleton after a 150ms anti-flash delay; `EmptyState` gains `icon`/`action`; app-level skeleton variants read clearly in dark mode; lives in `components/` because `ui/` is app-agnostic (ADR-0002). **Scope** — budgets/reports/dashboard migrate now; remaining pages and `ToPayWidget` migrate incrementally (convention, not mechanical enforcement). **Consequences** — migrated pages cannot forget a state; error isolation is per-query; the `month` filter stays in `useState` (moving it to the URL is follow-up under ADR-0027).

- [ ] **Step 4: Set both ADRs to Accepted and commit**

In each ADR change status `proposed` → `accepted`, and update the matching row in `docs/adr/README.md`.
```bash
cd /Users/angelozdev/me/quaestor && git add docs/adr && \
  git commit -m "docs(adr): bounded read path + frontend async-state contract"
```

---

### Task A2: Query-count helper + characterization baseline

Locks current read-path behavior with golden tests (green against today's code) and adds the query-count context manager later tasks assert on. The seed spans **two months** so rollover semantics are pinned through the refactor.

**Files:**
- Create: `backend/tests/support/__init__.py`
- Create: `backend/tests/support/query_counter.py`
- Create: `backend/tests/api/test_read_path_characterization.py`

**Interfaces:**
- Produces: `count_queries(engine_or_session) -> contextmanager` yielding an object with `.count: int`. Used by Tasks A3/A4/A5.

- [ ] **Step 1: Write the query-counter helper**

Create `backend/tests/support/__init__.py` (empty file) and `backend/tests/support/query_counter.py`:
```python
"""Test-only SQL query counter via SQLAlchemy's before_cursor_execute event."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session


@dataclass
class _Counter:
    count: int = 0


@contextmanager
def count_queries(target: Engine | Session):
    """Count SQL statements executed on `target`'s engine within the block."""
    engine = target.get_bind() if isinstance(target, Session) else target
    counter = _Counter()

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter.count += 1

    event.listen(engine, "before_cursor_execute", _before)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _before)
```

- [ ] **Step 2: Write the characterization test (seeds via API, asserts exact outputs incl. rollover)**

Create `backend/tests/api/test_read_path_characterization.py`:
```python
"""Golden outputs for the monthly read-path. These must not change through the
MonthAggregate refactor — they pin observable behavior at the API contract,
including rollover across months (May available rolls into June)."""


def _seed(client, auth):
    acc = client.post(
        "/api/accounts",
        json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    grp = client.post(
        "/api/category-groups", json={"name": "Living"}, headers=auth
    ).json()
    food = client.post(
        "/api/categories", json={"name": "Food", "group_id": grp["id"]}, headers=auth
    ).json()
    rent = client.post(
        "/api/categories", json={"name": "Rent", "group_id": grp["id"]}, headers=auth
    ).json()
    # May: assign 100k to Food, spend 60k -> May available 40k rolls into June.
    client.put(
        "/api/budgets",
        json={"category_id": food["id"], "year_month": "2026-05", "amount_assigned": 100_000},
        headers=auth,
    )
    client.post(
        "/api/transactions",
        json={
            "type": "expense", "account_id": acc["id"], "amount": 60_000,
            "currency": "COP", "date": "2026-05-15", "category_id": food["id"],
            "payee": "seed",
        },
        headers=auth,
    )
    # June: expenses + income + Food budget.
    for cat_id, amount, day in [
        (food["id"], 50_000, "05"),
        (food["id"], 30_000, "12"),
        (rent["id"], 800_000, "01"),
    ]:
        client.post(
            "/api/transactions",
            json={
                "type": "expense", "account_id": acc["id"], "amount": amount,
                "currency": "COP", "date": f"2026-06-{day}", "category_id": cat_id,
                "payee": "seed",
            },
            headers=auth,
        )
    client.post(
        "/api/transactions",
        json={
            "type": "income", "account_id": acc["id"], "amount": 2_000_000,
            "currency": "COP", "date": "2026-06-02", "payee": "Salary",
        },
        headers=auth,
    )
    client.put(
        "/api/budgets",
        json={"category_id": food["id"], "year_month": "2026-06", "amount_assigned": 100_000},
        headers=auth,
    )
    return {"food": food["id"], "rent": rent["id"]}


def test_report_totals_and_sections_are_stable(client, auth):
    _seed(client, auth)
    body = client.get("/api/reports", params={"month": "2026-06"}, headers=auth).json()
    assert body["income"] == 2_000_000
    assert body["expense"] == 880_000
    assert body["net"] == 1_120_000
    by_cat = {c["category"]: c["total"] for c in body["by_category"]}
    assert by_cat == {"Food": 80_000, "Rent": 800_000}
    by_group = {g["group"]: g["total"] for g in body["by_group"]}
    assert by_group == {"Living": 880_000}


def test_safe_to_spend_is_stable(client, auth):
    _seed(client, auth)
    sts = client.get(
        "/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth
    ).json()
    assert sts["year_month"] == "2026-06"
    assert sts["assigned_envelopes"] == 100_000


def test_list_budgets_pins_rollover(client, auth):
    ids = _seed(client, auth)
    lines = client.get(
        "/api/budgets", params={"month": "2026-06"}, headers=auth
    ).json()
    food = next(l for l in lines if l["category_id"] == ids["food"])
    assert food["assigned"] == 100_000
    assert food["spent"] == 80_000
    assert food["rollover_in"] == 40_000  # May: 100k assigned - 60k spent
    assert food["available"] == 60_000    # 40k rollover + 100k - 80k
    assert food["status"] == "under"
```

- [ ] **Step 3: Run the characterization tests against current code**

Run: `cd backend && uv run pytest tests/api/test_read_path_characterization.py -v`
Expected: PASS (they characterize today's behavior). If any assertion fails, correct the expected number to match current output — do not change product code in this task.

- [ ] **Step 4: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/tests/support backend/tests/api/test_read_path_characterization.py && \
  git commit -m "test(reports): characterization baseline (incl. rollover) + query-count helper"
```

---

### Task A3: `MonthAggregate` loader

The cohesive data-loading unit. History arrives as `GROUP BY` sums; full rows only for the two-month window; rollover is an iterative memoized fold.

**Files:**
- Create: `backend/src/quaestor/services/month_aggregate.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_month_aggregate.py`

**Interfaces:**
- Consumes: `count_queries` from Task A2.
- Produces:
  - `load_month_aggregate(session: Session, year_month: str) -> MonthAggregate`
  - `MonthAggregate` with fields `year_month, start, end, categories: dict[int, Category], groups: dict[int, CategoryGroup], budgets_month: list[Budget], budgeted_category_ids: frozenset[int], active_recurring: list[RecurringItem], month_planned_expense: list[Transaction]` and methods `category(id)`, `group_name(id)`, `assigned(cat_id, ym)`, `spent_for_budget(cat_id, ym)`, `available(cat_id, ym)`, `posted_in_month(ym, tx_type)` (valid only for the report month and its previous month), `totals_for(ym) -> tuple[int,int,int]` (same validity), `month_expense() -> list[Transaction]`, `month_income() -> list[Transaction]`.

- [ ] **Step 1: Write the loader unit tests (rollover, gap reset, bounded query count)**

Create `backend/tests/services/__init__.py` (empty) and `backend/tests/services/test_month_aggregate.py`:
```python
from datetime import date
from decimal import Decimal

from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    Account, AccountType, Budget, Category, Transaction, TxStatus, TxType,
)
from quaestor.services.month_aggregate import load_month_aggregate
from tests.support.query_counter import count_queries

import pytest
from sqlmodel import Session


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s


def _expense(acc_id, cat_id, d, amount):
    return Transaction(
        date=d, type=TxType.expense, status=TxStatus.posted, amount=amount,
        currency="COP", fx_rate=Decimal("1"), to_base=amount, account_id=acc_id,
        category_id=cat_id, payee="seed",
    )


def _setup(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    cat = Category(name="Food")
    session.add(acc); session.add(cat); session.commit()
    session.refresh(acc); session.refresh(cat)
    return acc, cat


def test_rollover_folds_forward_without_recursion_queries(session):
    acc, cat = _setup(session)
    # May: assign 100k, spend 60k -> available 40k
    session.add(Budget(category_id=cat.id, year_month="2026-05", amount_assigned=100_000))
    session.add(_expense(acc.id, cat.id, date(2026, 5, 10), 60_000))
    # Jun: assign 100k, spend 30k, rollover_in 40k -> available 110k
    session.add(Budget(category_id=cat.id, year_month="2026-06", amount_assigned=100_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 10), 30_000))
    session.commit()

    agg = load_month_aggregate(session, "2026-06")
    assert agg.assigned(cat.id, "2026-06") == 100_000
    assert agg.spent_for_budget(cat.id, "2026-06") == 30_000
    assert agg.available(cat.id, "2026-05") == 40_000
    assert agg.available(cat.id, "2026-06") == 110_000


def test_gap_month_resets_rollover(session):
    """A month with no assignment and no spending yields 0 and does NOT pass
    rollover forward — identical to the current recursion's base case."""
    acc, cat = _setup(session)
    session.add(Budget(category_id=cat.id, year_month="2026-04", amount_assigned=100_000))
    session.add(_expense(acc.id, cat.id, date(2026, 4, 10), 60_000))
    # 2026-05: gap (no budget, no spending)
    session.add(Budget(category_id=cat.id, year_month="2026-06", amount_assigned=50_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 10), 10_000))
    session.commit()

    agg = load_month_aggregate(session, "2026-06")
    assert agg.available(cat.id, "2026-04") == 40_000
    assert agg.available(cat.id, "2026-05") == 0
    assert agg.available(cat.id, "2026-06") == 40_000  # gap reset: 0 + 50k - 10k


def test_load_issues_bounded_query_count(session):
    acc, cat = _setup(session)
    for i in range(200):
        session.add(_expense(acc.id, cat.id, date(2026, 6, 1 + (i % 27)), 1_000))
    session.commit()
    with count_queries(session) as c:
        agg = load_month_aggregate(session, "2026-06")
        # Force full in-memory computation:
        agg.totals_for("2026-06")
        agg.available(cat.id, "2026-06")
    assert c.count <= 10, f"expected bounded loads, got {c.count}"


def test_excluded_category_has_zero_budget_spend(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    cat = Category(name="Transfers", exclude_from_budget=True)
    session.add(acc); session.add(cat); session.commit()
    session.refresh(acc); session.refresh(cat)
    session.add(_expense(acc.id, cat.id, date(2026, 6, 3), 500_000))
    session.commit()
    agg = load_month_aggregate(session, "2026-06")
    assert agg.spent_for_budget(cat.id, "2026-06") == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_month_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.services.month_aggregate'`.

- [ ] **Step 3: Implement `MonthAggregate`**

Create `backend/src/quaestor/services/month_aggregate.py`:
```python
"""Single-pass month loader: bulk-load once, compute aggregates in memory.

Replaces the per-category rollover recursion and per-budget query fanout in
the report/budget read-path. Expense history is loaded as GROUP BY sums
(rows bounded by categories × active months); full transaction rows are
loaded only for the report month and its previous month. All accessors read
memory — no DB access after `load_month_aggregate`. Response contracts are
unchanged; callers orchestrate over this unit.

Consistency: the ~8 loads run as separate statements (READ COMMITTED on
Postgres — each sees its own snapshot). A concurrent write landing mid-load
can skew one aggregate against another within a single response. Accepted
for this app; see the bounded-read-path ADR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date

from sqlalchemy import extract, func
from sqlmodel import Session, select

from ..domain.models import (
    Budget, Category, CategoryGroup, RecurringItem, Transaction, TxStatus, TxType,
)
from ..domain.rules import month_bounds, prev_year_month


def _ym(d: Date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _next_year_month(year_month: str) -> str:
    year, month = int(year_month[:4]), int(year_month[5:7])
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


@dataclass
class MonthAggregate:
    year_month: str
    start: Date
    end: Date
    categories: dict[int, Category]
    groups: dict[int, CategoryGroup]
    budgets_month: list[Budget]
    budgeted_category_ids: frozenset[int]
    active_recurring: list[RecurringItem]
    month_planned_expense: list[Transaction]
    # Full rows only for [previous month, report month]:
    _window_expense: list[Transaction]
    _window_income: list[Transaction]
    # Full history as sums, from one GROUP BY query:
    _spent_by_cat_month: dict[tuple[int | None, str], int]
    _assigned_by_cat_month: dict[tuple[int, str], int]
    _first_active: dict[int, str]
    _available_cache: dict[int, dict[str, int]] = field(default_factory=dict)

    # --- lookups (no DB) ---
    def category(self, category_id: int | None) -> Category | None:
        return self.categories.get(category_id) if category_id is not None else None

    def group_name(self, category_id: int | None) -> str | None:
        cat = self.category(category_id)
        if cat is None or cat.group_id is None:
            return None
        grp = self.groups.get(cat.group_id)
        return grp.name if grp is not None else None

    def assigned(self, category_id: int, year_month: str) -> int:
        return self._assigned_by_cat_month.get((category_id, year_month), 0)

    def spent_for_budget(self, category_id: int, year_month: str) -> int:
        cat = self.categories.get(category_id)
        if cat is not None and (cat.exclude_from_budget or cat.exclude_from_totals):
            return 0
        return self._spent_by_cat_month.get((category_id, year_month), 0)

    def available(self, category_id: int, year_month: str) -> int:
        """Iterative forward fold with memo. Same semantics as the old
        `_available` recursion, including the gap-month reset (an inactive
        month yields 0 and passes no rollover forward)."""
        cache = self._available_cache.setdefault(category_id, {})
        cached = cache.get(year_month)
        if cached is not None:
            return cached
        start = self._first_active.get(category_id)
        if start is None or year_month < start:
            return 0
        prev_avail = 0
        ym = start
        while True:
            assigned = self.assigned(category_id, ym)
            spent = self.spent_for_budget(category_id, ym)
            if assigned == 0 and spent == 0:
                avail = 0
            else:
                avail = max(prev_avail, 0) + assigned - spent
            cache[ym] = avail
            if ym == year_month:
                return avail
            prev_avail = avail
            ym = _next_year_month(ym)

    # --- month views (no DB; valid ONLY for the report month and its previous month) ---
    def posted_in_month(self, year_month: str, tx_type: TxType) -> list[Transaction]:
        source = (
            self._window_expense if tx_type == TxType.expense else self._window_income
        )
        kept: list[Transaction] = []
        for tx in source:
            if _ym(tx.date) != year_month:
                continue
            cat = self.category(tx.category_id)
            if cat is not None and cat.exclude_from_totals:
                continue
            kept.append(tx)
        return kept

    def month_expense(self) -> list[Transaction]:
        return self.posted_in_month(self.year_month, TxType.expense)

    def month_income(self) -> list[Transaction]:
        return self.posted_in_month(self.year_month, TxType.income)

    def totals_for(self, year_month: str) -> tuple[int, int, int]:
        income = sum(t.to_base for t in self.posted_in_month(year_month, TxType.income))
        expense = sum(t.to_base for t in self.posted_in_month(year_month, TxType.expense))
        return income, expense, income - expense


def load_month_aggregate(session: Session, year_month: str) -> MonthAggregate:
    start, end = month_bounds(year_month)
    prev_start, _ = month_bounds(prev_year_month(year_month))

    categories = {c.id: c for c in session.exec(select(Category)).all()}
    groups = {g.id: g for g in session.exec(select(CategoryGroup)).all()}

    # Full expense history as sums — engine-agnostic month bucketing via
    # extract() (EXTRACT on Postgres, strftime-backed on SQLite).
    spent_rows = session.exec(
        select(
            Transaction.category_id,
            extract("year", Transaction.date),
            extract("month", Transaction.date),
            func.sum(Transaction.to_base),
        )
        .where(
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
        )
        .group_by(
            Transaction.category_id,
            extract("year", Transaction.date),
            extract("month", Transaction.date),
        )
    ).all()
    spent_by_cat_month: dict[tuple[int | None, str], int] = {
        (cat_id, f"{int(y):04d}-{int(m):02d}"): int(total)
        for cat_id, y, m, total in spent_rows
    }

    def _window(tx_type: TxType) -> list[Transaction]:
        return list(
            session.exec(
                select(Transaction).where(
                    Transaction.type == tx_type,
                    Transaction.status == TxStatus.posted,
                    Transaction.date >= prev_start,
                    Transaction.date <= end,
                )
            ).all()
        )

    window_expense = _window(TxType.expense)
    window_income = _window(TxType.income)

    budgets_all = list(session.exec(select(Budget)).all())
    active_recurring = list(
        session.exec(
            select(RecurringItem).where(RecurringItem.active == True)  # noqa: E712
        ).all()
    )
    month_planned_expense = list(
        session.exec(
            select(Transaction).where(
                Transaction.type == TxType.expense,
                Transaction.status == TxStatus.planned,
                Transaction.recurring_id == None,  # noqa: E711
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).all()
    )

    assigned_by_cat_month = {
        (b.category_id, b.year_month): b.amount_assigned for b in budgets_all
    }
    budgets_month = [b for b in budgets_all if b.year_month == year_month]

    first_active: dict[int, str] = {}
    for cat_id, ym in list(spent_by_cat_month) + list(assigned_by_cat_month):
        if cat_id is None:
            continue
        if cat_id not in first_active or ym < first_active[cat_id]:
            first_active[cat_id] = ym

    return MonthAggregate(
        year_month=year_month, start=start, end=end,
        categories=categories, groups=groups,
        budgets_month=budgets_month,
        budgeted_category_ids=frozenset(b.category_id for b in budgets_month),
        active_recurring=active_recurring,
        month_planned_expense=month_planned_expense,
        _window_expense=window_expense,
        _window_income=window_income,
        _spent_by_cat_month=spent_by_cat_month,
        _assigned_by_cat_month=assigned_by_cat_month,
        _first_active=first_active,
    )
```
(8 loads total: categories, groups, history GROUP BY, window expense, window income, budgets, recurring, planned — under the test's ≤ 10 bound. If `extract` misbehaves on either engine the loader unit tests catch it immediately.)

- [ ] **Step 4: Run the loader tests to verify they pass**

Run: `cd backend && uv run pytest tests/services/test_month_aggregate.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/src/quaestor/services/month_aggregate.py backend/tests/services && \
  git commit -m "feat(services): MonthAggregate single-pass month loader (GROUP BY history + window rows)"
```

---

### Task A4: Refactor `budgets.py` onto `MonthAggregate`

Replace recursive/N+1 helpers with in-memory computation. Public signatures unchanged. The seed includes recurring items so the bound covers the documented FX/recurring linearity (COP items resolve FX without a query; the linearity note in the spec covers non-COP).

**Files:**
- Modify: `backend/src/quaestor/services/budgets.py`
- Create: `backend/tests/api/test_budgets_query_count.py`

**Interfaces:**
- Consumes: `load_month_aggregate`, `MonthAggregate` (Task A3); `count_queries` (Task A2).
- Produces: unchanged public functions `safe_to_spend(session, year_month) -> SafeToSpend`, `list_budgets(session, year_month) -> list[BudgetLine]`, `budget_status(session, category_id, year_month) -> BudgetStatus`, `set_budget(...)` (unchanged).

- [ ] **Step 1: Write the query-count test (red)**

Create `backend/tests/api/test_budgets_query_count.py`:
```python
"""The budgets read-path must be bounded regardless of category/month count.

Red rationale (verified against current code): list_budgets runs
budget_status per category (= _assigned 1 + _spent 2 + _available recursion
~2 per active month), so 15 categories × 3 active months ≈ 150+ queries.
safe_to_spend's _has_envelope adds one query per recurring item / planned tx /
unbudgeted posted tx. Both far exceed the bounds below before the refactor.
"""
from tests.support.query_counter import count_queries


def _seed(client, auth, n_categories=15):
    acc = client.post(
        "/api/accounts", json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    # Recurring items (COP -> no FX queries) so the bound covers the
    # recurring-scan path, not a seed that dodges it.
    for name, tx_type, amount in [("Salary", "income", 2_000_000), ("Rent", "expense", 800_000)]:
        client.post(
            "/api/recurring",
            json={
                "name": name, "type": tx_type, "mode": "manual", "amount": amount,
                "currency": "COP", "account_id": acc["id"], "interval_unit": "month",
                "interval_count": 1, "start_date": "2026-01-01",
            },
            headers=auth,
        )
    for i in range(n_categories):
        cat = client.post(
            "/api/categories", json={"name": f"Cat {i}"}, headers=auth
        ).json()
        for m in ("2026-04", "2026-05", "2026-06"):
            client.put(
                "/api/budgets",
                json={"category_id": cat["id"], "year_month": m, "amount_assigned": 10_000},
                headers=auth,
            )
            client.post(
                "/api/transactions",
                json={
                    "type": "expense", "account_id": acc["id"], "amount": 5_000,
                    "currency": "COP", "date": f"{m}-10", "category_id": cat["id"],
                    "payee": "seed",
                },
                headers=auth,
            )


def test_list_budgets_query_count_is_bounded(client, auth, engine):
    _seed(client, auth, n_categories=15)
    with count_queries(engine) as c:
        r = client.get("/api/budgets", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 15, f"list_budgets issued {c.count} queries"


def test_safe_to_spend_query_count_is_bounded(client, auth, engine):
    _seed(client, auth, n_categories=15)
    with count_queries(engine) as c:
        r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 20, f"safe_to_spend issued {c.count} queries"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_budgets_query_count.py -v`
Expected: FAIL on both tests, with counts in the hundreds (per-category recursion + per-item `_has_envelope`). If either test PASSES here, stop — the seed is not exercising the N+1 and must be fixed before proceeding (a green "red" test guards nothing).

- [ ] **Step 3: Rewrite `budgets.py` read-path over `MonthAggregate`**

In `backend/src/quaestor/services/budgets.py`, keep `set_budget` and `_validate_year_month` as-is. Replace the read helpers and public read functions with agg-based versions. Add the import and replace everything from `_assigned` through `list_budgets`:

```python
from .month_aggregate import MonthAggregate, load_month_aggregate
```

Replace the body from `_assigned` (line ~67) to end of `list_budgets` with:
```python
def _income_forecast(session: Session, agg: MonthAggregate) -> int:
    # Known linearity (see spec): one _resolve_fx per non-COP due date.
    # COP items resolve to Decimal(1) without touching the DB.
    total = 0
    for item in agg.active_recurring:
        if item.type != TxType.income:
            continue
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, agg.start, agg.end,
        ):
            rate = _tx._resolve_fx(session, item.currency, d, None)
            total += to_base_cents(item.amount, rate)
    return total


def _committed(session: Session, agg: MonthAggregate) -> tuple[int, list]:
    total = 0
    breakdown: list[CommittedItem] = []
    for item in agg.active_recurring:
        if item.type != TxType.expense:
            continue
        if item.category_id is not None and item.category_id in agg.budgeted_category_ids:
            continue
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, agg.start, agg.end,
        ):
            rate = _tx._resolve_fx(session, item.currency, d, None)
            amount = to_base_cents(item.amount, rate)
            total += amount
            breakdown.append(CommittedItem(kind="recurring", name=item.name, date=d, amount=amount))
    for tx in agg.month_planned_expense:
        if tx.category_id is not None and tx.category_id in agg.budgeted_category_ids:
            continue
        total += tx.to_base
        breakdown.append(CommittedItem(kind="planned", name=tx.payee, date=tx.date, amount=tx.to_base))
    return total, breakdown


def _unbudgeted_spending(agg: MonthAggregate) -> int:
    total = 0
    for tx in agg.month_expense():
        if tx.recurring_id is not None:
            continue
        if tx.category_id is None:
            total += tx.to_base
            continue
        cat = agg.category(tx.category_id)
        if cat is not None and (cat.exclude_from_budget or cat.exclude_from_totals):
            continue
        if tx.category_id in agg.budgeted_category_ids:
            continue
        total += tx.to_base
    return total


def _sum_assigned(agg: MonthAggregate) -> int:
    return sum(b.amount_assigned for b in agg.budgets_month)


def _sum_overspend(agg: MonthAggregate) -> int:
    total = 0
    for b in agg.budgets_month:
        spent = agg.spent_for_budget(b.category_id, agg.year_month)
        rollover_in = max(agg.available(b.category_id, prev_year_month(agg.year_month)), 0)
        over = spent - (b.amount_assigned + rollover_in)
        if over > 0:
            total += over
    return total


def _safe_to_spend(session: Session, agg: MonthAggregate) -> SafeToSpend:
    income = _income_forecast(session, agg)
    committed, breakdown = _committed(session, agg)
    assigned = _sum_assigned(agg)
    unbudgeted = _unbudgeted_spending(agg)
    overspend = _sum_overspend(agg)
    free = safe_to_spend_calc(income, committed, assigned, unbudgeted, overspend)
    return SafeToSpend(
        year_month=agg.year_month, income_forecast=income, committed=committed,
        assigned_envelopes=assigned, free=free, committed_breakdown=breakdown,
    )


def safe_to_spend(session: Session, year_month: str) -> SafeToSpend:
    """Global safe-to-spend headline + breakdown (ADR-003/005/014/016)."""
    _validate_year_month(year_month)
    return _safe_to_spend(session, load_month_aggregate(session, year_month))


def _status(agg: MonthAggregate, category_id: int) -> BudgetStatus:
    assigned = agg.assigned(category_id, agg.year_month)
    spent = agg.spent_for_budget(category_id, agg.year_month)
    rollover_in = max(agg.available(category_id, prev_year_month(agg.year_month)), 0)
    return envelope_status_calc(category_id, agg.year_month, assigned, rollover_in, spent)


def budget_status(session: Session, category_id: int, year_month: str) -> BudgetStatus:
    """Envelope status with rollover for a category/month.

    Write-path note: callers (PUT /api/budgets, MCP planning) now pay a fixed
    ~8-query aggregate load instead of 3 + 2×(active months) recursion.
    """
    _validate_year_month(year_month)
    if session.get(Category, category_id) is None:
        raise NotFound(f"category {category_id} not found")
    return _status(load_month_aggregate(session, year_month), category_id)


def _budget_lines(agg: MonthAggregate) -> list[BudgetLine]:
    lines: list[BudgetLine] = []
    eligible = [
        c for c in agg.categories.values()
        if not c.archived and not c.exclude_from_budget
    ]
    for cat in sorted(eligible, key=lambda c: c.id):
        st = _status(agg, cat.id)
        lines.append(
            BudgetLine(
                category_id=cat.id, category_name=cat.name, assigned=st.assigned,
                rollover_in=st.rollover_in, spent=st.spent, available=st.available,
                pct_used=st.pct_used, status=st.status,
            )
        )
    return lines


def list_budgets(session: Session, year_month: str) -> list[BudgetLine]:
    """One envelope line per budget-eligible category for the month."""
    _validate_year_month(year_month)
    return _budget_lines(load_month_aggregate(session, year_month))
```

Then update the module imports at the top by hand (no backend linter exists): remove now-unused `Budget`, `RecurringItem`, `TxStatus`, `month_bounds` if no longer referenced (keep `Category`, `TxType`), and keep `CommittedItem`, `BudgetStatus`, `BudgetLine`, `SafeToSpend` from `domain.dtos`, plus `NotFound`, `ValidationError`, `to_base_cents`, `due_dates`, `envelope_status_calc`, `prev_year_month`, `safe_to_spend_calc`, and `from . import transactions as _tx`. `uv run pytest -q` catches any import error.

- [ ] **Step 4: Run characterization + query-count + existing budget tests**

Run:
```bash
cd backend && uv run pytest tests/api/test_read_path_characterization.py tests/api/test_budgets_query_count.py tests/api/test_budgets.py -v
```
Expected: PASS (characterization unchanged — including the pinned rollover values, query-count now bounded, existing budget suite green).

- [ ] **Step 5: Full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/src/quaestor/services/budgets.py backend/tests/api/test_budgets_query_count.py && \
  git commit -m "perf(budgets): compute read-path over MonthAggregate (kills rollover recursion + per-item queries)"
```

---

### Task A5: Refactor `reports.py` onto `MonthAggregate`

`_goal_lines`, `_balance_lines`, and `_pending_lines` intentionally stay service-based — their cost is linear in goals/accounts (small user-curated sets; documented in the spec), and the seed includes goals so the bound covers that path honestly.

**Files:**
- Modify: `backend/src/quaestor/services/reports.py`
- Create: `backend/tests/api/test_reports_query_count.py`

**Interfaces:**
- Consumes: `load_month_aggregate`, `MonthAggregate` (A3); `budgets._safe_to_spend`, `budgets._status` (A4); `count_queries` (A2).
- Produces: unchanged public `monthly_report(session, month, *, today=None) -> MonthlyReport`.

- [ ] **Step 1: Write the query-count test (red)**

Create `backend/tests/api/test_reports_query_count.py`:
```python
"""The monthly report must be bounded regardless of transaction count.

Red rationale (verified against current code): _envelope_lines runs
budget_status per budget (recursion included: ~9 queries per budget with two
active months), safe_to_spend inside the report repeats the overspend walk,
and _has_envelope fires per item. With 6 budgeted categories over two months
plus goals, the current count lands in the hundreds — far above the bound.

NOTE on the bound: if this fails AFTER the refactor, record the actual count
and set the bound to actual + 2 — it must stay far below the pre-refactor
count (document the observed numbers in the commit message). Goals cost one
query each by design (see spec: known linearities).
"""
from tests.support.query_counter import count_queries


def test_report_query_count_is_bounded(client, auth, engine):
    acc = client.post(
        "/api/accounts", json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    savings = client.post(
        "/api/accounts", json={"name": "Savings", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    for g in range(3):
        client.post(
            "/api/goals",
            json={"name": f"Goal {g}", "monthly_amount": 100_000,
                  "savings_account_id": savings["id"]},
            headers=auth,
        )
    cats = [
        client.post("/api/categories", json={"name": f"Cat {i}"}, headers=auth).json()
        for i in range(6)
    ]
    # Budgets across two months -> _envelope_lines + rollover recursion are
    # genuinely exercised pre-refactor (this is what makes the test red).
    for cat in cats:
        for m in ("2026-05", "2026-06"):
            client.put(
                "/api/budgets",
                json={"category_id": cat["id"], "year_month": m, "amount_assigned": 50_000},
                headers=auth,
            )
    for i in range(120):
        month = "2026-05" if i % 2 else "2026-06"
        client.post(
            "/api/transactions",
            json={
                "type": "expense", "account_id": acc["id"], "amount": 1_000,
                "currency": "COP", "date": f"{month}-{1 + (i % 27):02d}",
                "category_id": cats[i % 6]["id"], "payee": "seed",
            },
            headers=auth,
        )
    with count_queries(engine) as c:
        r = client.get("/api/reports", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 25, f"monthly_report issued {c.count} queries"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_reports_query_count.py -v`
Expected: FAIL with a count in the hundreds (per-budget `budget_status` recursion across two months + `_has_envelope` per item + goals). If it PASSES here, stop and fix the seed — a green "red" test guards nothing.

- [ ] **Step 3: Rewrite `reports.py` aggregation over `MonthAggregate`**

In `backend/src/quaestor/services/reports.py`: remove `_posted_for_totals`, `_totals`, `_group_name` (moved into the aggregate). Replace `_usd_share`, `_category_sections`, `_group_sections`, `_drift`, `_envelope_lines`, and `monthly_report` with agg-based versions. Keep `_goal_lines`, `_balance_lines`, `_pending_lines` untouched (documented linearity — see task intro). Add imports:
```python
from .month_aggregate import MonthAggregate, load_month_aggregate
from .budgets import _safe_to_spend, _status as _budget_status_from_agg
```
Reusing `budgets._status` (agg-based) keeps envelope rollover and status semantics identical to the budgets service — no reinventing the "over"/"under" rule.
New bodies:
```python
def _usd_share(expenses: list[Transaction], expense_total: int) -> float:
    if expense_total == 0:
        return 0.0
    usd = sum(t.to_base for t in expenses if t.currency == "USD")
    return usd / expense_total


def _category_sections(
    agg: MonthAggregate, expenses: list[Transaction], expense_total: int
) -> list[CategorySection]:
    buckets: dict[int | None, int] = {}
    for tx in expenses:
        buckets[tx.category_id] = buckets.get(tx.category_id, 0) + tx.to_base
    sections: list[CategorySection] = []
    for cat_id, total in buckets.items():
        if cat_id is None:
            name, group = "Uncategorized", None
        else:
            cat = agg.category(cat_id)
            name = cat.name if cat is not None else f"category {cat_id}"
            group = agg.group_name(cat_id)
        pct = (total / expense_total * 100) if expense_total > 0 else 0.0
        sections.append(CategorySection(category=name, group=group, total=total, pct=pct))
    sections.sort(key=lambda s: (-s.total, s.category))
    return sections


def _group_sections(
    agg: MonthAggregate, expenses: list[Transaction], expense_total: int
) -> list[GroupSection]:
    buckets: dict[str, int] = {}
    for tx in expenses:
        name = agg.group_name(tx.category_id) or "Ungrouped"
        buckets[name] = buckets.get(name, 0) + tx.to_base
    sections = [
        GroupSection(
            group=name, total=total,
            pct=(total / expense_total * 100) if expense_total > 0 else 0.0,
        )
        for name, total in buckets.items()
    ]
    sections.sort(key=lambda s: (-s.total, s.group))
    return sections


def _drift(agg: MonthAggregate, income: int, expense: int, net: int) -> DriftMoM | None:
    prev = prev_year_month(agg.year_month)
    p_income, p_expense, p_net = agg.totals_for(prev)
    if p_income == 0 and p_expense == 0:
        return None

    def pct(curr: int, base: int) -> float | None:
        return ((curr - base) / base * 100) if base != 0 else None

    return DriftMoM(
        prev_month=prev,
        income_abs=income - p_income, income_pct=pct(income, p_income),
        expense_abs=expense - p_expense, expense_pct=pct(expense, p_expense),
        net_abs=net - p_net, net_pct=pct(net, p_net),
    )


def _envelope_lines(agg: MonthAggregate) -> tuple[list[EnvelopeLine], EnvelopesSummary]:
    lines: list[EnvelopeLine] = []
    for b in agg.budgets_month:
        st = _budget_status_from_agg(agg, b.category_id)
        cat = agg.category(b.category_id)
        name = cat.name if cat is not None else f"category {b.category_id}"
        lines.append(
            EnvelopeLine(
                category=name, allocated=st.assigned, rollover_in=st.rollover_in,
                spent=st.spent, available=st.available, status=st.status,
            )
        )
    lines.sort(key=lambda e: e.category)
    n_green = sum(1 for e in lines if e.status == "under")
    n_red = sum(1 for e in lines if e.status == "over")
    rollover_generated = sum(max(e.available, 0) for e in lines)
    return lines, EnvelopesSummary(
        n_green=n_green, n_red=n_red, rollover_generated=rollover_generated
    )
```

Replace `monthly_report` body:
```python
def monthly_report(
    session: Session, month: str, *, today: Date | None = None
) -> MonthlyReport:
    """Build the retrospective monthly report (data + markdown) for "YYYY-MM"."""
    _validate_month(month)
    if today is None:
        today = Date.today()
    agg = load_month_aggregate(session, month)
    start, end = agg.start, agg.end

    expenses = agg.month_expense()
    income, expense, net = agg.totals_for(month)
    envelopes, envelopes_summary = _envelope_lines(agg)
    report = MonthlyReport(
        month=month,
        income=income, expense=expense, net=net,
        envelopes_summary=envelopes_summary,
        envelopes=envelopes,
        by_category=_category_sections(agg, expenses, expense),
        by_group=_group_sections(agg, expenses, expense),
        goals=_goal_lines(session, today),
        balances=_balance_lines(session),
        drift_mom=_drift(agg, income, expense, net),
        usd_share=_usd_share(expenses, expense),
        pending=_pending_lines(session, start, end),
        safe_to_spend=_safe_to_spend(session, agg),
        markdown="",
    )
    report.markdown = render_markdown(report)
    return report
```

After replacing the bodies, remove now-unused imports in `reports.py` by hand (no backend linter — e.g. `Budget`, `TxStatus`, `CategoryGroup`, `month_bounds`, `select` if no longer referenced; keep `Transaction`, `TxType`, `Account` — still used by `_pending_lines` — and the `report_types` DTOs). The `status` value on each `EnvelopeLine` comes straight from `budgets._status` → `envelope_status_calc`, so it matches the existing type by construction.

- [ ] **Step 4: Run characterization + query-count + existing reports tests**

Run:
```bash
cd backend && uv run pytest tests/api/test_read_path_characterization.py tests/api/test_reports_query_count.py tests/api/test_reports.py -v
```
Expected: PASS. If `test_report_query_count_is_bounded` fails with a small overshoot (e.g. goals/balances internals cost a few more than estimated), apply the bound rule from the test's docstring: set bound = actual + 2 and record both numbers in the commit message.

- [ ] **Step 5: Full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/src/quaestor/services/reports.py backend/tests/api/test_reports_query_count.py && \
  git commit -m "perf(reports): compute monthly report over MonthAggregate"
```

---

### Task A6: Alembic index migration

One index, matched to the queries the refactor actually ships: the history `GROUP BY` filters on `(type, status)` (index prefix) and the window loads filter on `(type, status, date range)` (full index). The earlier candidates `Transaction(category_id)`, `Budget(year_month)`, and `RecurringItem(active, type)` are **dropped**: after A4/A5 no read-path query filters on them (budgets and recurring are loaded unfiltered or near-unfiltered; per-category transaction queries no longer exist).

**Files:**
- Create: `backend/src/quaestor/migrations/versions/0004_read_path_indexes.py` (script location per `alembic.ini`: `%(here)s/src/quaestor/migrations`; existing revisions use hand-set sequential ids `0001`–`0003`)

**Interfaces:**
- Consumes: nothing.
- Produces: the DB index supporting the read-path transaction scans on Postgres.

- [ ] **Step 1: Confirm the migrations directory and current head**

Run:
```bash
cd backend && uv run alembic history | head -5 && uv run alembic current
```
Expected: head is `0003` (`0003_bigint_for_transaction_to_base.py`), versions dir is `backend/src/quaestor/migrations/versions/`.

- [ ] **Step 2: Generate the revision with the repo's sequential id convention**

Run:
```bash
cd backend && uv run alembic revision --rev-id 0004 -m "read path indexes"
```
Expected: creates `backend/src/quaestor/migrations/versions/0004_read_path_indexes.py` (the `--rev-id` keeps the repo's numeric convention; without it alembic generates a hash id, breaking the `0001`–`0003` sequence). Open it and confirm `revision = "0004"`, `down_revision = "0003"`.

- [ ] **Step 3: Fill `upgrade`/`downgrade`**

```python
def upgrade() -> None:
    op.create_index(
        "ix_transaction_type_status_date", "transaction",
        ["type", "status", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_transaction_type_status_date", table_name="transaction")
```
Confirm the table name matches `__tablename__` in `domain/models.py` (`transaction`).

- [ ] **Step 4: Apply locally and verify boot**

Run: `cd backend && uv run alembic upgrade head && uv run pytest tests/api/test_app_boots.py -q`
Expected: migration applies cleanly; app boots.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/src/quaestor/migrations/versions && \
  git commit -m "perf(db): index transaction(type, status, date) for the read path"
```

---

## Phase B — Frontend: async-state contract

### Task B1: Upgrade `EmptyState` (icon + action)

**Files:**
- Modify: `frontend/components/empty-state.tsx`
- Create: `frontend/components/empty-state.test.tsx`

**Interfaces:**
- Produces: `EmptyState({ message, icon?, action? })` where `action?: { label: string; href?: string; onClick?: () => void }`.

- [ ] **Step 1: Write the failing test**

Create `frontend/components/empty-state.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { EmptyState } from "./empty-state"

describe("EmptyState", () => {
  it("renders the message", () => {
    render(<EmptyState message="Sin datos" />)
    expect(screen.getByText("Sin datos")).toBeInTheDocument()
  })

  it("renders an action button that fires onClick", async () => {
    const onClick = vi.fn()
    render(
      <EmptyState message="Nada aún" action={{ label: "Crear", onClick }} />,
    )
    screen.getByRole("button", { name: "Crear" }).click()
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("renders an action link when href is given", () => {
    render(
      <EmptyState message="Nada aún" action={{ label: "Ir", href: "/x" }} />,
    )
    expect(screen.getByRole("link", { name: "Ir" })).toHaveAttribute("href", "/x")
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && pnpm test -- empty-state`
Expected: FAIL (action not supported).

- [ ] **Step 3: Implement**

Replace `frontend/components/empty-state.tsx`:
```tsx
import Link from "next/link"
import type { ReactNode } from "react"

type Action = { label: string; href?: string; onClick?: () => void }

export function EmptyState({
  message,
  icon,
  action,
}: {
  message: string
  icon?: ReactNode
  action?: Action
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      {icon ? <div style={{ color: "var(--muted-foreground)" }}>{icon}</div> : null}
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        {message}
      </p>
      {action ? (
        action.href ? (
          <Link
            href={action.href}
            className="text-xs px-3 py-1.5 rounded-md border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
          >
            {action.label}
          </Link>
        ) : (
          <button
            type="button"
            onClick={action.onClick}
            className="text-xs px-3 py-1.5 rounded-md border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
          >
            {action.label}
          </button>
        )
      ) : null}
    </div>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && pnpm test -- empty-state`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add frontend/components/empty-state.tsx frontend/components/empty-state.test.tsx && \
  git commit -m "feat(ui): EmptyState supports icon + action CTA"
```

---

### Task B2: App-level skeleton variants (dark-visible, content-shaped)

**Files:**
- Create: `frontend/components/skeleton.tsx`
- Create: `frontend/components/skeleton.test.tsx`

**Interfaces:**
- Produces: `SkeletonText({ lines?, className? })`, `SkeletonCard({ className? })`, `SkeletonRows({ rows?, className? })`, `SkeletonBlock({ className? })` (free-form shapes, e.g. the dashboard hero). Built on the `ui` `Skeleton`.

- [ ] **Step 1: Write the failing test**

Create `frontend/components/skeleton.test.tsx`:
```tsx
import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { SkeletonBlock, SkeletonRows, SkeletonText } from "./skeleton"

describe("skeleton variants", () => {
  it("renders the requested number of text lines", () => {
    const { container } = render(<SkeletonText lines={3} />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(3)
  })

  it("renders the requested number of rows", () => {
    const { container } = render(<SkeletonRows rows={5} />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(5)
  })

  it("renders a free-form block", () => {
    const { container } = render(<SkeletonBlock className="h-14 w-64" />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && pnpm test -- skeleton`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `frontend/components/skeleton.tsx`:
```tsx
import { Skeleton } from "@/ui/components/skeleton"

// Raised-contrast wrapper so skeletons read clearly in dark mode.
const TONE = { background: "var(--muted-foreground)", opacity: 0.14 } as const

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4"
          style={{ ...TONE, width: i === lines - 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  )
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return <Skeleton className={`h-28 w-full rounded-lg ${className}`} style={TONE} />
}

export function SkeletonRows({ rows = 6, className = "" }: { rows?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" style={TONE} />
      ))}
    </div>
  )
}

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return <Skeleton className={className} style={TONE} />
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && pnpm test -- skeleton`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add frontend/components/skeleton.tsx frontend/components/skeleton.test.tsx && \
  git commit -m "feat(ui): dark-visible content-shaped skeleton variants"
```

---

### Task B3: `QueryBoundary` component

State selection against TanStack Query v5 semantics. Key decisions (all from the spec):
- `isPending` (v5 status), **not** `isLoading` — a disabled/paused query is `status: "pending"` with `isLoading: false` in v5, and keying on `isLoading` would render it as a permanent silent blank (the exact bug class this component exists to kill).
- **Data-first:** data present → render it, even when `isError` is true (failed background refetch). In that case a compact inline retry alert renders above the data. The current budgets page keeps data visible next to an error; the boundary must not regress that.
- Anti-flash delay defaults to 150ms and **production pages do not override it to 0** — the delay path itself is unit-tested with fake timers.

**Files:**
- Create: `frontend/components/query-boundary.tsx`
- Create: `frontend/components/query-boundary.test.tsx`

**Interfaces:**
- Consumes: `ErrorState` (existing).
- Produces:
  ```tsx
  QueryBoundary<T>({
    query: { isPending: boolean; isError: boolean; data: T | undefined; refetch: () => void },
    skeleton: ReactNode,
    empty?: { when: (data: T) => boolean; node: ReactNode },
    errorMessage?: string,
    delayMs?: number, // default 150
    children: (data: T) => ReactNode,
  })
  ```
  (`UseQueryResult` from TanStack v5 is structurally assignable to `query` — pages pass the query object straight through.)

- [ ] **Step 1: Write the failing test**

Create `frontend/components/query-boundary.test.tsx`:
```tsx
import { act, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { QueryBoundary } from "./query-boundary"

const base = { isPending: false, isError: false, data: undefined, refetch: vi.fn() }

describe("QueryBoundary", () => {
  it("shows the skeleton immediately when delayMs is 0", () => {
    render(
      <QueryBoundary
        query={{ ...base, isPending: true }}
        skeleton={<div>loading…</div>}
        delayMs={0}
      >
        {() => <div>data</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("loading…")).toBeInTheDocument()
  })

  it("holds the skeleton back for delayMs, then shows it (anti-flash)", () => {
    vi.useFakeTimers()
    try {
      render(
        <QueryBoundary query={{ ...base, isPending: true }} skeleton={<div>loading…</div>}>
          {() => <div>data</div>}
        </QueryBoundary>,
      )
      expect(screen.queryByText("loading…")).not.toBeInTheDocument()
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(screen.getByText("loading…")).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it("shows the error state with a retry button when there is no data", () => {
    const refetch = vi.fn()
    render(
      <QueryBoundary
        query={{ ...base, isError: true, refetch }}
        skeleton={<div>loading…</div>}
        errorMessage="Falló"
      >
        {() => <div>data</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("Falló")).toBeInTheDocument()
    screen.getByRole("button", { name: /reintentar/i }).click()
    expect(refetch).toHaveBeenCalled()
  })

  it("keeps data visible when a background refetch fails", () => {
    const refetch = vi.fn()
    render(
      <QueryBoundary
        query={{ ...base, isError: true, data: 42, refetch }}
        skeleton={<div>loading…</div>}
      >
        {(n) => <div>value {n}</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("value 42")).toBeInTheDocument()
    expect(screen.getByRole("alert")).toBeInTheDocument()
    screen.getByRole("button", { name: /reintentar/i }).click()
    expect(refetch).toHaveBeenCalled()
  })

  it("shows the empty node when the empty predicate matches", () => {
    render(
      <QueryBoundary
        query={{ ...base, data: [] as number[] }}
        skeleton={<div>loading…</div>}
        empty={{ when: (d) => d.length === 0, node: <div>vacío</div> }}
      >
        {() => <div>data</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("vacío")).toBeInTheDocument()
  })

  it("renders children with data on success", () => {
    render(
      <QueryBoundary query={{ ...base, data: 42 }} skeleton={<div>loading…</div>}>
        {(n) => <div>value {n}</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("value 42")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && pnpm test -- query-boundary`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `frontend/components/query-boundary.tsx`:
```tsx
"use client"

import { type ReactNode, useEffect, useState } from "react"
import { ErrorState } from "@/components/error-state"

type QueryLike<T> = {
  isPending: boolean
  isError: boolean
  data: T | undefined
  refetch: () => void
}

export function QueryBoundary<T>({
  query,
  skeleton,
  empty,
  errorMessage = "No se pudo cargar",
  delayMs = 150,
  children,
}: {
  query: QueryLike<T>
  skeleton: ReactNode
  empty?: { when: (data: T) => boolean; node: ReactNode }
  errorMessage?: string
  delayMs?: number
  children: (data: T) => ReactNode
}) {
  const [showSkeleton, setShowSkeleton] = useState(delayMs === 0)
  useEffect(() => {
    if (!query.isPending) {
      setShowSkeleton(false)
      return
    }
    if (delayMs === 0) {
      setShowSkeleton(true)
      return
    }
    const t = setTimeout(() => setShowSkeleton(true), delayMs)
    return () => clearTimeout(t)
  }, [query.isPending, delayMs])

  // Data-first: loaded data stays visible even if a background refetch fails.
  if (query.data !== undefined) {
    return (
      <>
        {query.isError ? (
          <p role="alert" className="text-xs" style={{ color: "var(--expense)" }}>
            No se pudo actualizar.{" "}
            <button type="button" className="underline" onClick={query.refetch}>
              Reintentar
            </button>
          </p>
        ) : null}
        {empty && empty.when(query.data) ? empty.node : children(query.data)}
      </>
    )
  }
  if (query.isError) {
    return <ErrorState message={errorMessage} onRetry={query.refetch} />
  }
  return showSkeleton ? <>{skeleton}</> : null
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && pnpm test -- query-boundary`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add frontend/components/query-boundary.tsx frontend/components/query-boundary.test.tsx && \
  git commit -m "feat(ui): QueryBoundary owns async-state selection (v5 semantics, data-first)"
```

---

### Task B4: Migrate the budgets page (fixes the confirmed blank bug)

Both boundaries use the default 150ms anti-flash delay — no `delayMs={0}` in production code. The page tests respect the delay via `waitFor` (real timers; the default `waitFor` timeout of 1s comfortably covers 150ms). Tests must not assert on the page's `useState` month plumbing (ADR-0027 follow-up will move it to the URL).

**Files:**
- Modify: `frontend/app/(app)/budgets/page.tsx`
- Create: `frontend/app/(app)/budgets/page.test.tsx`

**Interfaces:**
- Consumes: `QueryBoundary` (B3), `SkeletonCard`/`SkeletonRows` (B2), `EmptyState` (B1).

- [ ] **Step 1: Write the failing test (loading + error + empty)**

Create `frontend/app/(app)/budgets/page.test.tsx`. Mock the API module so the page's queries resolve deterministically:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api/budgets", () => ({
  safeToSpend: vi.fn(),
  listBudgets: vi.fn(),
  assignBudget: vi.fn(),
}))

import { listBudgets, safeToSpend } from "@/lib/api/budgets"
import BudgetsPage from "./page"

const STS = {
  year_month: "2026-07",
  income_forecast: 0,
  committed: 0,
  assigned_envelopes: 0,
  free: 0,
  committed_breakdown: [],
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <BudgetsPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("BudgetsPage async states", () => {
  it("shows a skeleton while loading (after the anti-flash delay)", async () => {
    vi.mocked(safeToSpend).mockReturnValue(new Promise(() => {})) // never resolves
    vi.mocked(listBudgets).mockReturnValue(new Promise(() => {}))
    const { container } = renderPage()
    await waitFor(() =>
      expect(
        container.querySelectorAll('[data-slot="skeleton"]').length,
      ).toBeGreaterThan(0),
    )
  })

  it("shows the error state with retry when safe-to-spend fails", async () => {
    vi.mocked(safeToSpend).mockRejectedValue(new Error("boom"))
    vi.mocked(listBudgets).mockResolvedValue([])
    renderPage()
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument(),
    )
  })

  it("shows an empty state when there are no envelopes", async () => {
    vi.mocked(safeToSpend).mockResolvedValue(STS)
    vi.mocked(listBudgets).mockResolvedValue([])
    renderPage()
    await waitFor(() =>
      expect(screen.getByText("Aún no hay sobres este mes")).toBeInTheDocument(),
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && pnpm test -- budgets/page`
Expected: FAIL — current page renders nothing while loading (the exact bug) and hides the envelopes section entirely when empty.

- [ ] **Step 3: Wrap both queries in `QueryBoundary`**

In `frontend/app/(app)/budgets/page.tsx`, add imports:
```tsx
import { QueryBoundary } from "@/components/query-boundary"
import { EmptyState } from "@/components/empty-state"
import { SkeletonCard, SkeletonRows } from "@/components/skeleton"
```
Replace the `{sts.isError && (...)}` block and the `{sts.data && (...)}` block with a single boundary (default delay — do NOT pass `delayMs`), and replace the `{lines.data && lines.data.length > 0 && (...)}` envelopes block with a second boundary:
```tsx
<QueryBoundary
  query={sts}
  skeleton={<SkeletonCard />}
  errorMessage="No se pudo cargar disponible para gastar"
>
  {(data) => (
    <div
      className="space-y-4 rounded-lg border p-5"
      style={{ borderColor: "var(--border)", background: "var(--card)" }}
    >
      {/* ...existing summary JSX, using `data` instead of `sts.data`... */}
    </div>
  )}
</QueryBoundary>

<QueryBoundary
  query={lines}
  skeleton={<SkeletonRows rows={6} />}
  errorMessage="No se pudieron cargar los sobres"
  empty={{
    when: (rows) => rows.length === 0,
    node: <EmptyState message="Aún no hay sobres este mes" />,
  }}
>
  {(rows) => (
    <div className="space-y-3">
      {/* ...existing envelopes table JSX, using `rows` instead of `lines.data`... */}
    </div>
  )}
</QueryBoundary>
```
Update the inner JSX references from `sts.data`/`lines.data` to the render-prop `data`/`rows`. Keep the `assign` mutation, `assignForm` logic, and the `month` `useState` unchanged.

- [ ] **Step 4: Run page + budgets-related tests**

Run: `cd frontend && pnpm test -- budgets && pnpm check`
Expected: PASS; Biome clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add "frontend/app/(app)/budgets/page.tsx" "frontend/app/(app)/budgets/page.test.tsx" && \
  git commit -m "fix(budgets): render loading/empty/error states (no more blank page)"
```

---

### Task B5: Migrate reports page + dashboard

Dashboard query→UI map (verified against `frontend/app/(app)/page.tsx`): the **hero** uses `sts` and the local `Skeleton`; the "Ingresos · Gastos · Neto" card uses `report`; "Saldos" uses `accounts`; "Metas" uses `goals`; "Sobres en riesgo" uses **`report`**, not `sts` — it reads `report.data.envelopes`. The local `Skeleton` has five usages (hero + four cards); it is deleted **only after** all five are replaced, otherwise the file does not compile.

**Files:**
- Modify: `frontend/app/(app)/reports/page.tsx`
- Modify: `frontend/app/(app)/page.tsx`

**Interfaces:**
- Consumes: `QueryBoundary` (B3), skeleton variants (B2), `EmptyState` (B1).

- [ ] **Step 1: Migrate the reports page (boundary + honest empty sections)**

In `frontend/app/(app)/reports/page.tsx`:
1. Add imports: `QueryBoundary`, `SkeletonCard`, `EmptyState`.
2. Replace the manual `{isLoading && (...)}`, `{isError && (...)}`, `{data && (...)}` triad with one boundary (default delay):
```tsx
<QueryBoundary
  query={q}
  skeleton={
    <div className="space-y-3">
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  }
  errorMessage="No se pudo cargar el reporte"
>
  {(data) => (
    <div className="space-y-6 animate-fade-up">
      {/* sections, per point 3 below */}
    </div>
  )}
</QueryBoundary>
```
(The page currently destructures `{ data, isLoading, isError, refetch }` — change it to `const q = useQuery(...)` and use `q` for the boundary.)
3. **The sections JSX changes** (this is a spec requirement, not a copy-paste): the "Sobres", "Por categoría", and "Por grupo" sections are currently gated `{data.envelopes.length > 0 && <Section>...}` etc., so empty months silently lose whole sections. Replace each gate so the `Section` always renders and the empty case is honest:
```tsx
<Section title="Sobres">
  {data.envelopes.length > 0 ? (
    /* existing table JSX */
  ) : (
    <EmptyState
      message="Sin sobres este mes"
      action={{ label: "Ir a presupuestos", href: "/budgets" }}
    />
  )}
</Section>

<Section title="Por categoría">
  {data.by_category.length > 0 ? (
    /* existing rows JSX */
  ) : (
    <EmptyState message="Sin gastos este mes" />
  )}
</Section>

<Section title="Por grupo">
  {data.by_group.length > 0 ? (
    /* existing rows JSX */
  ) : (
    <EmptyState message="Sin gastos agrupados este mes" />
  )}
</Section>
```
4. Delete the now-unused inline `animate-pulse` skeleton markup and the standalone `ErrorState` usage (the boundary supplies both). Keep the `month` `useState` unchanged (ADR-0027 follow-up).

- [ ] **Step 2: Migrate the dashboard — hero first, then the four cards, then delete the local Skeleton**

In `frontend/app/(app)/page.tsx`, add imports:
```tsx
import { QueryBoundary } from "@/components/query-boundary"
import { EmptyState } from "@/components/empty-state"
import { SkeletonBlock, SkeletonText } from "@/components/skeleton"
```
Migrate all five usages of the local `Skeleton`:

1. **Hero (`sts`)** — replace the `sts.isLoading ? <Skeleton/> : sts.data ? ... : "No disponible"` ternary (the "No disponible" string is an error state in disguise; the boundary renders a real `ErrorState`):
```tsx
<QueryBoundary
  query={sts}
  skeleton={<SkeletonBlock className="h-14 w-64" />}
  errorMessage="No se pudo cargar disponible para gastar"
>
  {(data) => (
    <p className="font-display text-gradient-mint text-5xl font-bold tabular-nums tracking-tight sm:text-6xl">
      {formatCents(data.free, "COP")}
    </p>
  )}
</QueryBoundary>
```
2. **"Ingresos · Gastos · Neto" card (`report`)** — boundary with `skeleton={<SkeletonText lines={3} />}`; children = the existing three `Row`s using `data.income`/`data.expense`/`data.net`. The `: "Sin datos"` branch disappears (it was an error state; the boundary handles it).
3. **"Saldos" card (`accounts`)** — boundary with `skeleton={<SkeletonText lines={2} />}` and
```tsx
empty={{
  when: (d) => d.filter((a) => !a.archived).length === 0,
  node: <EmptyState message="Sin cuentas" action={{ label: "Crear cuenta", href: "/accounts" }} />,
}}
```
4. **"Metas" card (`goals`)** — boundary with `skeleton={<SkeletonBlock className="h-16" />}` and `empty={{ when: (d) => d.length === 0, node: <EmptyState message="Sin metas activas" /> }}`.
5. **"Sobres en riesgo" card (`report` — same query as card 2, NOT `sts`)** — boundary with `skeleton={<SkeletonBlock className="h-16" />}`; children keep the existing inner logic (the "Todos los sobres al día" line is *success* content when nothing is over, not an empty state — leave it).

**Only after** all five usages compile against the new boundaries: delete the local `function Skeleton(...)` definition (lines ~48–52).

- [ ] **Step 3: Run the full frontend suite + lint**

Run: `cd frontend && pnpm test && pnpm check`
Expected: PASS; Biome clean. Also run `pnpm build` to typecheck under Next 16 — before editing further, read the relevant guide in `node_modules/next/dist/docs/` per `frontend/AGENTS.md` if any Next API is touched.

- [ ] **Step 4: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add "frontend/app/(app)/reports/page.tsx" "frontend/app/(app)/page.tsx" && \
  git commit -m "refactor(dashboard,reports): consistent async states via QueryBoundary"
```

---

### Task B6: Manual verification in the running app

**Files:** none (verification only).

- [ ] **Step 1: Rebuild and reload**

Run: `cd /Users/angelozdev/me/quaestor && just dev-down && just dev-real` (or the project's normal dev command), then open `http://localhost:3000`.

- [ ] **Step 2: Verify states and speed, with numbers**

Confirm, per page: (a) a visible skeleton appears after ~150ms then resolves — no blank void on Presupuestos or Reportes; (b) empty sections show an `EmptyState` message/CTA, not an empty box and not a vanished section (check Reportes on a month with no data); (c) in the Network panel, record the response times for `/api/reports` and `/api/budgets` and note them in the PR/commit description alongside the pre-refactor multi-second hang. If a hang remains: the query-count tests bound the number of round trips, so a residual hang is network/DB latency or row volume — capture the observed timing and open a follow-up rather than assuming the refactor covered it.

---

## Self-Review

**Spec coverage:**
- Honest loading/error/empty/success on the three in-scope pages → Tasks B1–B5 (spec Goal 1 scopes this to budgets/reports/dashboard; remaining pages are explicit follow-up).
- Budgets missing loading branch (the confirmed blank bug) → Task B4.
- Reports sections vanishing on empty months → Task B5 Step 1 point 3.
- Dark-invisible skeleton → Task B2.
- Dashboard duplicate `Skeleton` + "No disponible"/"Sin datos" fake states → Task B5 Step 2 (hero + 4 cards, correct query mapping, delete-last ordering).
- Failed-refetch must not hide data (v5 `isPending`, data-first) → Task B3.
- Anti-flash 150ms in production, tested with fake timers / `waitFor` → B3/B4 (no `delayMs={0}` outside tests).
- Bounded read-path (`MonthAggregate`: GROUP BY history + two-month window + memoized fold) → Tasks A3–A5.
- Rollover semantics incl. gap reset pinned → A2 (API-level golden) + A3 (unit).
- Known linearities (FX, goals, pendings) documented and inside seeded bounds → A4/A5 seeds + Global Constraints.
- Index matched to shipped queries (one index; dead candidates dropped) → Task A6.
- Unchanged API contracts → guarded by characterization tests (A2).
- ADRs (incl. READ COMMITTED note, write-path cost, incremental frontend scope) → Task A1.
- ADR-0003 (pnpm) respected in every frontend command; ADR-0027 relationship stated (month stays in `useState`; tests don't pin it).

**Red-test integrity:** A4/A5 Step 2 both instruct: if the "red" test passes before the refactor, STOP and fix the seed — a green red-test guards nothing. Seeds were chosen so current code demonstrably exceeds the bounds (multi-month budgets → recursion; recurring/goals → per-item paths).

**Type consistency:** `MonthAggregate` accessor names (`assigned`, `spent_for_budget`, `available`, `totals_for`, `month_expense`, `group_name`, `category`, `budgeted_category_ids`, `budgets_month`, `active_recurring`, `month_planned_expense`) are used identically in Tasks A3/A4/A5. `QueryBoundary` prop shape (`query{isPending,isError,data,refetch}/skeleton/empty/errorMessage/delayMs/children`) matches across B3/B4/B5. `EmptyState` `action` shape matches B1 and its consumers. Skeleton exports (`SkeletonText`, `SkeletonCard`, `SkeletonRows`, `SkeletonBlock`) match B2 and usages in B4/B5.
